from odoo import _, api, fields, models


class PoSOrderLine(models.Model):
    _inherit = "pos.order.line"

    order_name = fields.Char(
        related="order_id.name",
    )
    order_session_id = fields.Many2one(
        related="order_id.session_id",
    )
    order_partner_id = fields.Many2one(
        related="order_id.partner_id",
    )
    order_date_order = fields.Datetime(
        related="order_id.date_order",
    )
    order_user_id = fields.Many2one(
        related="order_id.user_id",
    )
    order_fiscal_position_id = fields.Many2one(
        related="order_id.fiscal_position_id",
    )
