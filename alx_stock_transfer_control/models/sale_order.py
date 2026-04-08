import logging
from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _check_warehouse_access(self):
        """Raise ValidationError if a plain operator tries to use a warehouse
        outside their allowed_warehouse_ids.

        Logic:
        - Superuser: always allowed.
        - Supervisors / Admins: always allowed (no warehouse restriction).
        - Non-stock users (no operator group): always allowed.
        - Plain operators: must use a warehouse in allowed_warehouse_ids.
          An empty allowed_warehouse_ids means NO warehouse is permitted,
          consistent with how stock picking record rules work.
        """

        if self.env.su:
            return
        
        user = self.env.user
        
        if user.has_group('alx_stock_transfer_control.group_stock_logistics_supervisor'):
            return
        
        if not user.has_group('alx_stock_transfer_control.group_stock_operator'):
            return  # Non-stock users are unrestricted
        
        # Plain operator — enforce allowed_warehouse_ids (empty = no access)
        for order in self:
            if order.warehouse_id not in user.allowed_warehouse_ids:
                _logger.warning("[SALE] operator=%s attempted sale from restricted warehouse=%s order=%s",user.login, order.warehouse_id.name, order.name)
                raise ValidationError(_("No tiene permiso para crear ventas desde el almacén '%(warehouse)s'. Contacte a su supervisor para obtener acceso.", warehouse=order.warehouse_id.display_name))

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    @api.constrains('warehouse_id')
    def _constrains_warehouse_allowed(self):
        self._check_warehouse_access()

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------
    def action_confirm(self):
        self._check_warehouse_access()
        return super().action_confirm()
