import { LitElement, html, css } from "lit";

class TopIps extends LitElement {
    static styles = css`
        :host { display: block; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-weight: 500; font-size: 12px; }
        .empty { color: #94a3b8; padding: 12px; font-size: 13px; }
        td.count { text-align: right; font-variant-numeric: tabular-nums; }
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
            const r = await fetch("/firewall/api/top-ips");
            this.items = await r.json();
        } catch (_) { /* ignore */ }
    }

    render() {
        if (!this.items.length) {
            return html`<div class="empty">No traffic recorded yet.</div>`;
        }
        return html`
            <table>
                <thead><tr><th>IP</th><th class="count">events / 24h</th></tr></thead>
                <tbody>
                    ${this.items.map(item => html`
                        <tr><td>${item.ip}</td><td class="count">${item.count}</td></tr>
                    `)}
                </tbody>
            </table>
        `;
    }
}

customElements.define("top-ips", TopIps);
