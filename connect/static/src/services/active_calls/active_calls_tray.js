/** @odoo-module **/
const {Component} = owl

export class ConnectActiveCallsTray extends Component {
    _onClick() {
        this.props.bus.trigger('connect_active_calls_toggle_display')
    }
}
ConnectActiveCallsTray.template = 'connect.active_calls_tray'
ConnectActiveCallsTray.props = {
    bus: Object,
}
