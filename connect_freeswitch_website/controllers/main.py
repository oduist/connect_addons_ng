# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

import pytz
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request
from odoo.tools import format_date, format_time

logger = logging.getLogger(__name__)

MAX_DAYS = 60


class ConnectFreeswitchWebsite(http.Controller):
    """Public read-only JSON endpoints backing the phone status and
    opening hours website snippets. Only numbers with an enabled working
    schedule are exposed; everything else is a 404."""

    def _get_number(self, number_id):
        number = request.env['connect.freeswitch.number'].sudo().browse(
            number_id).exists()
        if not number or not number.schedule_enabled or not number.schedule_id:
            raise NotFound()
        return number

    @http.route('/freeswitch/schedule/status/<int:number_id>',
                type='http', auth='public', website=True, methods=['GET'])
    def schedule_status(self, number_id, **kwargs):
        number = self._get_number(number_id)
        schedule = number.schedule_id
        status = schedule.get_status()
        env = request.env
        tz = pytz.timezone(schedule.calendar_id.tz or 'UTC')
        today = datetime.now(tz).date()

        def local(dt_utc):
            return pytz.utc.localize(dt_utc).astimezone(tz)

        status_text = ''
        if status['available'] and status['until']:
            until = local(status['until'])
            time_str = format_time(env, until.time(), time_format='short')
            if until.date() == today:
                status_text = env._('available until %s', time_str)
            else:
                status_text = env._(
                    'available until %(day)s %(time)s',
                    day=format_date(env, until.date(), date_format='EEEE'),
                    time=time_str)
        elif not status['available'] and status['next_open']:
            next_open = local(status['next_open'])
            time_str = format_time(env, next_open.time(), time_format='short')
            if next_open.date() == today:
                status_text = env._('opens at %s', time_str)
            elif next_open.date() == today + timedelta(days=1):
                status_text = env._('opens tomorrow %s', time_str)
            else:
                status_text = env._(
                    'opens %(day)s %(time)s',
                    day=format_date(
                        env, next_open.date(), date_format='EEEE'),
                    time=time_str)
        return request.make_json_response({
            'available': status['available'],
            'phone_number': number.phone_number,
            'status_text': status_text,
        })

    @http.route('/freeswitch/schedule/opening_hours/<int:number_id>',
                type='http', auth='public', website=True, methods=['GET'])
    def schedule_opening_hours(self, number_id, days=10, **kwargs):
        number = self._get_number(number_id)
        schedule = number.schedule_id
        env = request.env
        try:
            days = max(1, min(int(days), MAX_DAYS))
        except (TypeError, ValueError):
            days = 10
        tz = pytz.timezone(schedule.calendar_id.tz or 'UTC')
        today = datetime.now(tz).date()
        day_list = []
        for day in schedule.get_day_data(today, days):
            if day['windows']:
                hours = ', '.join(
                    '{} – {}'.format(
                        format_time(env, s.time(), time_format='short'),
                        format_time(env, e.time(), time_format='short'))
                    for s, e in day['windows'])
            else:
                hours = env._('Closed')
            day_list.append({
                'date_short': format_date(
                    env, day['date'], date_format='dd.MM.yyyy'),
                'date_long': format_date(
                    env, day['date'], date_format='EEEE, dd.MM.yyyy'),
                'hours': hours,
                'label': day['label'] or '',
                'closed': not day['windows'],
            })
        return request.make_json_response({
            'phone_number': number.phone_number,
            'days': day_list,
        })
