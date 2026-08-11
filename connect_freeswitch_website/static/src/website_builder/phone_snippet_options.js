import { BuilderAction } from "@html_builder/core/builder_action";
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class PhoneStatusOption extends BaseOptionComponent {
    static template = "connect_freeswitch_website.PhoneStatusOption";
    static selector = ".s_connect_phone_status";
}

export class PhoneOpeningHoursOption extends BaseOptionComponent {
    static template = "connect_freeswitch_website.PhoneOpeningHoursOption";
    static selector = ".s_connect_phone_opening_hours";
}

export class ConnectPhoneNumberAction extends BuilderAction {
    static id = "connectPhoneNumber";
    static dependencies = ["builderActions"];

    apply({ editingElement, value }) {
        const { id } = JSON.parse(value);
        this.dependencies.builderActions
            .getAction("dataAttributeAction")
            .apply({ editingElement, params: { mainParam: "numberId" }, value: id });
    }

    clean({ editingElement }) {
        this.dependencies.builderActions
            .getAction("dataAttributeAction")
            .clean({ editingElement, params: { mainParam: "numberId" } });
    }

    getValue({ editingElement }) {
        const id = this.dependencies.builderActions
            .getAction("dataAttributeAction")
            .getValue({ editingElement, params: { mainParam: "numberId" } });
        if (!id) {
            return;
        }
        return JSON.stringify({ id: parseInt(id) });
    }
}

class ConnectPhoneOptionPlugin extends Plugin {
    static id = "connectPhoneOption";
    static dependencies = ["builderActions"];
    resources = {
        builder_options: [PhoneStatusOption, PhoneOpeningHoursOption],
        builder_actions: {
            ConnectPhoneNumberAction,
        },
        dropzone_selector: {
            selector: ".s_connect_phone_status, .s_connect_phone_opening_hours",
            dropNear: "p, h1, h2, h3, blockquote, .card",
        },
    };
}

registry
    .category("website-plugins")
    .add(ConnectPhoneOptionPlugin.id, ConnectPhoneOptionPlugin);
