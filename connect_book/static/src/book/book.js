/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, markup } from "@odoo/owl";

/**
 * The "Book" client action: a two-pane documentation viewer.
 * On the left -- a searchable list of the installed Connect modules, each with
 * its own pages; on the right -- the page you selected.
 */
export class BookApp extends Component {
    static template = "connect_book.BookApp";
    static props = { "*": true };
    //: JSON endpoint the book pulls its pages from. Subclasses override it
    //  (e.g. the Admin Guide reads /connect_book/admin) -- everything else is shared.
    static endpoint = "/connect_book/book";

    setup() {
        this.state = useState({
            modules: [],
            activeId: null,
            search: "",
            loaded: false,
        });

        onWillStart(async () => {
            const data = await rpc(this.constructor.endpoint);
            this.state.modules = data.modules || [];
            this.state.loaded = true;
            const first = this.state.modules[0];
            if (first && first.pages.length) {
                this.state.activeId = first.pages[0].id;
            }
        });
    }

    /**
     * The module list narrowed down by the search box. A module whose own name
     * matches keeps all of its pages; otherwise only its matching pages stay,
     * and a module left with none drops out of the list.
     */
    get filteredModules() {
        const query = this.state.search.trim().toLowerCase();
        if (!query) {
            return this.state.modules;
        }
        const matches = [];
        for (const mod of this.state.modules) {
            if (mod.title.toLowerCase().includes(query)) {
                matches.push(mod);
                continue;
            }
            const pages = mod.pages.filter((page) =>
                page.title.toLowerCase().includes(query)
            );
            if (pages.length) {
                matches.push({ ...mod, pages });
            }
        }
        return matches;
    }

    get activePage() {
        for (const mod of this.state.modules) {
            const page = mod.pages.find((p) => p.id === this.state.activeId);
            if (page) {
                return { ...page, body: markup(page.html) };
            }
        }
        return null;
    }

    /**
     * Open a page by id, ignoring an id this book does not hold.
     *
     * A cross-reference can point at a page that is not in this book -- an
     * administrator page reached from the User Guide, or a page belonging to a
     * module that is not installed here. Blanking the content pane would be a
     * worse answer than staying put, so an unknown id is a no-op.
     */
    selectPage(id) {
        const known = this.state.modules.some((mod) =>
            mod.pages.some((page) => page.id === id)
        );
        if (known) {
            this.state.activeId = id;
        }
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
    }

    /**
     * Follow a cross-reference between two documentation pages.
     *
     * The Markdown cross-links pages by file name; the server rewrites those
     * into `data-book-page="<module>/<path>"` (see
     * `connect.book._rewrite_internal_links`) because a bare `.md` href means
     * nothing inside Odoo. Anything else in the page -- external links
     * included -- is left to the browser.
     */
    onContentClick(ev) {
        const anchor = ev.target.closest("[data-book-page]");
        if (!anchor) {
            return;
        }
        ev.preventDefault();
        this.selectPage(anchor.dataset.bookPage);
    }
}

registry.category("actions").add("connect_book.book", BookApp);
