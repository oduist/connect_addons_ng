/** @odoo-module **/

import {useService} from "@web/core/utils/hooks"
import session from "web.session"

const {Component} = owl
const {useState, onWillStart} = owl.hooks

const uid = session.uid

export class Favorites extends Component {

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
    }

    setup() {
        this.orm = useService('orm')
        this.action = useService('action')
        this.user = uid
        this.state = useState({
            favorites: [],
        })

        onWillStart(async () => {
            this.getFavorites()
        })
    }

    getFavorites() {
        const fields = [
            "id",
            "name",
            "partner",
            "user",
            "phone_number",
        ]

        this.orm.searchRead("connect.favorite", [], fields, {limit: 30}).then((records) => {
            this.state.favorites = records
        })
    }

    _onClickContactCall(phone_number) {
        this.bus.trigger('busPhoneMakeCall', {phone: phone_number})
    }

    // Odoo 15 / owl 1: inline handlers receive the event as last argument.
    _onClickRemoveFavorite(id, ev) {
        ev.stopPropagation()
        this.orm.unlink("connect.favorite", [id], {}).then(() => {
            this.getFavorites()
            this.bus.trigger('busCallsGetFavorites')
        })

    }
}
Favorites.template = 'connect_telnyx.favorites'
Favorites.props = {
    bus: Object,
}
