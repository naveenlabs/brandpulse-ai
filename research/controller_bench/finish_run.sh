#!/bin/zsh
# finish_run.sh — run every remaining stage unattended, cheapest-first.
#
# Order matters and is deliberate. `qwen3_8b` was moved to the END because it is
# far slower than every other candidate and fails gate G4, and a candidate that
# fails a gate is not adoptable whatever its accuracy (PROTOCOL.md §8). Run first,
# it would hold the other four models and every later stage behind it for over two
# hours; run last, its accuracy row is still collected in full and nothing waits.
#
# Final measured figures, once it completed (PROTOCOL.md Amendment A4): median
# 45.5 s per successful call against the incumbent's 2.13 s and a 6.39 s gate,
# and a 75.9% parse rate against a 95% gate — it fails G1 as well as G4. The
# ">48 s" figure this comment carried during the run was a lower bound taken while
# it was still going.
#
# Everything caches and resumes, so nothing already computed is recomputed.

set -u
cd "$(dirname "$0")/../.."
# The project's environment must be active (README.md, Setup); this used to
# source one virtualenv by its absolute path on the author's machine.
if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "activate the project's virtualenv first (README.md, Setup)" >&2
  exit 1
fi

FAST="llama3.2,llama3.1_8b,qwen2.5_7b,mistral_7b,gemma3_4b,phi4_mini,granite3.3_8b,rule_baseline,always_zero,always_flag"

echo "=== GRID (all but qwen3_8b) ==="
python research/controller_bench/run_bench.py --stage grid --only "$FAST"

echo "=== INCONGRUENCE ==="
python research/controller_bench/run_bench.py --stage incongruence --only "$FAST"

echo "=== DETERMINISM (G2) ==="
python research/controller_bench/run_bench.py --stage determinism --only "$FAST"

# The two ablation challengers are picked by measured P1 from the finished grid,
# not named here, so the choice cannot be steered after seeing the ablation.
TOP2=$(python - <<'PY'
import sys
sys.path.insert(0, "research/controller_bench")
import candidates as C, report_bench as RPT
rows = []
for n in C.LLM_CANDIDATES:
    if n == RPT.INCUMBENT:
        continue
    g = RPT.score_grid(n)
    if g:
        rows.append((g["P1_mcc"], n))
rows.sort(reverse=True)
print(",".join(n for _p, n in rows[:2]))
PY
)
echo "=== ABLATION (Q2): llama3.2,$TOP2 ==="
python research/controller_bench/run_bench.py --stage ablation --only "llama3.2,$TOP2"

echo "=== CORPUS (decisive set first, for Rule 7) ==="
python research/controller_bench/run_bench.py --stage corpus \
    --only "llama3.2,$TOP2,rule_baseline,always_zero,always_flag"

echo "=== CORPUS (breadth) ==="
python research/controller_bench/run_bench.py --stage corpus \
    --only "mistral_7b,gemma3_4b,phi4_mini,granite3.3_8b"

# Last, and only the grid: the accuracy row is worth having, the 481-segment
# corpus run for a gate-failing candidate is not.
echo "=== QWEN3 GRID (slow, gate-failing, run last) ==="
python research/controller_bench/run_bench.py --stage grid --only "qwen3_8b"
python research/controller_bench/run_bench.py --stage incongruence --only "qwen3_8b"

echo "=== FINISHRUNDONE $(date) ==="
