from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    allowed_warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'res_users_allowed_warehouse_rel',
        'user_id',
        'warehouse_id',
        string="Almacenes Permitidos"
    )

    is_stock_transfer_operator = fields.Boolean(
        compute='_compute_is_stock_transfer_operator',
        string='Es Únicamente Operador de Transferencias',
    )

    @api.depends('group_ids')
    def _compute_is_stock_transfer_operator(self):
        get = lambda xid: self.env.ref(xid, raise_if_not_found=False)

        operator_group = get('alx_stock_transfer_control.group_stock_operator')
        supervisor_group = get('alx_stock_transfer_control.group_stock_logistics_supervisor')
        admin_group = get('alx_stock_transfer_control.group_stock_inventory_admin')
        
        for user in self:
            if not operator_group:
                user.is_stock_transfer_operator = False
                continue

            in_operator = operator_group in user.group_ids
            in_supervisor = bool(supervisor_group) and supervisor_group in user.group_ids
            in_admin = bool(admin_group) and admin_group in user.group_ids

            user.is_stock_transfer_operator = in_operator and not in_supervisor and not in_admin

    def write(self, vals):
        res = super().write(vals)
        if 'group_ids' in vals:
            # When a user is promoted to supervisor or admin, warehouse restrictions
            # no longer apply — clear them so the field doesn't hold stale data.
            no_longer_operators = self.filtered(
                lambda u: u.allowed_warehouse_ids and not u.is_stock_transfer_operator
            )
            if no_longer_operators:
                no_longer_operators.write({'allowed_warehouse_ids': [(5, 0, 0)]})
        return res

    def _get_invalidation_fields(self):
        # Include allowed_warehouse_ids so that changing a user's warehouses
        # immediately clears the ir.rule ormcache, keeping record rules in sync.
        return super()._get_invalidation_fields() | {'allowed_warehouse_ids'}