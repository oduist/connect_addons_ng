/** @odoo-module */

import {Notification} from "@mail/core/common/notification_model"
import {_t} from "@web/core/l10n/translation"
import {patch} from "@web/core/utils/patch"

// connect_twilio ships an equivalent WhatsApp patch; both call super for
// foreign types, so stacking is safe on co-installation.
patch(Notification.prototype, {
    get icon() {
        if (this.notification_type === "WhatsApp") {
            return "fa fa-whatsapp"
        }
        if (this.notification_type === "RCS") {
            return "fa fa-commenting-o"
        }
        return super.icon
    },
    get label() {
        if (this.notification_type === "WhatsApp") {
            return _t("WhatsApp")
        }
        if (this.notification_type === "RCS") {
            return _t("RCS")
        }
        return super.label
    },
})
