/* statement.js -- the accessibility statement (INCLUSIVE_DESIGN.md I4).

   The statement itself is written into ui/accessibility.html and reads in full
   without JavaScript. This module only mounts the chrome every page shares --
   the masthead with its display and Reduce motion controls -- and the page's
   voice, so a reader can change the display from here as from anywhere. */

import "../styles/tokens.css";
import "../styles/chassis.css";
import "../styles/statement.css";

import { mountAll } from "../lib/chrome.js";
import { mountAnnouncer } from "../lib/announce.js";

mountAnnouncer();
mountAll({ here: "/accessibility" });
