/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";


export class ParkingPanel extends Component {
    static template = "connect_freeswitch.ParkingPanel";
    static props = {
        bus: Object,
        vertoClient: { optional: true },
        callState: String,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            slots: [],
            loading: false,
        });

        this._onParkingChanged = () => this._refreshSlots();

        onWillStart(async () => {
            await this._refreshSlots();
        });

        onMounted(() => {
            this.props.bus.addEventListener("parkingStateChanged", this._onParkingChanged);
        });

        onWillUnmount(() => {
            this.props.bus.removeEventListener("parkingStateChanged", this._onParkingChanged);
        });
    }

    async _refreshSlots() {
        this.state.loading = true;
        try {
            const slots = await this.orm.searchRead(
                "connect.freeswitch.parking.slot",
                [["active", "=", true]],
                [
                    "id", "name", "exten", "sequence",
                    "is_occupied", "parked_caller_number",
                    "parked_caller_name", "parked_at",
                ],
                { order: "sequence, exten" },
            );
            this.state.slots = slots;
        } catch (error) {
            console.error("[Parking] Failed to load slots:", error);
        } finally {
            this.state.loading = false;
        }
    }

    get hasActiveCall() {
        return this.props.callState === "active";
    }

    async onSlotClick(slot) {
        if (slot.is_occupied) {
            await this._unpark(slot);
        } else if (this.hasActiveCall) {
            await this._park(slot);
        } else {
            this.notification.add(
                _t("No active call to park. Connect first, then press Park on a free slot."),
                { type: "info" },
            );
        }
    }

    async _park(slot) {
        const uuid = this.props.vertoClient?.currentCall?.callId;
        if (!uuid) {
            this.notification.add(_t("No active call UUID found."), { type: "warning" });
            return;
        }
        try {
            const action = await this.orm.call(
                "connect.call", "action_fs_park_by_uuid", [uuid, slot.id],
            );
            if (action && action.params && action.params.message) {
                this.notification.add(action.params.message, {
                    type: action.params.type || "success",
                    title: action.params.title,
                });
            }
        } catch (error) {
            this._notifyError(error);
        }
    }

    async _unpark(slot) {
        try {
            const action = await this.orm.call(
                "connect.freeswitch.parking.slot", "action_unpark", [[slot.id]],
            );
            if (action && action.params && action.params.message) {
                this.notification.add(action.params.message, {
                    type: action.params.type || "info",
                    title: action.params.title,
                });
            }
        } catch (error) {
            this._notifyError(error);
        }
    }

    _notifyError(error) {
        const msg = error?.data?.message || error?.message || _t("Operation failed.");
        this.notification.add(msg, { type: "danger" });
    }

    slotClass(slot) {
        const base = "o_parking_slot";
        if (slot.is_occupied) return base + " o_parking_slot_occupied";
        if (this.hasActiveCall) return base + " o_parking_slot_parkable";
        return base + " o_parking_slot_idle";
    }

    slotLabel(slot) {
        if (slot.is_occupied) {
            if (slot.parked_caller_name && slot.parked_caller_number) {
                return `${slot.parked_caller_name} (${slot.parked_caller_number})`;
            }
            return slot.parked_caller_name || slot.parked_caller_number || _t("Parked");
        }
        return _t("Free");
    }
}
