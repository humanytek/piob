# -*- coding: utf-8 -*-
import base64
import io
import zipfile
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_REPORT_DYMO = 'alx_stock_label_pagination.action_report_label_pagination_dymo'
_REPORT_A4 = 'alx_stock_label_pagination.action_report_label_pagination_a4'


class StockLabelPaginationWizard(models.TransientModel):
    _name = 'alx.stock.label.pagination.wizard'
    _description = 'Imprimir Etiquetas de Inventario con Paginación'

    picking_ids = fields.Many2many('stock.picking', string='Transferencias')

    label_format = fields.Selection(
        [('dymo', 'Dymo LabelWriter (57mm × 32mm)'),
         ('a4', 'Hoja A4 (3 columnas)')],
        string='Formato de etiqueta',
        default='dymo',
        required=True,
    )

    # Opción A — ZIP
    batch_size = fields.Integer('Etiquetas por archivo (ZIP)', default=200)

    # Informativos
    total_labels = fields.Integer('Total de etiquetas', compute='_compute_totals')
    total_batches = fields.Integer('Archivos ZIP que se generarán', compute='_compute_totals')

    # Opciones B y C — desactivadas (mantenidas para compatibilidad de modelo)
    page_size = fields.Integer('Etiquetas por página', default=100)
    page_number = fields.Integer('Número de página', default=1)
    total_pages = fields.Integer('Total de páginas', compute='_compute_totals')

    @api.depends('picking_ids', 'batch_size', 'page_size')
    def _compute_totals(self):
        for rec in self:
            items = rec._get_label_quantities()
            n = sum(qty for _, qty in items)
            rec.total_labels = n
            rec.total_batches = max(1, -(-n // rec.batch_size)) if rec.batch_size else 1
            rec.total_pages = max(1, -(-n // rec.page_size)) if rec.page_size else 1

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_label_quantities(self):
        """Devuelve [(line_id, qty)] — una entrada por línea de movimiento con producto.

        qty es el número de etiquetas a imprimir para esa línea:
        toma la cantidad procesada (quantity) o la demandada (move_id.product_uom_qty),
        mínimo 1.
        """
        result = []
        for line in self.picking_ids.move_line_ids.filtered(lambda l: l.product_id):
            qty = int(line.quantity or line.move_id.product_uom_qty or 1)
            result.append((line.id, max(1, qty)))
        return result

    def _report_xml_id(self):
        return _REPORT_A4 if self.label_format == 'a4' else _REPORT_DYMO

    def _picking_display_name(self):
        name = self.picking_ids.name if len(self.picking_ids) == 1 else 'multi'
        return name.replace('/', '-')

    def _assert_lines(self):
        if not self._get_label_quantities():
            raise UserError(_('No hay líneas con producto en las transferencias seleccionadas.'))

    # -------------------------------------------------------------------------
    # Opción A — ZIP: múltiples PDFs empaquetados en un solo archivo
    # -------------------------------------------------------------------------

    def _render_dymo_pdf(self, batch_qty):
        """Genera un PDF Dymo usando EXACTAMENTE el mismo reporte estándar de Odoo
        ('product.report_product_template_label_dymo') que utiliza el botón nativo
        'Imprimir Etiquetas → Dymo'.

        Las claves de quantity_by_product y custom_barcodes se pasan como **str**
        porque _prepare_data() las consume con str(product.id).  Cuando el reporte
        se renderiza via HTTP el paso por JSON lo haría automáticamente; aquí se
        llama directo desde Python por lo que hay que hacerlo explícito.
        """
        quantity_by_product = defaultdict(int)
        custom_barcodes = defaultdict(list)

        lines = self.env['stock.move.line'].browse(list(batch_qty.keys()))
        for line in lines:
            qty = batch_qty[line.id]
            if line.lot_id and qty > 0:
                custom_barcodes[str(line.product_id.id)].append(
                    (line.lot_id.name, qty)
                )
            else:
                quantity_by_product[str(line.product_id.id)] += qty

        # _prepare_data() requiere un product.label.layout válido para leer pricelist_id
        pricelist = self.env['product.pricelist'].search(
            [('active', '=', True), ('company_id', 'in', [False, self.env.company.id])],
            limit=1,
        )
        layout_wizard = self.env['product.label.layout'].create({
            'print_format': 'dymo',
            'product_ids': [(6, 0, list({line.product_id.id for line in lines}))],
            'pricelist_id': pricelist.id if pricelist else False,
        })

        data = {
            'active_model': 'product.product',
            'quantity_by_product': {k: v for k, v in quantity_by_product.items() if v > 0},
            'custom_barcodes': dict(custom_barcodes),
            'layout_wizard': layout_wizard.id,
            'price_included': False,
        }

        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            'product.report_product_template_label_dymo',
            res_ids=None,
            data=data,
        )
        return pdf_content

    def action_print_zip(self):
        """Divide las etiquetas en lotes de batch_size UNIDADES, genera un PDF por
        lote con las cantidades exactas por línea y los empaqueta en un ZIP.
        Para Dymo usa el reporte estándar de Odoo para garantizar output idéntico.
        """
        self.ensure_one()
        self._assert_lines()
        if not self.batch_size or self.batch_size < 1:
            raise UserError(_('El tamaño de lote debe ser mayor a 0.'))

        items = self._get_label_quantities()

        # Lista plana de IDs expandida por cantidad: [id1, id1, id2, id2, id2, ...]
        flat = []
        for line_id, qty in items:
            flat.extend([line_id] * qty)

        total = len(flat)
        batches_flat = [flat[i:i + self.batch_size] for i in range(0, total, self.batch_size)]
        name = self._picking_display_name()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, batch_flat in enumerate(batches_flat, 1):
                # Colapsar [id, id, id2, id2] → {id: 2, id2: 2}
                batch_qty = {}
                for lid in batch_flat:
                    batch_qty[lid] = batch_qty.get(lid, 0) + 1

                if self.label_format == 'dymo':
                    # Usa el reporte estándar de Odoo → output 100% idéntico al botón nativo
                    pdf_content = self._render_dymo_pdf(batch_qty)
                else:
                    pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                        _REPORT_A4,
                        res_ids=list(batch_qty.keys()),
                        data={'quantities': batch_qty},
                    )
                zf.writestr(
                    f'{name}_etiquetas_{idx:03d}_de_{len(batches_flat):03d}.pdf',
                    pdf_content,
                )

        zip_buffer.seek(0)
        attachment = self.env['ir.attachment'].create({
            'name': f'etiquetas_{name}.zip',
            'type': 'binary',
            'datas': base64.b64encode(zip_buffer.read()),
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    # -------------------------------------------------------------------------
    # Opción B — desactivada (PDF de un rango: el wizard hace el slice)
    # -------------------------------------------------------------------------

    # def action_print_range(self):
    #     """
    #     Calcula el rango [start:end] según page_number y page_size,
    #     pasa solo esos IDs al reporte y abre el PDF en el visor nativo.
    #     Nota: usa _get_label_line_ids() (IDs únicos, sin expansión por cantidad).
    #     """
    #     self.ensure_one()
    #     self._assert_lines()
    #     if not self.page_size or self.page_size < 1:
    #         raise UserError(_('El tamaño de página debe ser mayor a 0.'))
    #
    #     line_ids = [lid for lid, _ in self._get_label_quantities()]
    #     total_pages = max(1, -(-len(line_ids) // self.page_size))
    #     if not (1 <= self.page_number <= total_pages):
    #         raise UserError(_('Número de página fuera de rango (1–%d).') % total_pages)
    #
    #     start = (self.page_number - 1) * self.page_size
    #     batch_ids = line_ids[start:start + self.page_size]
    #
    #     report = self.env.ref(self._report_xml_id())
    #     action = report.report_action(batch_ids, config=False)
    #     action['close_on_report_download'] = True
    #     return action

    # -------------------------------------------------------------------------
    # Opción C — desactivada (paginación en AbstractModel)
    # -------------------------------------------------------------------------

    # def action_print_paginated_c(self):
    #     """
    #     Pasa TODOS los IDs al reporte junto con page_size y page_num en `data`.
    #     El AbstractModel (report.alx_stock_label_pagination.report_label_pagination)
    #     se encarga de hacer el slice antes de hacer el browse, demostrando que
    #     la lógica de paginación puede vivir en la capa del reporte y no en el wizard.
    #     Nota: no usa expansión por cantidad; renderiza una etiqueta por línea.
    #     """
    #     self.ensure_one()
    #     self._assert_lines()
    #     if not self.page_size or self.page_size < 1:
    #         raise UserError(_('El tamaño de página debe ser mayor a 0.'))
    #
    #     line_ids = [lid for lid, _ in self._get_label_quantities()]
    #     data = {
    #         'page_size': self.page_size,
    #         'page_num': self.page_number - 1,
    #     }
    #     pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
    #         self._report_xml_id(), line_ids, data=data
    #     )
    #     name = self._picking_display_name()
    #     attachment = self.env['ir.attachment'].create({
    #         'name': f'etiquetas_{name}_pag{self.page_number}.pdf',
    #         'type': 'binary',
    #         'datas': base64.b64encode(pdf_content),
    #         'res_model': self._name,
    #         'res_id': self.id,
    #     })
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/{attachment.id}?download=true',
    #         'target': 'self',
    #     }
