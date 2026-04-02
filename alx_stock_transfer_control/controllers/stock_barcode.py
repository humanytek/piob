import logging

from odoo import http
from odoo.http import request
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController

_logger = logging.getLogger(__name__)


class StockTransferBarcodeController(StockBarcodeController):
    """
    Override the Barcode App's save endpoint to inject the 'from_barcode_app'
    context flag into every ORM call triggered by a barcode scan.

    This allows stock_move_line.write() to distinguish between:
      - A legitimate barcode scan  → allow, mark captured_by_barcode = True
      - A manual form-view edit    → block for Operators
    """

    @http.route('/stock_barcode/save_barcode_data', type='jsonrpc', auth='user')
    def save_barcode_data(self, model, res_id, write_field, write_vals):
        # NOTE: if this log line never appears, Odoo's router is using the parent
        # class route directly (registered first at stock_barcode module load).
        # Detection falls back to HTTP path inspection in stock_move_line._is_from_barcode_app().
        _logger.info("[BARCODE SAVE] CONTROLLER HIT user=%s model=%s res_id=%s write_field=%s",request.env.user.login, model, res_id, write_field,)
        _logger.debug("[BARCODE SAVE] write_vals=%s", write_vals)
        # Belt-and-suspenders: inject context flag for the ORM write chain.
        request.update_env(context={**request.env.context, 'from_barcode_app': True})
        result = super().save_barcode_data(model, res_id, write_field, write_vals)
        _logger.info("[BARCODE SAVE] completed successfully for res_id=%s", res_id)
        return result
