// Colour-scheme toggle. The attribute is written twice: once by the inline
// snippet in base.html (before first paint, so the page never flashes the
// wrong palette) and again here, when the reader clicks the toggle.
const KEY = "docs-scheme";

export function initScheme() {
  const button = document.querySelector("[data-scheme-toggle]");
  if (!button) return;

  button.addEventListener("click", () => {
    const next =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(KEY, next);
    button.setAttribute("aria-pressed", String(next === "dark"));
  });
}
