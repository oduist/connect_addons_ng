# -*- coding: utf-8 -*-
from odoo import fields, models, api


class Settings(models.Model):
    """One record model to keep all settings. The record is created on
    get_param / set_param methods on 1-st call.
    """

    _name = "connect.settings"
    _description = "Connect Settings"

    name = fields.Char(compute="_compute_name")
    debug_mode = fields.Boolean(string="Debug Mode")

    @api.depends_context('lang')
    def _compute_name(self):
        for rec in self:
            rec.name = "Connect Settings"

    @api.model
    def _get_settings_record(self):
        """Get or create the singleton settings record."""
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    @api.model
    def get_param(self, param):
        """Get a settings parameter value."""
        rec = self._get_settings_record()
        return getattr(rec, param, False)

    @api.model
    def set_param(self, param, value):
        """Set a settings parameter value."""
        rec = self._get_settings_record()
        if hasattr(rec, param):
            rec.write({param: value})

    @api.model
    def open_settings_form(self):
        """Open the settings form view."""
        rec = self._get_settings_record()
        return {
            "type": "ir.actions.act_window",
            "name": "Settings",
            "res_model": self._name,
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
