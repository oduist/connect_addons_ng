/** @odoo-module **/

// Odoo 15 variant (ADR-062): the wowl bus_service with typed subscribe()
// is 17+. On 15 the longpolling bus is a legacy AbstractService, so this
// bridge subscribes on the legacy side and reaches the wowl notification
// and action services through the root env (owl.Component.env, set by
// startWebClient on Odoo 15).
import AbstractService from "web.AbstractService"
import core from "web.core"
import session from "web.session"

const personal_channel = 'connect_actions_' + session.uid
const common_channel = 'connect_actions'

function stripHtml(text) {
    // 15's notification service renders the message as text; server-sent
    // markup would otherwise show up as escaped tags.
    const div = document.createElement('div')
    div.innerHTML = text || ''
    return div.textContent || ''
}

export const PbxActionService = AbstractService.extend({
    dependencies: ['bus_service'],

    start() {
        this._super(...arguments)
        this.call('bus_service', 'addChannel', personal_channel)
        this.call('bus_service', 'addChannel', common_channel)
        this.call('bus_service', 'onNotification', this, this._onNotification)
    },

    _wowlServices() {
        const env = owl.Component.env
        return (env && env.services) || {}
    },

    _onNotification(notifications) {
        for (const notif of notifications) {
            const message = (notif && notif.message !== undefined) ? notif.message : notif
            if (!message || typeof message !== 'object') {
                continue
            }
            if (message.type === 'connect_notify') {
                this.connect_handle_notify(message.payload || {})
            } else if (message.type === 'reload_view') {
                this.connect_handle_reload_view(message.payload || {})
            }
        }
    },

    connect_handle_reload_view(message) {
        const {action} = this._wowlServices()
        try {
            const controller = action && action.currentController
            if (controller && controller.action &&
                    controller.action.res_model === message.model) {
                action.restore(controller.jsId)
                return
            }
            if (controller) {
                return
            }
        } catch (error) {
            console.warn('connect reload_view failed:', error)
        }
        // Fallback when the controller is not reachable: reload only if the
        // current URL points at the reloaded model.
        if (window.location.hash.includes(`model=${message.model}`)) {
            window.location.reload()
        }
    },

    connect_handle_notify({title, message, sticky, warning}) {
        const {notification} = this._wowlServices()
        if (!notification) {
            return
        }
        notification.add(stripHtml(message), {
            title, sticky, type: warning === true ? 'danger' : 'info'})
    },
})

core.serviceRegistry.add('connectTelnyxActionService', PbxActionService)
