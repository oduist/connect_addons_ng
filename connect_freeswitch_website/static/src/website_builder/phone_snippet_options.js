/** @odoo-module **/

import options from "@web_editor/js/editor/snippets.options";

const PhoneScheduleOptions = options.Class.extend({
    willStart() {
        const superWillStart = this._super.bind(this);
        return this.orm.searchRead(
                "connect.freeswitch.number",
                [["schedule_enabled", "=", true], ["schedule_id", "!=", false]],
                ["display_name"]
            )
            .then((phoneNumbers) => {
                this.phoneNumbers = phoneNumbers;
                return superWillStart(...arguments);
            });
    },

    async _renderCustomXML(uiFragment) {
        const selectorEl = uiFragment.querySelector("[data-name='phone_number_opt']");
        for (const number of this.phoneNumbers) {
            const buttonEl = document.createElement("we-button");
            buttonEl.dataset.selectDataAttribute = number.id;
            buttonEl.textContent = number.display_name;
            selectorEl.appendChild(buttonEl);
        }
    },
});

options.registry.ConnectPhoneStatus = PhoneScheduleOptions.extend({});
options.registry.ConnectPhoneOpeningHours = PhoneScheduleOptions.extend({});
