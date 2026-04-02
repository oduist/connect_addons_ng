/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { PhoneDialpad } from "./phone_systray";


export class PhonePanel extends Component {
    static template = "connect_freeswitch.PhonePanel";
    static components = { PhoneDialpad };
    static props = {
        bus: Object,
        displayMode: String,
        getVertoClient: Function,
        connect: Function,
    };

    setup() {
        this.panelRef = useRef("panelRef");

        this.state = useState({
            showDialpad: false,
            vertoState: "disconnected",
            callState: "idle",
            callerName: "",
            callerNumber: "",
        });

        this._anchorRect = null;

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
            if (detail && detail.anchorRect) {
                this._anchorRect = detail.anchorRect;
            }
            this._updateDropdownPosition();
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
        });

        onWillUnmount(() => {
            this.props.bus.removeEventListener("phoneStateChanged", this._onStateChanged);
            this.props.bus.removeEventListener("phoneCallStateChanged", this._onCallStateChanged);
            this.props.bus.removeEventListener("phoneToggle", this._onToggle);
            this.props.bus.removeEventListener("phoneClose", this._onClose);
            this.props.bus.removeEventListener("phoneNavigated", this._onNavigated);
        });
    }

    _updateDropdownPosition() {
        if (this.props.displayMode !== "dropdown" || !this.state.showDialpad) return;

        // Wait for the DOM to render, then position the dialpad
        requestAnimationFrame(() => {
            const dialpad = this.panelRef.el?.querySelector(".o_phone_dialpad");
            if (!dialpad || !this._anchorRect) return;

            const rect = this._anchorRect;
            dialpad.style.top = `${rect.bottom}px`;
            dialpad.style.right = `${window.innerWidth - rect.right}px`;
        });
    }

    get modeClass() {
        return this.props.displayMode === "float" ? "o_phone_mode_float" : "o_phone_mode_dropdown";
    }

    closeDialpad() {
        this.state.showDialpad = false;
    }
}
