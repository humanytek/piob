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
        # Pass which fields were explicitly provided so _propagate_to_product
        # can avoid overwriting product booleans with default False values on
        # auto-created lines (e.g. procurement triggered by sale confirmation).
        for line, vals in zip(lines, vals_list):
            line._propagate_to_product(explicit_fields=set(vals.keys()))
        return lines

    def write(self, vals):
        res = super().write(vals)
        trigger_fields = {'price_unit', 'product_list_price', 'category_id',
                          'product_id', 'available_in_pos', 'track_inventory'}
        if trigger_fields & set(vals):
            self._propagate_to_product(explicit_fields=set(vals.keys()))
        return res

    # -------------------------------------------------------------------------
    # Business Logic
    # -------------------------------------------------------------------------

    def _propagate_to_product(self, explicit_fields=None):
        """Propaga campos de configuración a la plantilla del producto cuando
        éste es nuevo (standard_price == 0). Usa la primera ocurrencia de cada
        plantilla en el recordset para evitar inconsistencias.

        Args:
            explicit_fields: conjunto de nombres de campo que fueron provistos
                explícitamente en los vals originales del create/write.  Si es
                None se asume que todos los campos son explícitos (compatibilidad
                hacia atrás).  Los campos booleanos 'track_inventory' y
                'available_in_pos' SÓLO se propagan cuando estaban en este
                conjunto; de lo contrario solo tienen su valor por defecto (False)
                y escribirlos desactivaría la configuración existente del producto.

                Caso problemático sin este guard:
                  - Se confirma una venta con 500 productos que tienen ruta "Compra".
                  - La confirmación dispara aprovisionamiento que crea líneas de OC
                    automáticamente, sin 'track_inventory' en los vals.
                  - _propagate_to_product escribía is_storable=False en cada
                    producto con standard_price==0, desactivando rastreo de stock.
        """
        if explicit_fields is None:
            explicit_fields = {'track_inventory', 'available_in_pos'}  # asumir explícitos

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
            # Solo propagar booleanos si el usuario los especificó explícitamente.
            # Si no estaban en los vals originales solo tienen su valor por defecto
            # (False) y sobreescribirlos destruiría la configuración del producto.
            if 'available_in_pos' in explicit_fields:
                vals['available_in_pos'] = line.available_in_pos
            if 'track_inventory' in explicit_fields:
                vals['is_storable'] = line.track_inventory
            tmpl.write(vals)
            _logger.info(
                'pit_purchase: propagado a producto nuevo id=%s campos=%s',
                tmpl.id, list(vals.keys()),
            )
