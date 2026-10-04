/** @odoo-module **/
import {Component, t, useProps} from "@odoo/owl"

export class ConnectActiveCallsTray extends Component {
    static template = 'connect.active_calls_tray'
    props = useProps({
        bus: t.any(),
    })

    _onClick() {
        this.props.bus.trigger('connect_active_calls_toggle_display')
    }
}
