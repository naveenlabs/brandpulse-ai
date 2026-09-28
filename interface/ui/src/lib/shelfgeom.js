/* ===========================================================================
   shelfgeom.js — the bookcase's dimensions, with no renderer attached.

   These numbers are wanted in two places that must not both pay for Three.js.
   `shelf.js` needs them to build the carcass; `library.js` needs the case's
   PROPORTION before it decides how tall to make the stage, and library.js is
   the page's entry chunk. Keeping the arithmetic here means the page can size
   its own furniture from ~1 KB of maths and still fetch the 500 KB renderer
   only when it is going to draw something.

   Nothing in this file touches the DOM or WebGL, so it is also the part that
   can be reasoned about on paper.
   =========================================================================== */

export const SHELF_LAYOUT = {
  perShelf: 3,        // volumes across one shelf
  minRows: 4,         // EVERY case is a finished four-shelf carcass, however
                      // few volumes it holds. See shelfRows.
  bookW: 0.887, bookH: 1.33, bookD: 0.17,   // the registered 2:3 format
  slot: 1.235,        // volume pitch across a shelf, registered
  rowH: 1.62,         // shelf pitch, leaving headroom over a standing volume
  bayGap: 0.16,       // the upright between two cases
  plankThick: 0.105, plankDepth: 0.80,
  lean: -0.20, yaw: 0.155,
  bow: 0.0080, chamf: 0.0135, chamfR: 0.022,

  /* boxCY, registered. The camera looks at (0, boxCY, 0) and a lifted volume
     comes to rest at boxCY - 0.02 -- that pairing is why the registered
     composition holds a volume dead centre when it is brought to hand. The
     build this replaces dropped boxCY, aimed the camera at boxY * 0.255
     instead (about 1.8 units, thirty times the registered offset) to clear
     room for a masthead, and left the volume resting at y = 0. The gap
     between those two numbers, magnified by the 60%-fill zoom in activeZ(),
     is exactly why an opened volume was landing off the edge of the canvas. */
  boxCY: 0.06,

  /* FRAMING. padX/padY are the wall left around the carcass, in the same units
     as the carcass itself. They were 0.70 and 1.00; the 1.00 existed to hold
     the three case labels, which now sit in the masthead above the stage where
     they can be aligned to real type. Giving that band back to the furniture
     is the single cheapest way to put more pixels on a cover, and pixels on a
     cover are the whole complaint this revision answers. padY keeps about 20px
     of floor under the bottom rail: at 0.30 the carcass sat flush on the frame
     edge and read as cut off rather than as standing on something. */
  padX: 0.44, padY: 0.42,
  /* offset and maxWidthPx are the registered framing, restored. 1.015 was
     drift: it cropped the room to 1.5% of margin where the source asks for
     25%, which is most of why the shelf stopped reading as a room and
     started reading as a wall of covers. */
  fov: 20, offset: 1.25, maxWidthPx: 1550,

  orbitAz: 0.085, orbitEl: 0.052,

  /* HOW FAR THE ROOM SWINGS WHILE A VOLUME IS IN HAND.

     The camera orbits toward the pointer, so moving the mouse right swings
     the camera right and the volume appears to go left -- inverted, which is
     what an orbit is and is not the complaint. The complaint is distance. The
     registered damp is 0.42, giving orbitAz * 0.42 = +/-2.0 degrees of camera
     travel; that reads as a gentle parallax on a shelf eight units away, but
     an active volume has been pulled to within 60% of frame height of the
     lens by activeZ(), and at that range the same 2 degrees throws it right
     across the frame.

     MEASURED at 1440x900, tracking the volume by the centroid of its edge
     energy -- the room behind it is blurred by the composite, so the only
     sharp edges in frame are the volume's own:

       damp 0.42   260.4px horizontal travel, 163.6px vertical
       damp 0.22   152.9px horizontal travel,  86.2px vertical

     across the full width and height of the window. 41% and 47% less. That
     keeps the room alive under the pointer without the volume sliding about
     while it is being read.

     A deliberate deviation from the registered 0.42, at the author's request
     and for a reason the registered composition does not have: its volumes
     sit closer to the centre of a smaller room. */
  activeOrbitDamp: 0.22,
  activeX: 0.72, activeRot: [0.075, 0.285, 0.0],
  activeDuration: 700, hoverDrop: 400, hoverLift: 1000,
  /* THE INTRO IS A GREETING, NOT A LOADING BAR.

     Retimed 23 Sep 2026. At 78/1000/460 the last of 17 volumes did not START
     arriving until 1000 + 17*78 = 2326ms after the first painted frame, and
     settled at 2786ms -- and the CSS fade on .bk__canvas ran 900ms on top of
     it. Reported as "I refresh and see some other page, then this one loads",
     which is what a two-and-a-half-second staged reveal looks like from the
     reader's chair.

     The shape is kept -- wall first, then volumes left to right -- and only
     the clock changes: the last volume now starts at 450 + 17*26 = 892ms and
     settles at 1192ms. */
  introStagger: 26, introWallFade: 450, introFade: 300,
};

/**
 * How many shelves every case gets.
 *
 * All three cases are the same height, always. A case with two volumes in it
 * is a whole four-shelf bookcase with room in it, not a stub: three cases of
 * different heights read as a broken unit rather than as a library, and the
 * emptiness is honest — it is exactly how much room is left.
 *
 * When any one case outgrows its shelves, ALL THREE gain a shelf together, so
 * the unit stays one rectangle and the eye never has to re-find the datum.
 *
 * @param {number[]} counts volumes in each case
 * @param {object} K
 * @returns {number} shelves per case
 */
export function shelfRows(counts, K = SHELF_LAYOUT) {
  const need = counts.reduce((m, n) => Math.max(m, Math.ceil(n / K.perShelf)), 0);
  return Math.max(K.minRows, need);
}

/**
 * The box the camera has to frame, and its aspect.
 *
 * The page sets the stage to exactly this aspect, so the carcass fills the
 * frame in both directions and no wall is rendered that nobody wanted. It also
 * means the stage grows taller of its own accord when a shelf is added: the
 * volumes stay the size they were instead of shrinking to make room.
 */
export function shelfBox(counts, K = SHELF_LAYOUT) {
  const rows = shelfRows(counts, K);
  const unitW = 3 * (K.perShelf * K.slot) + 4 * K.bayGap;
  const unitH = rows * K.rowH;
  const w = unitW + K.padX, h = unitH + K.padY;
  return { rows, unitW, unitH, w, h, ratio: w / h };
}
