// Highlights the table-of-contents entry for the heading currently on screen.
export function initToc() {
  const links = [...document.querySelectorAll(".docs-toc__link")];
  if (!links.length) return;

  const byId = new Map();
  for (const link of links) {
    const id = decodeURIComponent(link.hash.slice(1));
    const heading = id && document.getElementById(id);
    if (heading) byId.set(heading, link);
  }

  let active = null;
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const link = byId.get(entry.target);
        if (!link || link === active) continue;
        active?.removeAttribute("aria-current");
        link.setAttribute("aria-current", "true");
        active = link;
      }
    },
    // Only the band just below the sticky header counts as "current".
    // rootMargin only accepts px/percent (not rem) — 7rem == 112px at the
    // root 16px font-size; a rem value here throws in the IntersectionObserver
    // constructor and silently aborts every initializer queued after this one.
    { rootMargin: "-112px 0px -70% 0px" },
  );

  for (const heading of byId.keys()) observer.observe(heading);
}
