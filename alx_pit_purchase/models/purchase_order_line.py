# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    category_id = fields.Many2one(
        comodel_name='product.category',
        string='Categoría del producto',
        help='Se asigna al producto si es nuevo (costo = 0)',
    )
    product_list_price = fields.Float(
        string='Precio de venta',
        digits='Product Price',
        help='Se asigna al producto si es nuevo (costo = 0)',
    )
    available_in_pos = fields.Boolean(
        string='Disponible en PdV',
        help='Se asigna al producto si es nuevo (costo = 0)',
    )
    track_inventory = fields.Boolean(
        string='Rastrear inventario',
        help='Si está activo, el producto se crea como almacenable. Se asigna si es nuevo (costo = 0)',
    )

    # -------------------------------------------------------------------------
    # CRUD Overrides
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._propagate_to_product()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if {'price_unit', 'product_list_price', 'category_id', 'product_id',
                'available_in_pos', 'track_inventory'} & set(vals):
            self._propagate_to_product()
        return res

    # -------------------------------------------------------------------------
    # Business Logic
    # -------------------------------------------------------------------------

    def _propagate_to_product(self):
        """Propaga campos de configuración a la plantilla del producto cuando
        éste es nuevo (standard_price == 0). Usa la primera ocurrencia de cada
        plantilla en el recordset para evitar inconsistencias."""
        seen_templates = set()
        for line in self:
            tmpl = line.product_id.product_tmpl_id
            if not tmpl or tmpl.id in seen_templates:
                continue
            if tmpl.standard_price != 0:
                continue
            seen_templates.add(tmpl.id)
            vals = {'standard_price': line.price_unit}
            if line.product_list_price > 0:
                vals['list_price'] = line.product_list_price
            if line.category_id:
                vals['categ_id'] = line.category_id.id
            vals['available_in_pos'] = line.available_in_pos
            vals['is_storable'] = line.track_inventory
            tmpl.write(vals)
            _logger.info(
                'pit_purchase: propagado a producto nuevo id=%s campos=%s',
                tmpl.id, list(vals.keys()),
            )
