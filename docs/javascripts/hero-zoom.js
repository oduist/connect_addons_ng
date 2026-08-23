/*
 * Lightbox for the hero screenshot on the docs home page.
 *
 * The screenshot ships at 1200px but renders at roughly half that inside the
 * hero's column, so the UI in it is hard to read. Clicking opens it in a native
 * modal <dialog>.
 *
 * The element does the work: Esc, the focus trap, making the rest of the page
 * inert and the backdrop itself all come from showModal(). The only behaviour
 * written here is closing on a backdrop click — a click that lands on the
 * dialog box rather than on anything inside it.
 *
 * Scoped to the hero on purpose. Making every screenshot in the docs zoomable
 * is a different job, better served by the mkdocs-glightbox plugin.
 */
(function () {
  // mdi close, inlined so the close button does not depend on an icon
  // pipeline. The hover hint carries a word, not a glyph.
  var ICON_CLOSE =
    "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12," +
    "13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";

  var dialog = null;

  function build(img) {
    var el = document.createElement("dialog");
    el.className = "hero-zoom";

    var full = document.createElement("img");
    full.className = "hero-zoom__img";
    full.src = img.currentSrc || img.src;
    full.alt = img.alt || "";

    var close = document.createElement("button");
    close.className = "hero-zoom__close";
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    close.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' +
      ICON_CLOSE +
      '"/></svg>';
    close.addEventListener("click", function () {
      el.close();
    });

    // A click on the backdrop is reported against the dialog element itself;
    // anything inside the picture or the button targets those instead.
    el.addEventListener("click", function (e) {
      if (e.target === el) el.close();
    });

    el.appendChild(full);
    el.appendChild(close);
    document.body.appendChild(el);
    return el;
  }

  function open(img) {
    if (!dialog) dialog = build(img);
    dialog.showModal();
  }

  function init() {
    var img = document.querySelector(".hero-art img");
    if (!img || img.dataset.zoomInit === "1") return;
    img.dataset.zoomInit = "1";

    img.classList.add("hero-art__zoomable");
    img.setAttribute("role", "button");
    img.setAttribute("tabindex", "0");
    img.setAttribute("aria-label", "Enlarge screenshot");

    // Hover affordance: crop marks closing in on the picture's corners and a
    // label in its bottom-right, revealed on hover and on keyboard focus. Built
    // here rather than in index.md so it only ever shows up when the click
    // handler behind it is actually attached.
    var art = img.parentNode;
    art.classList.add("hero-art--zoomable");
    art.insertAdjacentHTML(
      "beforeend",
      '<span class="hero-art__hint" aria-hidden="true">' +
        '<span class="hero-art__hint-chip">Enlarge</span></span>'
    );

    img.addEventListener("click", function () {
      open(img);
    });
    img.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open(img);
      }
    });
  }

  if (document.readyState !== "loading") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
