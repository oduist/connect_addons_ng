import { LitElement, html, css } from "lit";

class AttemptsSparkline extends LitElement {
    static styles = css`
        :host { display: block; }
        svg { width: 100%; height: 80px; display: block; }
        .total { font-size: 12px; color: #94a3b8; margin-top: 4px; }
    `;

    static properties = { buckets: { state: true } };

    constructor() {
        super();
        this.buckets = [];
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
            const r = await fetch("/firewall/api/attempts-per-minute");
            this.buckets = await r.json();
        } catch (_) { /* ignore */ }
    }

    render() {
        if (!this.buckets.length) {
            return html`<svg viewBox="0 0 60 40"></svg>
                       <div class="total">no data</div>`;
        }
        const max = Math.max(1, ...this.buckets.map(b => b.count));
        const total = this.buckets.reduce((a, b) => a + b.count, 0);
        const points = this.buckets
            .map((b, i) => `${i},${40 - (b.count / max) * 38 - 1}`)
            .join(" ");
        return html`
            <svg viewBox="0 0 60 40" preserveAspectRatio="none">
                <polyline fill="none" stroke="#38bdf8" stroke-width="0.8"
                          points="${points}"/>
            </svg>
            <div class="total">${total} attempts in the last hour (peak ${max}/min)</div>
        `;
    }
}

customElements.define("attempts-sparkline", AttemptsSparkline);
