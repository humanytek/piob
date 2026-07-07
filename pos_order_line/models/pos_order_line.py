from odoo import api, fields, models


class PoSOrderLine(models.Model):
    _inherit = "pos.order.line"

    translated_product_name = fields.Char(
        string="Product Name (Translated)",
        compute="_compute_translated_product_name",
    )

    @api.depends("product_id")
    def _compute_translated_product_name(self):
        for line in self:
            line.translated_product_name = line.product_id.name if line.product_id else False

