/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const ConnectPhoneOpeningHours = publicWidget.Widget.extend({
    selector: ".s_connect_phone_opening_hours",
    disabledInEditableMode: false,

    async start() {
        this.previousChildren = [...this.el.childNodes];
        const numberId = parseInt(this.el.dataset.numberId || "0", 10);
        if (!numberId) {
            return this._super(...arguments);
        }
        const days = parseInt(this.el.dataset.days || "10", 10) || 10;
        let data;
        try {
            const response = await fetch(
                `/freeswitch/schedule/opening_hours/${numberId}?days=${days}`
            );
            if (response.ok) {
                data = await response.json();
            }
        } catch {
            // Leave the placeholder content on network errors.
        }
        if (!data) {
            return this._super(...arguments);
        }
        const dataset = this.el.dataset;
        const useLongDate = dataset.dateFormat !== "short";
        const showLabels = dataset.showLabels === "true";

        const tableEl = document.createElement("table");
        tableEl.classList.add("table", "table-sm");
        const bodyEl = document.createElement("tbody");
        for (const day of data.days) {
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

        this.el.replaceChildren(tableEl);
        return this._super(...arguments);
    },

    destroy() {
        if (this.previousChildren) {
            this.el.replaceChildren(...this.previousChildren);
        }
        this._super(...arguments);
    },
});

publicWidget.registry.connectPhoneOpeningHours = ConnectPhoneOpeningHours;
