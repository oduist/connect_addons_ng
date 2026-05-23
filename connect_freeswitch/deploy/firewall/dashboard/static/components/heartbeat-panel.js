import { LitElement, html, css } from "lit";

class HeartbeatPanel extends LitElement {
    static styles = css`
        :host { display: flex; gap: 12px; align-items: center; font-size: 13px; }
        .pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .ok   { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
        .warn { background: rgba(250, 204, 21, 0.15); color: #facc15; }
        .bad  { background: rgba(248, 113, 113, 0.15); color: #f87171; }
        .muted { color: #94a3b8; }
    `;

    static properties = {
        data: { state: true },
        connected: { state: true },
    };

    constructor() {
        super();
        this.data = null;
        this.connected = false;
        this._timer = null;
    }

    connectedCallback() {
        super.connectedCallback();
        this._refresh();
        this._timer = setInterval(() => this._refresh(), 5000);
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        clearInterval(this._timer);
    }

    async _refresh() {
        try {
            const r = await fetch("/firewall/api/heartbeat");
            this.data = await r.json();
            this.connected = true;
        } catch (_) {
            this.connected = false;
        }
    }

    _eslPill() {
        if (!this.data) return html`<span class="pill warn">…</span>`;
        return this.data.esl_connected
            ? html`<span class="pill ok">ESL up</span>`
            : html`<span class="pill bad">ESL down</span>`;
    }

    _odooPill() {
        if (!this.data) return html`<span class="pill warn">…</span>`;
        return this.data.odoo_connected
            ? html`<span class="pill ok">Odoo</span>`
            : html`<span class="pill bad">Odoo</span>`;
    }

    _uptime() {
        if (!this.data || !this.data.uptime_seconds) return "—";
        let s = this.data.uptime_seconds;
        const h = Math.floor(s / 3600); s -= h * 3600;
        const m = Math.floor(s / 60); s -= m * 60;
        return `${h}h ${m}m ${s}s`;
    }

    render() {
        return html`
            ${this._eslPill()}
            ${this._odooPill()}
            <span class="muted">uptime ${this._uptime()}</span>
        `;
    }
}

customElements.define("heartbeat-panel", HeartbeatPanel);
