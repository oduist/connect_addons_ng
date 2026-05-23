import { LitElement, html, css } from "lit";

const COLORS = {
    auto_ban:     "#f87171",
    auth_success: "#4ade80",
    challenge:    "#facc15",
    unban:        "#38bdf8",
    manual_unban_applied: "#38bdf8",
    manual_ban_applied:   "#f87171",
};

function ts(t) {
    const d = new Date((typeof t === "number" ? t : parseFloat(t)) * 1000);
    if (Number.isNaN(d.getTime())) return "";
    return d.toTimeString().slice(0, 8);
}

class EventStream extends LitElement {
    static styles = css`
        :host { display: block; }
        .empty { color: #94a3b8; padding: 12px; font-size: 13px; }
        ul {
            list-style: none;
            margin: 0;
            padding: 0;
            max-height: 320px;
            overflow-y: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 12px;
        }
        li {
            padding: 4px 10px;
            border-bottom: 1px solid #334155;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .ts { color: #94a3b8; margin-right: 8px; }
        .type { display: inline-block; min-width: 110px; font-weight: 600; }
    `;

    static properties = { events: { state: true } };

    constructor() {
        super();
        this.events = [];
        this._sse = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._sse = new EventSource("/firewall/events");
        // We don't know the event names in advance — listen to anything via the default channel.
        this._sse.onmessage = e => this._push(e.data);
        ["auto_ban", "auth_success", "challenge", "unban",
         "manual_ban_applied", "manual_unban_applied"].forEach(name =>
            this._sse.addEventListener(name, e => this._push(e.data, name))
        );
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        if (this._sse) this._sse.close();
    }

    _push(raw, name) {
        let payload = {};
        try { payload = JSON.parse(raw); } catch (_) { payload = { raw }; }
        if (name && !payload.type) payload.type = name;
        this.events = [payload, ...this.events].slice(0, 200);
    }

    render() {
        if (!this.events.length) {
            return html`<div class="empty">Waiting for events…</div>`;
        }
        return html`
            <ul>
                ${this.events.map(e => html`
                    <li>
                        <span class="ts">${ts(e.ts)}</span>
                        <span class="type" style="color:${COLORS[e.type] || "#e2e8f0"}">
                            ${e.type || "?"}
                        </span>
                        ${e.ip || ""}
                        ${e.account_id ? html`user=${e.account_id}` : ""}
                        ${e.user_agent ? html`ua=${e.user_agent}` : ""}
                    </li>
                `)}
            </ul>
        `;
    }
}

customElements.define("event-stream", EventStream);
