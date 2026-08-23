// Click any content image to see it at full size.
//
// The enlarged view is a native modal <dialog>: Escape, the focus trap, making
// the rest of the page inert and the backdrop itself all come from showModal().
// The only behaviour written here is closing on a backdrop click — a click that
// lands on the dialog box rather than on anything inside it.
//
// Screenshots are the reason this exists. Documentation is full of pictures of
// interfaces that render at half their natural size in a content column, where
// the text inside them is unreadable.

// mdi close and magnify-plus-outline, inlined so the theme depends on no icon
// pipeline.
const ICON_CLOSE =
  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12," +
  "13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";
const ICON_MAGNIFY =
  "M15.5,14L20.5,19L19,20.5L14,15.5V14.71L13.73,14.43C12.59,15.41 11.11,16 " +
  "9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3A6.5,6.5 0 0,1 " +
  "16,9.5C16,11.11 15.41,12.59 14.43,13.73L14.71,14H15.5M9.5,14C12,14 " +
  "14,12 14,9.5C14,7 12,5 9.5,5C7,5 5,7 5,9.5C5,12 7,14 " +
  "9.5,14M12,10H10V12H9V10H7V9H9V7H10V9H12V10Z";

// Below this an image is decoration — an icon, a badge, a shield — and blowing
// it up serves nobody.
const MIN_WIDTH = 200;

let dialog = null;
let trigger = null;
let openedByPointer = false;

function icon(path) {
  return (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '"/></svg>'
  );
}

function build() {
  const el = document.createElement("dialog");
  el.className = "docs-zoom";
  el.innerHTML =
    '<img class="docs-zoom__img" alt="" draggable="false">' +
    '<button class="docs-zoom__close" type="button" aria-label="Close">' +
    icon(ICON_CLOSE) +
    "</button>";

  el.querySelector(".docs-zoom__close").addEventListener("click", () =>
    el.close(),
  );

  // A click on the backdrop is reported against the dialog element itself;
  // anything inside the picture or the button targets those instead.
  el.addEventListener("click", (e) => {
    if (e.target === el) el.close();
  });

  // Closing a modal returns focus to whatever opened it, and the browser then
  // treats that element as keyboard-focused — leaving the hover hint painted
  // over the thumbnail with the pointer nowhere near it. Drop focus again, but
  // only when the pointer opened the dialog: a reader who got here with Enter
  // needs the focus back where they left it.
  el.addEventListener("close", () => {
    if (openedByPointer && trigger) trigger.blur();
  });

  document.body.appendChild(el);
  return el;
}

function open(img, fromPointer) {
  trigger = img;
  openedByPointer = !!fromPointer;
  if (!dialog) dialog = build();

  const full = dialog.querySelector(".docs-zoom__img");
  full.src = img.currentSrc || img.src;
  full.alt = img.alt || "";
  dialog.showModal();
}

// The hint is a sibling of the image, not a wrapper around it: the image keeps
// its place in the flow, and CSS can reveal the hint on hover or on the
// image's own keyboard focus.
function attach(img) {
  const frame = document.createElement("span");
  frame.className = "docs-zoomable";
  img.parentNode.insertBefore(frame, img);
  frame.appendChild(img);
  frame.insertAdjacentHTML(
    "beforeend",
    '<span class="docs-zoomable__hint" aria-hidden="true">' +
      '<span class="docs-zoomable__glyph">' +
      icon(ICON_MAGNIFY) +
      "</span></span>",
  );

  img.classList.add("docs-zoomable__img");
  img.draggable = false;
  img.setAttribute("role", "button");
  img.setAttribute("tabindex", "0");
  img.setAttribute("aria-label", "Enlarge image");

  // detail is 0 for a click synthesised from Enter or Space and non-zero for a
  // real pointer click, which is how the close handler knows whether returning
  // focus here helps or just leaves the hint stuck on screen.
  img.addEventListener("click", (e) => open(img, e.detail > 0));
  img.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open(img, false);
    }
  });
}

function eligible(img) {
  if (img.closest("a")) return false; // already has a job when clicked
  if (img.closest(".docs-zoomable")) return false; // done already
  if (img.hasAttribute("data-no-zoom")) return false; // opted out by the author
  const width = img.naturalWidth || img.width;
  return !width || width >= MIN_WIDTH;
}

export function initImageZoom() {
  const main = document.getElementById("docs-main");
  if (!main) return;

  for (const img of main.querySelectorAll("img")) {
    // naturalWidth is 0 until the image loads, so an image that has not
    // arrived yet is measured once it does rather than guessed at now.
    if (img.complete) {
      if (eligible(img)) attach(img);
    } else {
      img.addEventListener(
        "load",
        () => {
          if (eligible(img)) attach(img);
        },
        { once: true },
      );
    }
  }
}
