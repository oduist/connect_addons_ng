/** @odoo-module **/
"use strict"
import {Component, useState, onMounted} from "@odoo/owl"

export class LivekitPhoneSysTray extends Component {
    static template = 'connect_livekit.menu'
    static props = {
        bus: Object,
    }

    setup() {
        this.state = useState({
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
