// Mobile navigation. The sidebar exists once in the page; on narrow screens it
// is moved into a <dialog>, which gives focus trapping and Esc for free.
export function initDrawer() {
  const dialog = document.querySelector("[data-drawer]");
  const body = dialog?.querySelector("[data-drawer-body]");
  const nav = document.querySelector(".docs-nav");
  const openButton = document.querySelector("[data-drawer-open]");
  if (!dialog || !body || !nav || !openButton) return;

  openButton.addEventListener("click", () => {
    body.append(nav);
    dialog.showModal();
  });

  dialog.querySelector("[data-drawer-close]")?.addEventListener("click", () => {
    dialog.close();
  });

  // Put the sidebar back where the layout expects it once the drawer closes.
  dialog.addEventListener("close", () => {
    document.querySelector(".docs-shell")?.prepend(nav);
  });
}
