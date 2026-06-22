from odoo import models


class ReportLabelPagination(models.AbstractModel):
    _name = 'report.alx_stock_label_pagination.report_label_pagination'
    _description = 'Reporte de Etiquetas — A4 (3 columnas)'

    def _get_report_values(self, docids, data=None):
        d = data or {}
        # JSON coerces int dict keys to str — normalise to int before lookup
        quantities = {int(k): v for k, v in d.get('quantities', {}).items()}

        unique_ids = list(dict.fromkeys(docids))
        line_map = {l.id: l for l in self.env['stock.move.line'].browse(unique_ids)}

        expanded = []
        for lid in unique_ids:
            line = line_map.get(lid)
            if not line:
                continue
            qty = quantities.get(lid) or int(
                line.quantity or line.move_id.product_uom_qty or 1
            )
            expanded.extend([line] * max(1, qty))

        return {
            'doc_ids': docids,
            'doc_model': 'stock.move.line',
            'docs': expanded,
            'data': d,
        }


class ReportLabelDymo(models.AbstractModel):
    _name = 'report.alx_stock_label_pagination.report_label_dymo'
    _inherit = 'report.alx_stock_label_pagination.report_label_pagination'
    _description = 'Reporte de Etiquetas — Dymo (1 por página)'

    def _get_report_values(self, docids, data=None):
        vals = super()._get_report_values(docids, data=data)
        # product.report_simple_label_dymo requiere `pricelist` en el contexto.
        # Usamos la lista de precios del usuario o la primera activa en la compañía.
        pricelist = (
            self.env.user.property_product_pricelist
            or self.env['product.pricelist'].search([('active', '=', True)], limit=1)
        )
        vals['pricelist'] = pricelist
        return vals
