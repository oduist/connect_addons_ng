/** @odoo-module **/

// Odoo 15 variant (ADR-062): owl 1.x has no EventTarget-based EventBus.
// This class provides the same addEventListener/trigger({detail}) API on
// top of the native EventTarget, so the component code stays as close as
// possible to the 19.0 branch.
export class ConnectEventBus extends EventTarget {
    trigger(name, payload) {
        this.dispatchEvent(new CustomEvent(name, {detail: payload}))
    }
}
