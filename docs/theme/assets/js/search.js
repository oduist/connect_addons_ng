// Site search over the index the MkDocs `search` plugin emits at
// search/search_index.json. Engine: lunr 2.3.9, vendored in assets/vendor/.
//
// The plugin writes one record per page AND one per section with its anchor,
// so results land on the right heading. The index is ~500 KB raw, so it is
// fetched on first use, never on page load.
let indexPromise = null;

async function loadIndex(base) {
  const response = await fetch(`${base}search/search_index.json`);
  const payload = await response.json();
  const documents = new Map();

  const index = lunr(function () {
    this.ref("location");
    this.field("title", { boost: 10 });
    this.field("text");
    for (const doc of payload.docs) {
      documents.set(doc.location, doc);
      this.add(doc);
    }
  });

  return { index, documents };
}

function moduleOf(location) {
  const [first] = location.split("/");
  return first && !first.includes(".") ? first : "Home";
}

function snippet(text, terms) {
  const lowered = text.toLowerCase();
  const at = terms
    .map((term) => lowered.indexOf(term.toLowerCase()))
    .filter((position) => position >= 0)
    .sort((a, b) => a - b)[0];
  const start = Math.max(0, (at ?? 0) - 60);
  const raw = text.slice(start, start + 200);
  const escaped = raw.replace(/[&<>]/g, (c) => `&#${c.charCodeAt(0)};`);
  return terms.reduce(
    (acc, term) =>
      acc.replace(new RegExp(`(${term})`, "gi"), "<mark>$1</mark>"),
    escaped,
  );
}

export function initSearch() {
  const dialog = document.querySelector("[data-search]");
  const input = dialog?.querySelector("[data-search-input]");
  const output = dialog?.querySelector("[data-search-results]");
  const opener = document.querySelector("[data-search-open]");
  if (!dialog || !input || !output || !opener) return;

  const base = document.documentElement.dataset.base || "";

  const open = () => {
    dialog.showModal();
    input.focus();
    if (!indexPromise) {
      output.innerHTML = "<li class='docs-search__status'>Indexing…</li>";
      indexPromise = loadIndex(base);
    }
  };

  opener.addEventListener("click", open);
  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(event.target.tagName);
    if (typing) return;
    if (event.key === "/" || (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey))) {
      event.preventDefault();
      open();
    }
  });

  // A click that lands on the <dialog> element itself (not on any of its
  // children) is a click on the backdrop — native <dialog> only wires up
  // Esc, so close on backdrop click too. Clicks on the form/results inside
  // always target a descendant, never the dialog itself.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    if (query.length < 2) {
      output.innerHTML = "";
      return;
    }
    const { index, documents } = await indexPromise;
    const terms = query.split(/\s+/);
    const hits = index.query((q) => {
      for (const term of terms) {
        q.term(term, { boost: 2 });
        q.term(term, { wildcard: lunr.Query.wildcard.TRAILING });
      }
    });

    output.innerHTML =
      hits
        .slice(0, 20)
        .map((hit) => {
          const doc = documents.get(hit.ref);
          // doc.location carries a trailing #anchor for section-level hits
          // (one record per heading — see the module comment above). A
          // fragment absorbs everything after it, including a literal "?",
          // so ?h=<query> must be inserted before the anchor or the query
          // string never reaches the destination page and highlightQuery()
          // finds nothing.
          const [path, anchor] = doc.location.split("#");
          const href = `${base}${path}?h=${encodeURIComponent(query)}${anchor ? `#${anchor}` : ""}`;
          return `<li class="docs-search__hit">
            <a href="${href}">
              <span class="docs-search__module">${moduleOf(doc.location)}</span>
              <span class="docs-search__title">${doc.title}</span>
              <span class="docs-search__text">${snippet(doc.text, terms)}</span>
            </a>
          </li>`;
        })
        .join("") || "<li class='docs-search__status'>No results</li>";
  });

  // Keyboard navigation across the result list.
  input.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown") return;
    event.preventDefault();
    output.querySelector("a")?.focus();
  });
}

// Highlights the terms carried over from the search dialog (?h=...).
export function highlightQuery() {
  const query = new URLSearchParams(location.search).get("h");
  const main = document.getElementById("docs-main");
  if (!query || !main || !window.CSS?.highlights) return;

  const ranges = [];
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  const needles = query.toLowerCase().split(/\s+/).filter(Boolean);

  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent.toLowerCase();
    for (const needle of needles) {
      let from = text.indexOf(needle);
      while (from >= 0) {
        const range = new Range();
        range.setStart(node, from);
        range.setEnd(node, from + needle.length);
        ranges.push(range);
        from = text.indexOf(needle, from + needle.length);
      }
    }
  }

  CSS.highlights.set("search", new Highlight(...ranges));
}
