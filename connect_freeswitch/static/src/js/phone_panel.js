/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { PhoneDialpad } from "./phone_systray";
import { ParkingPanel } from "./parking_panel";


export class PhonePanel extends Component {
    static template = "connect_freeswitch.PhonePanel";
    static components = { PhoneDialpad, ParkingPanel };
    static props = {
        bus: Object,
        displayMode: String,
        getVertoClient: Function,
        connect: Function,
    };

    setup() {
        this.state = useState({
            showDialpad: false,
            activeTab: "dialer",
            vertoState: "disconnected",
            callState: "idle",
            callerName: "",
            callerNumber: "",
        });

        this._onStateChanged = ({ detail }) => {
            this.state.vertoState = detail.vertoState;
        };
        this._onCallStateChanged = ({ detail }) => {
            this.state.callState = detail.callState;
            if (detail.callState === "idle") {
                this.state.callerName = "";
                this.state.callerNumber = "";
            } else {
                if (detail.callerName) this.state.callerName = detail.callerName;
                if (detail.callerNumber) this.state.callerNumber = detail.callerNumber;
            }
        };
        this._onToggle = ({ detail }) => {
            if (detail && detail.show !== undefined) {
                this.state.showDialpad = detail.show;
            } else {
                this.state.showDialpad = !this.state.showDialpad;
            }
        };
        this._onClose = () => {
            this.state.showDialpad = false;
        };
        this._onNavigated = () => {
            if (this.props.displayMode === "dropdown") {
                this.state.showDialpad = false;
            }
        };

        onMounted(() => {
            this.props.bus.addEventListener("phoneStateChanged", this._onStateChanged);
            this.props.bus.addEventListener("phoneCallStateChanged", this._onCallStateChanged);
            this.props.bus.addEventListener("phoneToggle", this._onToggle);
            this.props.bus.addEventListener("phoneClose", this._onClose);
            this.props.bus.addEventListener("phoneNavigated", this._onNavigated);
            // Verto fires phoneStateChanged once, ~1s after page load. If we
            // mount later (the panel often does — it's lazy), we miss it and
            // stay at the initial "disconnected" forever. Sync from the live
            // client now that listeners are in place.
            const vc = this.props.getVertoClient && this.props.getVertoClient();
            if (vc) {
                this.state.vertoState = vc.state || "disconnected";
                this.state.callState = vc.callState || "idle";
            }
        });

        onWillUnmount(() => {
            this.props.bus.removeEventListener("phoneStateChanged", this._onStateChanged);
            this.props.bus.removeEventListener("phoneCallStateChanged", this._onCallStateChanged);
            this.props.bus.removeEventListener("phoneToggle", this._onToggle);
            this.props.bus.removeEventListener("phoneClose", this._onClose);
            this.props.bus.removeEventListener("phoneNavigated", this._onNavigated);
        });
    }

    get modeClass() {
        return this.props.displayMode === "float" ? "o_phone_mode_float" : "o_phone_mode_dropdown";
    }

    closeDialpad() {
        this.state.showDialpad = false;
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }
}
