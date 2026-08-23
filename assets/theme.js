// Theme entry point. Every behaviour lives in its own module under js/; this
// file only wires them up on DOM ready.
import { initScheme } from "./js/scheme.js";
import { initImageZoom } from "./js/image-zoom.js";
import { initModuleTable } from "./js/module-table.js";
import { initToc } from "./js/toc.js";
import { initDrawer } from "./js/drawer.js";
import { initCopyButtons, wrapTables } from "./js/copy.js";
import { initSearch, highlightQuery } from "./js/search.js";

// Each initializer is independent (different DOM regions, no shared state),
// so one throwing must not skip the rest — an uncaught error from, say,
// initToc() used to abort initDrawer()/initSearch()/highlightQuery() too,
// since they were bare top-level calls in one synchronous run.
for (const init of [
  initScheme,
  initToc,
  initDrawer,
  wrapTables,
  initCopyButtons,
  initSearch,
  highlightQuery,
  initImageZoom,
  initModuleTable,
]) {
  try {
    init();
  } catch (error) {
    console.error(`docs theme: ${init.name} failed`, error);
  }
}
