from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    transfer_audit_ids = fields.One2many('stock.transfer.audit','picking_id',string='Registro de Auditoría',readonly=True)

    user_can_edit_operations = fields.Boolean(compute='_compute_user_can_edit_operations',help='True for supervisors/admins: can edit locations, operation type, and see Validate button.')
    user_can_edit_qty = fields.Boolean(compute='_compute_user_can_edit_qty', help='True only for admins: can edit quantities directly. Operators and supervisors must use the Barcode App.',)

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_user_can_edit_operations(self):
        # Supervisors and admins can edit structural fields (locations, operation type).
        # Operators are excluded: they may only scan via the Barcode App.
        user = self.env.user
        has_permission = user.has_group('alx_stock_transfer_control.group_stock_logistics_supervisor')
        
        for picking in self:
            picking.user_can_edit_operations = has_permission and picking.state != 'done'

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_user_can_edit_qty(self):
        # Only admins can edit quantities directly from the form.
        # Both operators and supervisors must scan via the Barcode App.
        user = self.env.user
        has_permission = user.has_group('alx_stock_transfer_control.group_stock_inventory_admin')
        
        for picking in self:
            picking.user_can_edit_qty = has_permission and picking.state != 'done'

    def _user_can_bypass_barcode_check(self):
        """Supervisors and Admins can validate transfers that have manual entry reasons."""
        if self.env.su:
            return True
        
        return self.env.user.has_group('alx_stock_transfer_control.group_stock_logistics_supervisor')

    def _user_can_bypass_qty_check(self):
        """Only Admins (and sudo) can validate with quantity differences vs. demand."""
        if self.env.su:
            return True
        
        return self.env.user.has_group('alx_stock_transfer_control.group_stock_inventory_admin')

    def _user_is_restricted_operator(self):
        """Return True if the current user is a plain Operator (not supervisor/admin)."""
        if self.env.su:
            return False

        user = self.env.user
        
        if user.has_group('alx_stock_transfer_control.group_stock_logistics_supervisor'):
            return False
        
        return user.has_group('alx_stock_transfer_control.group_stock_operator')

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------
    def write(self, vals):
        """Block structural field changes for Operators. Supervisors and Admins can change anything."""
        protected_fields = {'picking_type_id', 'location_id', 'location_dest_id', 'move_ids_without_package'}

        if protected_fields.intersection(vals.keys()) and self._user_is_restricted_operator():
            # Audit what was attempted
            for picking in self:
                changed = protected_fields.intersection(vals.keys())
                self.env['stock.transfer.audit'].sudo().create({
                    'picking_id': picking.id,
                    'action': 'operation_change' if 'picking_type_id' in changed else 'location_change',
                    'user_id': self.env.user.id,
                    'reason': f'Blocked attempt to change {", ".join(changed)}',
                })

            raise ValidationError(_("No tiene permiso para modificar el tipo de operación o las ubicaciones del traslado. Contacte a su supervisor."))

        return super().write(vals)

    def unlink(self):
        """Only Admins can delete a picking."""
        if not self.env.su and not self.env.user.has_group('alx_stock_transfer_control.group_stock_inventory_admin'):
            raise ValidationError(_("No puede eliminar un traslado. Solo los administradores de inventario pueden realizar esta acción."))
        
        return super().unlink()

    # -------------------------------------------------------------------------
    # Validation helpers
    # -------------------------------------------------------------------------
    def _check_exact_quantities(self):
        """
        Operators: must scan EXACTLY the expected quantity on every move — no skipping allowed.
        Supervisors: may leave moves untouched (qty=0 will create a backorder), but any move
                     that was partially started must have EXACTLY the expected quantity.
                     It's all-or-nothing per product line.
        Admins: can validate with any quantity difference (always audited).
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for picking in self:
            for move in picking.move_ids:
                expected = move.product_uom_qty
                # Only count lines the operator has confirmed ('picked' flag)
                done = sum(move.move_line_ids.filtered('picked').mapped('quantity'))

                # ── Case 1: nothing scanned for this move ─────────────────────
                if float_is_zero(done, precision_digits=precision):
                    if picking._user_can_bypass_barcode_check():
                        # Supervisors and admins can skip a move entirely.
                        # Odoo's standard flow will create a backorder for it.
                        continue
                    else:
                        # Operators must scan every product — skipping is not allowed.
                        raise ValidationError(_(
                            "El producto '%(product)s' no fue escaneado. "
                            "Debe escanear la cantidad exacta antes de validar.",
                            product=move.product_id.display_name,
                        ))

                # ── Case 2: some quantity scanned — must match exactly (or admin) ──
                if float_compare(expected, done, precision_digits=precision) != 0:
                    if picking._user_can_bypass_qty_check():
                        # Admin: audit the difference and allow
                        self.env['stock.transfer.audit'].sudo().create({
                            'picking_id': picking.id,
                            'action': 'validate_diff',
                            'user_id': self.env.user.id,
                            'product_id': move.product_id.id,
                            'qty_expected': expected,
                            'qty_done': done,
                            'authorized_by_id': self.env.user.id,
                            'reason': 'Admin validated with quantity difference.',
                        })
                    else:
                        # Operators and supervisors: partial qty on a started move is forbidden.
                        # Must scan the full demand or leave the move at 0 (backorder).
                        raise ValidationError(_(
                            "Discrepancia de cantidad en el producto '%(product)s': "
                            "esperada %(expected)s, escaneada %(done)s. "
                            "Debe escanear la cantidad exacta o dejar el producto sin escanear para crear un pedido pendiente.",
                            product=move.product_id.display_name,
                            expected=expected,
                            done=done,
                        ))

    def _check_barcode_capture(self):
        """
        Operators/Supervisors: ALL move lines must be captured via the Barcode App.
        Administrators: can validate with manual entries (audited).
        """
        for picking in self:
            # 'picked' means operator confirmed this line is done
            manual_lines = picking.move_line_ids.filtered(lambda l: not l.captured_by_barcode and l.picked)
            
            if not manual_lines:
                continue

            if picking._user_can_bypass_barcode_check():
                # Audit manual entries
                for line in manual_lines:
                    self.env['stock.transfer.audit'].sudo().create({
                        'picking_id': picking.id,
                        'move_line_id': line.id,
                        'action': 'manual_entry',
                        'user_id': self.env.user.id,
                        'product_id': line.product_id.id,
                        'qty_done': line.quantity,
                        'authorized_by_id': self.env.user.id,
                        'reason': line.manual_entry_reason or 'Manual entry by supervisor/admin.',
                    })
            
            else:
                products = ', '.join(manual_lines.mapped('product_id.display_name'))
                raise ValidationError(_(
                    "Los siguientes productos no fueron escaneados con la aplicación de Código de Barras: %(products)s. "
                    "Debe escanear todos los productos antes de validar.",
                    products=products
                ))

    def _check_has_lines(self):
        """Block validation of pickings with no move lines at all."""
        for picking in self:
            if not picking.move_line_ids:
                raise ValidationError(_("El traslado '%(name)s' no tiene líneas para validar. "
                    "Escanee los productos con la aplicación de Código de Barras primero.",
                    name=picking.name))

    # -------------------------------------------------------------------------
    # button_validate override
    # -------------------------------------------------------------------------
    def button_validate(self):
        self._check_has_lines()
        self._check_barcode_capture()
        self._check_exact_quantities()
        return super().button_validate()
