import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class ConnectPhoneStatus extends Interaction {
    static selector = ".s_connect_phone_status";

    async willStart() {
        this.data = null;
        const numberId = parseInt(this.el.dataset.numberId || "0", 10);
        if (!numberId) {
            return;
        }
        try {
            const response = await this.waitFor(
                fetch(`/freeswitch/schedule/status/${numberId}`)
            );
            if (response.ok) {
                this.data = await this.waitFor(response.json());
            }
        } catch {
            // Leave the placeholder content on network errors.
        }
    }

    start() {
        if (!this.data) {
            return;
        }
        const data = this.data;
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

        const previousChildren = [...this.el.childNodes];
        this.el.replaceChildren(...parts);
        this.registerCleanup(() => {
            this.el.replaceChildren(...previousChildren);
        });
    }
}

registry
    .category("public.interactions")
    .add("connect_freeswitch_website.phone_status", ConnectPhoneStatus);
