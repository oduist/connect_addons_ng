import { LitElement, html, css } from "lit";

class WhitelistView extends LitElement {
    static styles = css`
        :host { display: block; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-weight: 500; font-size: 12px; }
        .empty { color: #94a3b8; padding: 12px; font-size: 13px; }
        .hint { color: #94a3b8; font-size: 12px; margin-top: 6px; }
    `;

    static properties = { items: { state: true } };

    constructor() {
        super();
        this.items = [];
        this._timer = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._refresh();
        this._timer = setInterval(() => this._refresh(), 30000);
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearInterval(this._timer);
    }

    async _refresh() {
        try {
            const r = await fetch("/firewall/api/whitelist");
            this.items = await r.json();
        } catch (_) { /* ignore */ }
    }

    render() {
        if (!this.items.length) {
            return html`<div class="empty">Whitelist is empty.</div>
                       <div class="hint">Manage in Odoo → PBX → Firewall → Whitelist.</div>`;
        }
        return html`
            <table>
                <thead><tr><th>IP / CIDR</th><th>Comment</th></tr></thead>
                <tbody>
                    ${this.items.map(item => html`
                        <tr><td>${item.entry}</td><td>${item.comment || ""}</td></tr>
                    `)}
                </tbody>
            </table>
            <div class="hint">Manage in Odoo → PBX → Firewall → Whitelist.</div>
        `;
    }
}

customElements.define("whitelist-view", WhitelistView);
