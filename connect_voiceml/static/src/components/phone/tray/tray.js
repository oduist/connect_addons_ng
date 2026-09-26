/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { VoiceMLPhone } from "@connect_voiceml/components/phone/phone";

export class VoiceMLPhoneSysTray extends Component {
    static template = "connect_voiceml.phone_tray";

    setup() {
        this.state = useState({ open: false });
    }
}

VoiceMLPhoneSysTray.components = { VoiceMLPhone };
