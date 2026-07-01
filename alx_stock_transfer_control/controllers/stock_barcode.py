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

    def _get_groups_data(self):
        """
        Inject 'user_can_edit_qty' into the barcode groups payload.
        True only for group_stock_inventory_admin; hides the -1/+1/+N scan
        buttons and the digipad in the line-edit form for all other roles.
        """
        group_data = super()._get_groups_data()
        group_data['user_can_edit_qty'] = request.env.user.has_group(
            'alx_stock_transfer_control.group_stock_inventory_admin'
        )
        return group_data

    @http.route('/stock_barcode/save_barcode_data', type='jsonrpc', auth='user')
    def save_barcode_data(self, model, res_id, write_field, write_vals):
        _logger.info("[BARCODE SAVE] CONTROLLER HIT user=%s model=%s res_id=%s write_field=%s",request.env.user.login, model, res_id, write_field,)
        _logger.debug("[BARCODE SAVE] write_vals=%s", write_vals)
       
        # Inject context flag for the ORM write chain.
        request.update_env(context={**request.env.context, 'from_barcode_app': True})
        result = super().save_barcode_data(model, res_id, write_field, write_vals)
        return result
