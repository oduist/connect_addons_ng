/** @odoo-module **/
import {Component, t, useProps} from "@odoo/owl"

export class ConnectActiveCallsTray extends Component {
    static template = 'connect_vonage.active_calls_tray'
    props = useProps({
        bus: t.object(),
    })

    _onClick() {
        this.props.bus.trigger('connect_active_calls_toggle_display')
    }
}

