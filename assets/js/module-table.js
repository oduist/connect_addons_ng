/*
 * "The module system" block: hover tooltips on the module tiles and a legend
 * that isolates one or more categories.
 *
 * Part of the home page kit — the markup lives in a site's own index.md and the
 * class names are this theme's public surface (see README.md). A page without
 * a .mod-grid gets nothing; the initializer returns immediately.
 *
 * Ported from the Oduist Connect marketing site (src/pages/index.astro).
 */
export function initModuleTable() {
    var grid = document.querySelector(".mod-grid");
    if (!grid || grid.dataset.modInit === "1") return;
    grid.dataset.modInit = "1";

    var tiles = Array.prototype.slice.call(
      document.querySelectorAll(".mod-tile")
    );
    var legs = Array.prototype.slice.call(
      document.querySelectorAll(".mod-leg")
    );
    var tip = document.getElementById("mod-tip");

    // Tooltip: follows the cursor, clamped to the viewport. Skipped only on
    // touch (coarse) pointers, which tap straight through to the module's
    // docs — environments that report no pointer at all still get it.
    var coarse = window.matchMedia("(pointer: coarse)").matches;
    if (tip && !coarse) {
      tiles.forEach(function (t) {
        t.addEventListener("mousemove", function (e) {
          tip.innerHTML =
            '<div class="tt">' +
            t.dataset.code +
            " &middot; " +
            t.dataset.label +
            '</div><div class="tb">' +
            t.dataset.tip +
            "</div>";
          tip.style.opacity = "1";
          var w = tip.offsetWidth;
          var h = tip.offsetHeight;
          tip.style.left =
            Math.min(e.clientX + 14, window.innerWidth - w - 8) + "px";
          tip.style.top = Math.max(8, e.clientY - h - 12) + "px";
        });
        t.addEventListener("mouseleave", function () {
          tip.style.opacity = "0";
        });
      });
    }

    // Legend: first click isolates a category; further clicks toggle
    // categories in/out. Emptying the selection restores all.
    var cats = legs.map(function (l) {
      return l.dataset.cat;
    });
    var active = {};
    cats.forEach(function (c) {
      active[c] = true;
    });

    function count() {
      return Object.keys(active).length;
    }
    function sync() {
      var all = count() === cats.length;
      legs.forEach(function (l) {
        l.classList.toggle("off", !all && !active[l.dataset.cat]);
      });
      tiles.forEach(function (t) {
        t.classList.toggle("dim", !all && !active[t.dataset.cat]);
      });
    }

    legs.forEach(function (l) {
      l.addEventListener("click", function () {
        var key = l.dataset.cat;
        if (count() === cats.length) {
          active = {};
          active[key] = true;
        } else if (active[key]) {
          delete active[key];
        } else {
          active[key] = true;
        }
        if (count() === 0) {
          cats.forEach(function (c) {
            active[c] = true;
          });
        }
        sync();
      });
    });
  }
