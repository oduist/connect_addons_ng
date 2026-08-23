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
  // mdi magnify-plus-outline / mdi close, inlined so the hover hint and the
  // close button do not depend on an icon pipeline.
  var ICON_MAGNIFY =
    "M15.5,14L20.5,19L19,20.5L14,15.5V14.71L13.73,14.43C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.43,13.73L14.71,14H15.5M9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14M12,10H10V12H9V10H7V9H9V7H10V9H12V10Z";
  var ICON_CLOSE =
    "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12," +
    "13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";

  var dialog = null;
  var trigger = null;
  var openedByPointer = false;

  function build(img) {
    var el = document.createElement("dialog");
    el.className = "hero-zoom";

    var full = document.createElement("img");
    full.className = "hero-zoom__img";
    full.src = img.currentSrc || img.src;
    full.alt = img.alt || "";
    // Pressing and moving on an image starts the browser's own drag-and-drop
    // and a ghost thumbnail follows the cursor. Nothing here accepts a drop,
    // so the gesture only gets in the way of reading the picture.
    full.draggable = false;

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

    // Closing a modal returns focus to whatever opened it, and the browser
    // then treats that element as keyboard-focused — so the hover hint stayed
    // painted over the thumbnail with the pointer nowhere near it. Drop focus
    // again, but only when the pointer opened the dialog: a reader who got
    // here with Enter needs the focus back where they left it.
    el.addEventListener("close", function () {
      if (openedByPointer && trigger) trigger.blur();
    });

    el.appendChild(full);
    el.appendChild(close);
    document.body.appendChild(el);
    return el;
  }

  function open(img, fromPointer) {
    trigger = img;
    openedByPointer = !!fromPointer;
    if (!dialog) dialog = build(img);
    dialog.showModal();
  }

  function init() {
    var img = document.querySelector(".hero-art img");
    if (!img || img.dataset.zoomInit === "1") return;
    img.dataset.zoomInit = "1";

    img.classList.add("hero-art__zoomable");
    img.draggable = false;
    img.setAttribute("role", "button");
    img.setAttribute("tabindex", "0");
    img.setAttribute("aria-label", "Enlarge screenshot");

    // Hover affordance: crop marks closing in on the picture's corners, a
    // scrim and a magnifier, revealed on hover and on keyboard focus. Built
    // here rather than in index.md so it only ever shows up when the click
    // handler behind it is actually attached.
    var art = img.parentNode;
    art.classList.add("hero-art--zoomable");
    art.insertAdjacentHTML(
      "beforeend",
      '<span class="hero-art__hint" aria-hidden="true">' +
        '<span class="hero-art__hint-chip">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' +
        ICON_MAGNIFY +
        '"/></svg></span></span>'
    );

    // detail is 0 for a click synthesised from Enter or Space, and non-zero
    // for a real pointer click — which is how the close handler above knows
    // whether returning focus here would be helpful or would just leave the
    // hint stuck on screen.
    img.addEventListener("click", function (e) {
      open(img, e.detail > 0);
    });
    img.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open(img, false);
      }
    });
  }

  if (document.readyState !== "loading") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
