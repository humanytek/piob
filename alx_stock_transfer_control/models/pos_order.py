import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _process_order(self, order, existing_order):
        """Inject from_pos_order context so stock move line writes bypass the
        barcode-only restriction for operator-role users.
        """
        _logger.debug("[POS] processing order with from_pos_order context, user=%s", self.env.user.login)
        return super(
            PosOrder, self.with_context(from_pos_order=True)
        )._process_order(order, existing_order)
