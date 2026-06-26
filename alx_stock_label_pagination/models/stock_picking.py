from odoo import _, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_open_label_pagination_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imprimir Etiquetas con Paginación'),
            'res_model': 'alx.stock.label.pagination.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_ids': self.ids},
        }
