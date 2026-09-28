/* ===========================================================================
   frames.js — resolving a second of video to an image, honestly.

   `ui_build/build_frames.py` and `frame_cache.py` derive images from the 1 fps
   frames the pipeline actually analysed: a 1440px PLATE at every segment
   midpoint, a 560px WINDOW frame at every second inside a flagged segment,
   and one sprite STRIP per video for the opening film (stripInfo). A 2560px
   hero size is derived on request, and no page asks for it. The manifest is
   the only authority on what exists.

   The one rule here: never return a URL for a frame that was not derived.
   A broken image would read as "the system saw nothing", which is a claim
   about the data rather than about the build, and those must not be confused.
   ======================================================================== */

import { getManifest } from "./api.js";

let cached = null;

export async function manifest() {
  if (!cached) {
    try { cached = await getManifest(); }
    catch { cached = { videos: {} }; }   // no imagery derived; pages draw the absence
  }
  return cached;
}

/** The 11-character YouTube id in a report's video_url, or null. */
export function videoIdOf(report) {
  const match = String((report && report.video_url) || "")
    .match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/);
  return match ? match[1] : null;
}

/** The whole second at a segment's midpoint — what the plate was derived at. */
export const midpointOf = (segment) =>
  Math.floor((segment.start_s + segment.end_s) / 2);

/**
 * A URL for one whole second, at the best size derived, or null.
 * Plates are preferred; window frames are the fallback inside flagged spans.
 */
export function frameAt(man, videoId, second) {
  const video = man && man.videos && man.videos[videoId];
  if (!video) return null;
  if (video.seconds && video.seconds.includes(second)) {
    return `/static/frames/${videoId}/p/${second}.jpg`;
  }
  if (video.window_seconds && video.window_seconds.includes(second)) {
    return `/static/frames/${videoId}/w/${second}.jpg`;
  }
  return null;
}

/** The plate for a segment, or null when it was never derived. */
export const plateFor = (man, videoId, segment) =>
  frameAt(man, videoId, midpointOf(segment));

/** Whether any imagery at all was derived for a video. */
export const hasImagery = (man, videoId) =>
  Boolean(man && man.videos && man.videos[videoId]);

/** Sprite-sheet geometry for the scrub strip, or null. */
export function stripInfo(man, videoId) {
  const video = man && man.videos && man.videos[videoId];
  if (!video || !video.strip) return null;
  return {
    url: `/static/frames/${videoId}/strip.jpg`,
    ...video.strip,
    tile: video.tile,
    seconds: video.seconds,
    hero: video.hero || null,
  };
}

