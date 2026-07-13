/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const ConnectPhoneStatus = publicWidget.Widget.extend({
    selector: ".s_connect_phone_status",
    disabledInEditableMode: false,

    async start() {
        const superStart = this._super.bind(this);
        this.previousChildren = [...this.el.childNodes];
        const numberId = parseInt(this.el.dataset.numberId || "0", 10);
        if (!numberId) {
            return superStart(...arguments);
        }
        let data;
        try {
            const response = await fetch(`/freeswitch/schedule/status/${numberId}`);
            if (response.ok) {
                data = await response.json();
            }
        } catch {
            // Leave the placeholder content on network errors.
        }
        if (!data) {
            return superStart(...arguments);
        }
        const dataset = this.el.dataset;
        const parts = [];

        let numberEl;
        if (dataset.linkPhone === "true") {
            numberEl = document.createElement("a");
            numberEl.href = "tel:" + data.phone_number.replace(/[^+\d]/g, "");
            numberEl.textContent = data.phone_number;
        } else {
            numberEl = document.createElement("span");
            numberEl.textContent = data.phone_number;
        }
        parts.push(numberEl);

        let statusEl;
        const statusText = data.available ? "\u{1F7E2}" : "\u{1F534}";
        if (dataset.linkPage) {
            statusEl = document.createElement("a");
            statusEl.href = dataset.linkPage;
            statusEl.classList.add("text-decoration-none");
            statusEl.textContent = statusText;
        } else {
            statusEl = document.createElement("span");
            statusEl.textContent = statusText;
        }
        parts.push(document.createTextNode(" "), statusEl);

        if (dataset.showTime === "true" && data.status_text) {
            parts.push(document.createTextNode(` (${data.status_text})`));
        }

        this.el.replaceChildren(...parts);
        return superStart(...arguments);
    },

    destroy() {
        if (this.previousChildren) {
            this.el.replaceChildren(...this.previousChildren);
        }
        this._super(...arguments);
    },
});

publicWidget.registry.connectPhoneStatus = ConnectPhoneStatus;
