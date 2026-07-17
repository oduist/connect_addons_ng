import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class ConnectPhoneOpeningHours extends Interaction {
    static selector = ".s_connect_phone_opening_hours";

    async willStart() {
        this.data = null;
        const numberId = parseInt(this.el.dataset.numberId || "0", 10);
        if (!numberId) {
            return;
        }
        const days = parseInt(this.el.dataset.days || "10", 10) || 10;
        try {
            const response = await this.waitFor(
                fetch(`/freeswitch/schedule/opening_hours/${numberId}?days=${days}`)
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
        const dataset = this.el.dataset;
        const useLongDate = dataset.dateFormat !== "short";
        const showLabels = dataset.showLabels === "true";

        const tableEl = document.createElement("table");
        tableEl.classList.add("table", "table-sm");
        const bodyEl = document.createElement("tbody");
        for (const day of this.data.days) {
            const rowEl = document.createElement("tr");
            const dateEl = document.createElement("td");
            dateEl.textContent = useLongDate ? day.date_long : day.date_short;
            const hoursEl = document.createElement("td");
            hoursEl.textContent = day.hours;
            if (day.closed) {
                hoursEl.classList.add("text-muted");
            }
            if (showLabels && day.label) {
                const labelEl = document.createElement("em");
                labelEl.textContent = ` (${day.label})`;
                hoursEl.appendChild(labelEl);
            }
            rowEl.append(dateEl, hoursEl);
            bodyEl.appendChild(rowEl);
        }
        tableEl.appendChild(bodyEl);

        const previousChildren = [...this.el.childNodes];
        this.el.replaceChildren(tableEl);
        this.registerCleanup(() => {
            this.el.replaceChildren(...previousChildren);
        });
    }
}

registry
    .category("public.interactions")
    .add(
        "connect_freeswitch_website.phone_opening_hours",
        ConnectPhoneOpeningHours
    );
