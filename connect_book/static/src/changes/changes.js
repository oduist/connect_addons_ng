/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Component, useState, onWillStart, useRef, markup } from "@odoo/owl";

/**
 * The "Changelog" client action.
 * On the left -- the contents, one line per release; on the right -- the
 * changelog itself. It is one document rather than a page per release, so
 * reading straight down works and the contents are for jumping, not paging.
 */
export class ChangelogApp extends Component {
    static template = "connect_book.ChangelogApp";
    static props = { "*": true };

    setup() {
        this.state = useState({
            html: "",
            sections: [],
            activeId: null,
            loaded: false,
        });
        this.content = useRef("content");

        onWillStart(async () => {
            const data = await rpc("/connect_book/changes");
            this.state.html = data.html || "";
            this.state.sections = data.sections || [];
            this.state.loaded = true;
        });
    }

    get body() {
        return markup(this.state.html);
    }

    /**
     * Scroll a release into view. The ids come from the server, which read
     * them back off the rendered headings, so the target is always there --
     * but guard anyway rather than throw inside a click handler.
     */
    jumpTo(id) {
        this.state.activeId = id;
        const root = this.content.el;
        if (!root) {
            return;
        }
        const heading = root.querySelector(`[id="${CSS.escape(id)}"]`);
        if (heading) {
            heading.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }
}

registry.category("actions").add("connect_book.changes", ChangelogApp);
