// Two content fix-ups Material used to do for us.
export function initCopyButtons() {
  for (const block of document.querySelectorAll(".highlight")) {
    const code = block.querySelector("code");
    if (!code) continue;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "docs-copy";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.innerText);
        button.textContent = "Copied";
      } catch (error) {
        // Denied clipboard permission or a non-secure context both reject
        // here; without the catch the button was left stuck on "Copy" with
        // no feedback at all.
        button.textContent = "Copy failed";
      }
      setTimeout(() => (button.textContent = "Copy"), 1500);
    });
    block.append(button);
  }
}

export function wrapTables() {
  for (const table of document.querySelectorAll(".prose table")) {
    if (table.parentElement?.classList.contains("docs-table-wrap")) continue;
    const wrap = document.createElement("div");
    wrap.className = "docs-table-wrap";
    table.replaceWith(wrap);
    wrap.append(table);
  }
}
