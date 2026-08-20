/*
 * Lightbox for the hero screenshot on the docs home page.
 *
 * The screenshot ships at 1200px but renders at roughly half that inside the
 * hero's column, so the UI in it is hard to read. Clicking enlarges it to its
 * natural size (capped to the viewport).
 *
 * The open/close motion is a FLIP transition: a clone is placed at its final
 * geometry, given the inverse transform that maps it back onto the thumbnail,
 * and then released to identity on the next frame. Only transform and opacity
 * animate, so the whole thing stays on the compositor — the picture appears to
 * grow out of the page rather than being swapped for a bigger one.
 *
 * Scoped to the hero on purpose. Making every screenshot in the docs zoomable
 * is a different job, better served by the mkdocs-glightbox plugin.
 */
(function () {
  // Kept in sync with the transition declared on .hero-zoom / .hero-zoom__img.
  var DURATION = 420;

  // mdi magnify-plus-outline / mdi close, inlined so the hint and the close
  // button do not depend on Material's icon pipeline.
  var ICON_MAGNIFY =
    "M15.5,14L20.5,19L19,20.5L14,15.5V14.71L13.73,14.43C12.59,15.41 11.11,16 " +
    "9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3A6.5,6.5 0 0,1 " +
    "16,9.5C16,11.11 15.41,12.59 14.43,13.73L14.71,14H15.5M9.5,14C12,14 " +
    "14,12 14,9.5C14,7 12,5 9.5,5C7,5 5,7 5,9.5C5,12 7,14 " +
    "9.5,14M12,10H10V12H9V10H7V9H9V7H10V9H12V10Z";
  var ICON_CLOSE =
    "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12," +
    "13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";

  var state = null;

  function icon(path) {
    return (
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '"/></svg>'
    );
  }

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /* Geometry of the enlarged image, in the overlay's content coordinates.
     Never upscales past the natural size — beyond that it only gets blurrier. */
  function targetRect(img, rect) {
    var vw = document.documentElement.clientWidth;
    var vh = document.documentElement.clientHeight;
    var nw = img.naturalWidth || img.offsetWidth;
    var nh = img.naturalHeight || img.offsetHeight;

    var fit = Math.min((vw * 0.92) / nw, (vh * 0.9) / nh, 1);
    // On a portrait phone the hero already spans the full column, so fitting
    // the viewport would enlarge nothing at all. Fall back to the natural size
    // and let the overlay scroll sideways instead — a UI screenshot is worth
    // more at 1:1 than shrunk to fit.
    var scale = nw * fit < rect.width * 1.25 ? Math.min((vh * 0.9) / nh, 1) : fit;

    var w = nw * scale;
    var h = nh * scale;
    var contentWidth = Math.max(w, vw);
    return {
      left: (contentWidth - w) / 2,
      top: (vh - h) / 2,
      width: w,
      height: h,
      scrollLeft: (contentWidth - vw) / 2
    };
  }

  /* Transform that maps the enlarged box back onto `rect`. transform-origin is
     0 0 (see the stylesheet), which keeps this to a translate plus a scale.
     `scrollLeft` converts the target from content to viewport coordinates —
     the two differ once the overlay is wide enough to pan. */
  function invert(rect, target, scrollLeft) {
    return (
      "translate(" +
      (rect.left - (target.left - scrollLeft)) +
      "px, " +
      (rect.top - target.top) +
      "px) scale(" +
      rect.width / target.width +
      ")"
    );
  }

  function open(img) {
    if (state) return;

    var rect = img.getBoundingClientRect();
    var target = targetRect(img, rect);

    var overlay = document.createElement("div");
    overlay.className = "hero-zoom";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", img.alt || "Enlarged screenshot");

    var clone = document.createElement("img");
    clone.className = "hero-zoom__img";
    clone.src = img.currentSrc || img.src;
    clone.alt = "";
    clone.style.left = target.left + "px";
    clone.style.top = target.top + "px";
    clone.style.width = target.width + "px";
    clone.style.height = target.height + "px";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "hero-zoom__close";
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.innerHTML = icon(ICON_CLOSE);
    if (target.scrollLeft > 0) {
      // The image is wider than the screen and pans, so a button pinned to its
      // corner would start off-screen. Pin it to the viewport instead.
      closeBtn.classList.add("hero-zoom__close--fixed");
    } else {
      // Straddling the image's top-right corner: clear of the screenshot's
      // content, and unmistakably attached to it. Content and viewport
      // coordinates coincide here, because nothing scrolls.
      closeBtn.style.left = target.left + target.width - 22 + "px";
      closeBtn.style.top = target.top - 22 + "px";
    }
    closeBtn.addEventListener("click", close);

    overlay.appendChild(clone);
    document.body.appendChild(overlay);
    // Deliberately a sibling of the overlay, not a child: the overlay's
    // backdrop-filter would make it the containing block for position:fixed,
    // and the button would then pan away with the image on narrow screens.
    document.body.appendChild(closeBtn);

    // Centre the pan before the first paint, so an image wider than the
    // viewport opens on its middle rather than its left edge.
    overlay.scrollLeft = target.scrollLeft;
    if (!reducedMotion()) {
      clone.style.transform = invert(rect, target, overlay.scrollLeft);
    }

    state = {
      img: img,
      overlay: overlay,
      clone: clone,
      closeBtn: closeBtn,
      target: target
    };

    // Two frames: the first commits the inverted transform as the starting
    // style, the second changes it so the transition actually runs.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (!state) return;
        overlay.classList.add("is-open");
        closeBtn.classList.add("is-open");
        clone.style.transform = "none";
        img.style.visibility = "hidden";
        // Move focus into the dialog, so Escape and Tab behave as expected and
        // the close button is the first thing a keyboard user lands on.
        closeBtn.focus({ preventScroll: true });
      });
    });

    overlay.addEventListener("click", close);
    document.addEventListener("keydown", onKeydown);
    window.addEventListener("resize", close);
  }

  function close() {
    if (!state) return;
    var current = state;
    state = null;

    document.removeEventListener("keydown", onKeydown);
    window.removeEventListener("resize", close);

    current.overlay.classList.remove("is-open");
    current.closeBtn.classList.remove("is-open");
    // Re-measure both ends: the page may have been scrolled and the overlay
    // panned while it was up, so neither the thumbnail nor the enlarged image
    // is necessarily where it was when we opened.
    current.img.style.visibility = "";
    if (!reducedMotion()) {
      current.clone.style.transform = invert(
        current.img.getBoundingClientRect(),
        current.target,
        current.overlay.scrollLeft
      );
    }

    window.setTimeout(function () {
      [current.overlay, current.closeBtn].forEach(function (el) {
        if (el.parentNode) el.parentNode.removeChild(el);
      });
    }, DURATION);

    current.img.focus({ preventScroll: true });
  }

  function onKeydown(e) {
    if (e.key === "Escape") close();
  }

  function init() {
    var img = document.querySelector(".hero-art img");
    if (!img || img.dataset.zoomInit === "1") return;
    img.dataset.zoomInit = "1";

    img.classList.add("hero-art__zoomable");
    img.setAttribute("role", "button");
    img.setAttribute("tabindex", "0");
    img.setAttribute("aria-label", "Enlarge screenshot");

    // Hover affordance: a magnifier over a soft scrim, revealed on hover and on
    // keyboard focus. Built here rather than in index.md so it only ever shows
    // up when the click handler behind it is actually attached.
    var art = img.parentNode;
    art.classList.add("hero-art--zoomable");
    art.insertAdjacentHTML(
      "beforeend",
      '<span class="hero-art__hint" aria-hidden="true">' +
        '<span class="hero-art__hint-chip">' +
        icon(ICON_MAGNIFY) +
        "</span></span>"
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

  // Material re-emits document$ on instant navigation; fall back to the
  // plain ready event when instant loading is off.
  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(init);
  } else if (document.readyState !== "loading") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
