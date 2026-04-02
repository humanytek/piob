from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'
    # Scan status is tracked per line (stock.move.line.captured_by_barcode).
    # No aggregate fields needed on the move itself.
