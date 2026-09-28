#!/usr/bin/env bash

set -Eeuo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly OLLAMA_MODEL="llama3.1:8b"
readonly OLLAMA_URL="http://127.0.0.1:11434/api/tags"

MODE="full"
case "${1:-}" in
  "") ;;
  --saved-reports-only) MODE="saved" ;;
  -h|--help)
    cat <<'EOF'
Usage: bash setup.sh [--saved-reports-only]

Without an option, prepare everything required to run a new analysis.
Use --saved-reports-only to install the application without ffmpeg, Ollama,
or the 4.9 GB controller model.
EOF
    exit 0
    ;;
  *)
    printf 'Unknown option: %s\n' "$1" >&2
    printf 'Run "bash setup.sh --help" for usage.\n' >&2
    exit 2
    ;;
esac

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'
  CYAN=$'\033[36m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  RESET=$'\033[0m'
else
  BOLD="" CYAN="" GREEN="" YELLOW="" RESET=""
fi

step() { printf '\n%s%s%s\n' "${BOLD}${CYAN}" "$1" "$RESET"; }
ok() { printf '%s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
note() { printf '%s•%s %s\n' "$YELLOW" "$RESET" "$1"; }
fail() { printf '\nSetup stopped: %s\n' "$1" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif has sudo; then
    sudo "$@"
  else
    fail "Administrator access is required to install system packages."
  fi
}

load_homebrew() {
  if has brew; then
    return
  fi

  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    return
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
    return
  fi

  step "Installing Homebrew"
  has curl || fail "curl is required to install Homebrew."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
  has brew || fail "Homebrew installed but is not available in this terminal. Follow the Homebrew 'Next steps', then rerun setup."
}

install_linux_package() {
  local package="$1"
  if has apt-get; then
    run_as_root apt-get update
    run_as_root apt-get install -y "$package"
  elif has dnf; then
    run_as_root dnf install -y "$package"
  elif has pacman; then
    run_as_root pacman -S --needed --noconfirm "$package"
  elif has zypper; then
    run_as_root zypper --non-interactive install "$package"
  else
    return 1
  fi
}

install_uv() {
  step "Installing the Python 3.11 manager"
  has curl || install_linux_package curl || fail "Install curl, then rerun setup."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  has uv || fail "The Python manager installed but is not available in this terminal. Reopen it and rerun setup."
  uv python install 3.11
}

prepare_python() {
  step "Preparing Python 3.11"

  cd "$PROJECT_ROOT"
  if [[ -x .venv/bin/python ]]; then
    .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 11))' \
      || fail ".venv uses a different Python version. Remove .venv and rerun setup."
    ok "Reusing the existing Python 3.11 environment"
  else
    if ! has python3.11; then
      if [[ "$OSTYPE" == darwin* ]]; then
        load_homebrew
        brew install python@3.11
      elif [[ "$OSTYPE" == linux* ]]; then
        if has apt-get; then
          run_as_root apt-get update
          run_as_root apt-get install -y python3.11 python3.11-venv || true
        elif has dnf; then
          run_as_root dnf install -y python3.11 || true
        elif has zypper; then
          run_as_root zypper --non-interactive install python311 python311-pip || true
        fi
      fi
    fi

    if has python3.11; then
      if ! python3.11 -m venv .venv; then
        if [[ "$OSTYPE" == linux* ]] && has apt-get; then
          run_as_root apt-get install -y python3.11-venv
          python3.11 -m venv .venv
        else
          fail "Python 3.11 could not create a virtual environment. Install its venv component and rerun setup."
        fi
      fi
      ok "Created .venv with Python 3.11"
    else
      has uv || install_uv
      uv venv --seed --python 3.11 .venv
      ok "Created .venv with Python 3.11"
    fi
  fi

  .venv/bin/python -m pip install --upgrade pip setuptools wheel
  .venv/bin/python -m pip install -r requirements.txt
  ok "Installed the Python packages"
}

prepare_macos_tools() {
  load_homebrew
  step "Installing ffmpeg and Ollama"
  has ffmpeg || brew install ffmpeg
  has ollama || brew install ollama
  if brew list --formula ollama >/dev/null 2>&1; then
    brew services start ollama >/dev/null
  fi
  ok "ffmpeg and Ollama are installed"
}

prepare_linux_tools() {
  step "Installing ffmpeg"
  has ffmpeg || install_linux_package ffmpeg \
    || fail "No supported package manager was found. Install ffmpeg, then rerun setup."
  ok "ffmpeg is installed"

  if ! has ollama; then
    step "Installing Ollama"
    has curl || install_linux_package curl || fail "Install curl, then rerun setup."
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  has ollama || fail "Ollama installed but its command is not available. Reopen the terminal and rerun setup."
  ok "Ollama is installed"
}

ollama_ready() {
  curl --silent --fail --max-time 2 "$OLLAMA_URL" >/dev/null 2>&1
}

start_ollama() {
  if ollama_ready; then
    ok "Ollama is running"
    return
  fi

  step "Starting Ollama"
  if [[ "$OSTYPE" == darwin* ]] && has brew; then
    brew services start ollama >/dev/null || true
  elif has systemctl; then
    run_as_root systemctl start ollama >/dev/null 2>&1 || true
  fi

  if ! ollama_ready; then
    nohup ollama serve >"${TMPDIR:-/tmp}/brandpulse-ollama.log" 2>&1 &
  fi

  local attempt
  for attempt in {1..30}; do
    if ollama_ready; then
      ok "Ollama is running"
      return
    fi
    sleep 1
  done
  fail "Ollama did not start. Run 'ollama serve' in another terminal, then rerun setup."
}

prepare_analysis_tools() {
  if [[ "$OSTYPE" == darwin* ]]; then
    prepare_macos_tools
  elif [[ "$OSTYPE" == linux* ]]; then
    prepare_linux_tools
  else
    fail "This installer supports macOS and Linux. On Windows, run setup.ps1 in PowerShell."
  fi

  has ffmpeg || fail "ffmpeg is installed but is not available on PATH. Reopen the terminal and rerun setup."
  has ollama || fail "Ollama is installed but is not available on PATH. Reopen the terminal and rerun setup."
  start_ollama

  step "Downloading the local controller model"
  ollama pull "$OLLAMA_MODEL"
  ollama show "$OLLAMA_MODEL" >/dev/null
  ok "$OLLAMA_MODEL is ready"
}

prepare_environment_file() {
  if [[ -f .env ]]; then
    ok "Kept the existing private .env file"
  else
    cp .env.example .env
    ok "Created .env from .env.example"
  fi
}

main() {
  cd "$PROJECT_ROOT"
  printf '%sBrandPulse AI setup%s\n' "$BOLD" "$RESET"
  [[ "$MODE" == "saved" ]] && note "Saved-report mode: ffmpeg, Ollama and the controller model will be skipped."

  prepare_python
  if [[ "$MODE" == "full" ]]; then
    prepare_analysis_tools
  fi
  prepare_environment_file

  step "Setup complete"
  printf 'Run the application with:\n\n'
  printf '  .venv/bin/python -m flask --app app run --port 5001\n\n'
  printf 'Then open http://localhost:5001\n'
  if [[ "$MODE" == "full" ]]; then
    printf 'Before a new analysis, open .env and replace the YouTube API key placeholder.\n'
  fi
}

main
