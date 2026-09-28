/* api.js — every request this interface makes.

   All of them are same-origin by construction: the paths below are relative
   and no absolute URL appears anywhere in this build. A test asserts that no
   third-party host is named in the built output, because "nothing leaves this
   machine" is the product's central claim and the interface must not be the
   thing that breaks it. */

/** Throw with the server's own message when it sent one. */
async function unwrap(response) {
  let body = null;
  try { body = await response.json(); } catch { /* not JSON; fall through */ }
  if (!response.ok) {
    const message = (body && (body.error || body.message)) || `${response.status} ${response.statusText}`;
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

/* A report is a JSON file on disk, and so are the written reports beside it.
   The pages print some of their numbers straight into markup: segment ids as
   attribute values and selectors, class counts as style values, a few counts
   and accuracies as text. The pipeline only ever writes numbers there, but a
   hand-edited or copied-in file could put markup in their place, and measured
   on 26 Sep 2026 that ran script on the report page (the segment ids and the
   audience counts of a report; nine fields of its written report). So those
   fields are held to numbers here, once, for every page that reads them. A
   number or an empty value passes through untouched, so a file the pipeline
   wrote reads exactly as before. */
const numberOr = (value, fallback) =>
  (typeof value === "number" && Number.isFinite(value)) || value == null ? value : fallback;

export function asReport(report) {
  if (!report || typeof report !== "object") return report;
  for (const key of ["all_segments", "flagged_segments"]) {
    const list = report[key];
    if (!Array.isArray(list)) continue;
    list.forEach((segment, i) => {
      if (segment && typeof segment === "object") segment.segment_id = numberOr(segment.segment_id, -1 - i);
    });
  }
  const dist = report.comment_sentiment && report.comment_sentiment.distribution;
  if (dist && typeof dist === "object") {
    for (const k of Object.keys(dist)) dist[k] = numberOr(dist[k], 0);
  }
  return report;
}

/* A sweep's record prints its audience's class counts as style values, like a
   report's (measured the same day; nothing else in the record reached markup). */
export function asSweep(record) {
  const dist = record && record.summary && record.summary.comment_distribution;
  if (dist && typeof dist === "object") {
    for (const k of Object.keys(dist)) dist[k] = numberOr(dist[k], 0);
  }
  return record;
}

/* Keys that hold a number wherever the analyst writes them (pipeline/analyst*.py;
   the combined report's included), and the two places where `comment`,
   `transcript` and `dropped` do; elsewhere those three name a label, a coverage
   record or a list. Only a text value is replaced: text is the only thing that
   can become markup, so an object or a list under one of these keys is looked
   inside rather than discarded. */
const ANALYSIS_NUMBERS = new Set([
  "seg", "POSITIVE", "NEUTRAL", "NEGATIVE", "checked", "present",
  "n", "i", "count", "of", "talked", "praise_in", "criticism_in",
]);
const scalarNumberOr = (value, fallback) =>
  (value && typeof value === "object" ? value : numberOr(value, fallback));

export function asAnalysis(analysis) {
  if (!analysis || typeof analysis !== "object") return analysis;
  (function walk(node) {
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!node || typeof node !== "object") return;
    for (const [key, value] of Object.entries(node)) {
      if (ANALYSIS_NUMBERS.has(key)) node[key] = scalarNumberOr(value, null);
      walk(node[key]);
    }
  })(analysis);
  const accuracy = analysis.facts && analysis.facts.confidence && analysis.facts.confidence.accuracy;
  if (accuracy && typeof accuracy === "object") {
    for (const k of ["comment", "transcript"]) if (k in accuracy) accuracy[k] = scalarNumberOr(accuracy[k], null);
  }
  const byField = analysis.verifier && analysis.verifier.by_field;
  if (byField && typeof byField === "object") {
    for (const field of Object.values(byField)) {
      if (field && typeof field === "object" && "dropped" in field) field.dropped = scalarNumberOr(field.dropped, 0);
    }
  }
  return analysis;
}

export const listReports = () => fetch("/reports").then(unwrap);

export const getReport = (filename) =>
  fetch(`/reports/${encodeURIComponent(filename)}`).then(unwrap).then(asReport);

/* Both deletes are permanent and reach the filesystem: there is no trash and
   nothing to undo them with. The confirmation that guards them is the caller's
   job, not this module's — these do exactly what they are told, at once.

   Deleting a sweep deletes the member reports inside it, because a sweep IS
   the directory they live in. Deleting a report reaches only that one file.
   Neither touches the frames under static/frames/, which are shared. */

export const deleteReport = (filename) =>
  fetch(`/reports/${encodeURIComponent(filename)}`, { method: "DELETE" }).then(unwrap);

export const deleteSweep = (sweepId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}`, { method: "DELETE" }).then(unwrap);

export const getFigures = () => fetch("/evidence/figures.json").then(unwrap);

export const getManifest = () => fetch("/static/frames/manifest.json").then(unwrap);

export const activeJob = () => fetch("/analyse/active").then(unwrap);

export const jobStatus = (jobId) => fetch(`/analyse/status/${jobId}`).then(unwrap);

export const startJob = (body) =>
  fetch("/analyse/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(unwrap);

export const cancelJob = (jobId) =>
  fetch(`/analyse/cancel/${jobId}`, { method: "POST" }).then(unwrap);

/* Sweeps: five videos about one subject.

   The search is a separate request from the start on purpose. Searching costs
   one API call and starts nothing; starting costs an hour of this machine. A
   person reads the candidates and their verdicts in between. */

export const sweepSearch = (body) =>
  fetch("/sweep/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(unwrap);

export const sweepStart = (body) =>
  fetch("/sweep/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(unwrap);

export const sweepStatus = (jobId) => fetch(`/sweep/status/${jobId}`).then(unwrap);

export const cancelSweep = (jobId) =>
  fetch(`/sweep/cancel/${jobId}`, { method: "POST" }).then(unwrap);

export const listSweeps = () => fetch("/sweeps").then(unwrap);

export const getSweep = (sweepId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}`).then(unwrap).then(asSweep);

export const getSweepMember = (sweepId, videoId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}/members/${encodeURIComponent(videoId)}`)
    .then(unwrap).then(asReport);

/* The written report beside a report: the model's analysis once it has run,
   or the facts layer computed live until then. Same origin, like everything
   here; the analysis itself was written on this machine. */
export const getReportAnalysis = (filename) =>
  fetch(`/reports/${encodeURIComponent(filename)}/analysis`).then(unwrap).then(asAnalysis);

export const getMemberAnalysis = (sweepId, videoId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}/members/${encodeURIComponent(videoId)}/analysis`)
    .then(unwrap).then(asAnalysis);

/* The combined written report for a sweep, or its facts computed live; and
   two sweeps of one subject held against each other (both computed on this
   machine from files already on it -- neither searches anything). */
export const getSweepAnalysis = (sweepId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}/analysis`).then(unwrap).then(asAnalysis);

export const compareSweeps = (sweepId, otherId) =>
  fetch(`/sweeps/${encodeURIComponent(sweepId)}/compare/${encodeURIComponent(otherId)}`)
    .then(unwrap).then(asAnalysis);
