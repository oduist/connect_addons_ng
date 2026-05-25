import { LitElement, html, css } from "lit";

function fmt(seconds) {
    if (seconds == null || seconds <= 0) return "—";
    let s = seconds;
    const h = Math.floor(s / 3600); s -= h * 3600;
    const m = Math.floor(s / 60); s -= m * 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

class ActiveBans extends LitElement {
    static styles = css`
        :host { display: block; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-weight: 500; font-size: 12px; }
        button {
            background: transparent;
            color: #38bdf8;
            border: 1px solid #38bdf8;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
            cursor: pointer;
        }
        button:hover { background: rgba(56, 189, 248, 0.1); }
        .empty { color: #94a3b8; padding: 12px; font-size: 13px; }
    `;

    static properties = { items: { state: true } };

    constructor() {
        super();
        this.items = [];
        this._timer = null;
        this._sse = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._refresh();
        this._timer = setInterval(() => this._tick(), 1000);
        this._sse = new EventSource("/firewall/events");
        this._sse.addEventListener("auto_ban", () => this._refresh());
        this._sse.addEventListener("unban", () => this._refresh());
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearInterval(this._timer);
        if (this._sse) this._sse.close();
    }

    async _refresh() {
        try {
            const r = await fetch("/firewall/api/bans");
            this.items = await r.json();
        } catch (_) { /* keep last data */ }
    }

    _tick() {
        // Re-render so the countdown updates without re-fetching.
        this.items = this.items.map(e =>
            e.timeout != null ? { ...e, timeout: Math.max(0, e.timeout - 1) } : e
        );
    }

    async _unban(ip) {
        await fetch(`/firewall/api/bans/${encodeURIComponent(ip)}`, { method: "DELETE" });
        this._refresh();
    }

    render() {
        if (!this.items.length) {
            return html`<div class="empty">No active auto-bans.</div>`;
        }
        return html`
            <table>
                <thead>
                    <tr><th>IP</th><th>TTL</th><th>Comment</th><th></th></tr>
                </thead>
                <tbody>
                    ${this.items.map(item => html`
                        <tr>
                            <td>${item.entry}</td>
                            <td>${fmt(item.timeout)}</td>
                            <td>${item.comment || ""}</td>
                            <td><button @click=${() => this._unban(item.entry)}>Unban</button></td>
                        </tr>
                    `)}
                </tbody>
            </table>
        `;
    }
}

customElements.define("active-bans", ActiveBans);
