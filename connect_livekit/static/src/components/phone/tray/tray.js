/** @odoo-module **/
"use strict"
import {Component, onMounted, proxy, t, useProps} from "@odoo/owl"

export class LivekitPhoneSysTray extends Component {
    static template = 'connect_livekit.menu'
    props = useProps({
        bus: t.object(),
    })

    setup() {
        this.state = proxy({
            inCall: false,
        })
        onMounted(() => {
            this.props.bus.addEventListener('busLivekitTrayState', ({detail}) => {
                this.state.inCall = detail.inCall
            })
        })
    }

    _onClick() {
        this.props.bus.trigger('busLivekitPhoneToggle')
    }
}
