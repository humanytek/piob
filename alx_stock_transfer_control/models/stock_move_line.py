import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request as http_request


_logger = logging.getLogger(__name__)

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    captured_by_barcode = fields.Boolean(string='Capturado por Código de Barras', default=False, help='Se establece como verdadero cuando esta línea fue confirmada mediante la aplicación de Código de Barras.')
    manual_entry_reason = fields.Text(string='Motivo de Captura Manual', help='Requerido cuando un supervisor ingresa cantidades manualmente.')
    user_can_edit_operations = fields.Boolean(
        related='picking_id.user_can_edit_operations',
        help='True for supervisors/admins: controls location field editability in views.',
    )
    user_can_edit_qty = fields.Boolean(
        related='picking_id.user_can_edit_qty',
        help='True only for admins: controls quantity field editability in views.',
    )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _user_is_restricted_operator(self):
        """Return True if the current user is a plain Operator (not supervisor/admin)."""
        if self.env.su:
            return False

        user = self.env.user
        if user.has_group('alx_stock_transfer_control.group_stock_logistics_supervisor'):
            return False
        
        return user.has_group('alx_stock_transfer_control.group_stock_operator')

    def _is_from_barcode_app(self):
        """Return True when the call originates from the Barcode App's save endpoint.

        Two detection methods are tried in order:
        1. Context flag 'from_barcode_app' — set by our controller override when
           the route inheritance works correctly.
        2. HTTP request path — reliable fallback when controller subclassing does
           not intercept the route (Odoo registers the parent route first).
        """
        if self.env.context.get('from_barcode_app'):
            _logger.info("[BARCODE DETECT] detected via context flag")
            return True
        try:
            if http_request and http_request.httprequest.path == '/stock_barcode/save_barcode_data':
                _logger.info(
                    "[BARCODE DETECT] detected via HTTP path for user=%s ids=%s",
                    self.env.user.login, self.ids,
                )
                return True
        except Exception:
            pass
        _logger.debug("[BARCODE DETECT] not a barcode request for user=%s ids=%s", self.env.user.login, self.ids)
        return False

    # -------------------------------------------------------------------------
    # ORM overrides — Restrictions 
    # -------------------------------------------------------------------------
    def write(self, vals):
        """
        Operators can only update quantity-related fields through the Barcode App.
        - Manual edits to quantity/picked/qty_done are blocked.
        - Barcode App writes (context from_barcode_app=True) are allowed and auto-mark
          captured_by_barcode = True.
        - Location, product, and move changes are always blocked for operators.
        """
        from_barcode = self._is_from_barcode_app()
        _logger.info("[ML WRITE] user=%s from_barcode=%s ids=%s vals_keys=%s",
            self.env.user.login, from_barcode, self.ids, list(vals.keys()))

        qty_fields = {'quantity', 'picked', 'qty_done'}
        writing_qty = qty_fields.intersection(vals)

        # Qty restriction: operators AND supervisors must always use the Barcode App.
        # Only admins (group_stock_inventory_admin) can edit quantities directly.
        if writing_qty and not from_barcode and not self.env.su:
            if not self.env.user.has_group('alx_stock_transfer_control.group_stock_inventory_admin'):
                _logger.warning("[ML WRITE] BLOCKED manual qty change: user=%s ids=%s",
                    self.env.user.login, self.ids)
                raise ValidationError(_("No se permiten cambios manuales de cantidades. Utilice la aplicación de Código de Barras para escanear los productos."))

        # Mark barcode capture for any role scanning via the app
        if writing_qty and from_barcode:
            _logger.info("[ML WRITE] marking captured_by_barcode=True for ids=%s", self.ids)
            vals = dict(vals, captured_by_barcode=True)

        # Structural restriction: only operators are blocked from locations, product, lot.
        # Supervisors and admins can freely change location_id / location_dest_id on move lines.
        if self._user_is_restricted_operator():
            locked_structural = {
                'location_id', 'location_dest_id', 'result_package_id',
                'product_id', 'move_id', 'manual_entry_reason',
            }
            if locked_structural.intersection(vals):
                raise ValidationError(_("No tiene permiso para modificar las líneas de movimiento de inventario."))

        return super().write(vals)

    def unlink(self):
        """
        Only Admins (and sudo/system) can delete move lines where work has been confirmed.
        Odoo's internal machinery (_action_done, _do_unreserve, _free_reservation) exclusively
        deletes lines with picked=False — reservation placeholders — which must pass through
        for all roles so that validation and unreservation work correctly.
        """
        if not self.env.su and not self.env.user.has_group('alx_stock_transfer_control.group_stock_inventory_admin'):
            processed = self.filtered(lambda l: l.picked or l.captured_by_barcode)
            if processed:
                raise ValidationError(_("No está permitido eliminar líneas de movimiento con trabajo confirmado. Contacte a su administrador para corregir este traslado."))
        
        # Audit log for admin deletes
        audit_vals = []
        for line in self:
            if line.picking_id and self.env.user.has_group('alx_stock_transfer_control.group_stock_inventory_admin'):
                audit_vals.append({   
                    'picking_id': line.picking_id.id,
                    'action': 'delete_line',
                    'user_id': self.env.user.id,
                    'product_id': line.product_id.id,
                    'qty_expected': line.move_id.product_uom_qty if line.move_id else 0,
                    'qty_done': line.quantity,
                    'location_id': line.location_id.id,
                    'location_dest_id': line.location_dest_id.id,
                })

        result = super().unlink()
        
        if audit_vals:
            self.env['stock.transfer.audit'].create(audit_vals)

        return result
