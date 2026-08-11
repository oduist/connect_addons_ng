# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api

from vonage_numbers import ListOwnedNumbersFilter, UpdateNumberParams

from odoo.addons.connect.models.settings import debug
from .settings import to_e164

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    country = fields.Char(readonly=True)
    features = fields.Char(readonly=True)
    ncco = fields.Many2one('connect.ncco', string='NCCO', ondelete='set null')
    destination = fields.Selection(
        selection_add=[('ncco', 'NCCO')],
        ondelete={'ncco': 'set null'},
    )

    def write(self, vals):
        if 'destination' in vals:
            for field in ['user', 'callflow', 'ncco']:
                if field != vals['destination']:
                    vals.update({field: None})
        return super().write(vals)

    def link_to_application(self, client, number_data):
        """Point the number's voice and messages traffic to our Application."""
        self.ensure_one()
        application_id = self.env['connect.settings'].sudo().get_param(
            'vonage_application_id')
        if not application_id:
            return
        if number_data.app_id == application_id:
            return
        try:
            client.numbers.update_number(UpdateNumberParams(
                country=number_data.country,
                msisdn=number_data.msisdn,
                app_id=application_id,
            ))
            debug(self, 'Number {} linked to application {}.'.format(
                self.phone_number, application_id))
        except Exception as e:
            logger.error(
                'Cannot link number %s to the application: %s',
                self.phone_number, e)

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_client()
        vonage_numbers = []
        index = None
        while True:
            filter_kwargs = {'size': 100}
            if index:
                filter_kwargs['index'] = index
            numbers, _count, index = client.numbers.list_owned_numbers(
                ListOwnedNumbersFilter(**filter_kwargs))
            vonage_numbers.extend(numbers)
            if not index:
                break
        known_numbers = []
        for number in vonage_numbers:
            phone_number = to_e164(number.msisdn)
            known_numbers.append(phone_number)
            rec = self.search([('phone_number', '=', phone_number)], limit=1)
            if not rec:
                rec = self.create({
                    'phone_number': phone_number,
                    'friendly_name': number.msisdn,
                    'country': number.country,
                    'features': ','.join(number.features or []),
                })
                self.env['connect.settings'].connect_notify(
                    title='Vonage Sync',
                    message='Number {} added'.format(phone_number),
                )
            else:
                rec.write({
                    'country': number.country,
                    'features': ','.join(number.features or []),
                })
            rec.link_to_application(client, number)
        # Remove numbers that exist only in Odoo
        numbers_to_remove = self.search(
            [('phone_number', 'not in', known_numbers),
             ('country', '!=', False)])
        if numbers_to_remove:
            user_message = 'Number(s) {} removed in Vonage!'.format(
                ','.join([k.phone_number for k in numbers_to_remove]))
            numbers_to_remove.unlink()
            self.env['connect.settings'].connect_notify(
                title='Vonage Sync',
                warning=True,
                sticky=True,
                message=user_message,
            )

    def render(self, request={}, params={}):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect'):
            return [{'action': 'talk', 'text': 'Service unavailable.'}]
        if self.destination == 'ncco' and self.ncco:
            return self.ncco.render(request, params)
        elif self.destination == 'user' and self.user:
            return self.user.render(request, params)
        elif self.destination == 'callflow' and self.callflow:
            return self.callflow.render(request, params)
        else:
            return [{'action': 'talk',
                     'text': 'Number not configured. Goodbye!'}]

    @api.model
    def route_call(self, request, params={}):
        debug(self, 'Route number call: %s' % json.dumps(request, indent=2))
        # The answer webhook arrives before any status event: create the
        # inbound channel now so render() can find the call.
        event = dict(request)
        event.setdefault('status', 'started')
        event.setdefault('direction', 'inbound')
        self.env['connect.call'].on_voice_event(event)
        number = self.sudo().search(
            [('phone_number', '=', to_e164(request.get('to')))], limit=1)
        if not number:
            return [{'action': 'talk', 'text': 'Number not found. Goodbye!'}]
        return number.render(request=request, params=params)
