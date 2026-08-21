// Theme entry point. Every behaviour lives in its own module under js/; this
// file only wires them up on DOM ready.
import { initScheme } from "./js/scheme.js";
import { initToc } from "./js/toc.js";
import { initDrawer } from "./js/drawer.js";
import { initCopyButtons, wrapTables } from "./js/copy.js";
import { initSearch, highlightQuery } from "./js/search.js";

initScheme();
initToc();
initDrawer();
wrapTables();
initCopyButtons();
initSearch();
highlightQuery();
