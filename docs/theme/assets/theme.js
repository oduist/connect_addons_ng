// Theme entry point. Every behaviour lives in its own module under js/; this
// file only wires them up on DOM ready.
import { initScheme } from "./js/scheme.js";
import { initToc } from "./js/toc.js";
import { initDrawer } from "./js/drawer.js";

initScheme();
initToc();
initDrawer();
