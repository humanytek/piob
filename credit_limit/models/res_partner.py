from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    credit_limit = fields.Float()
