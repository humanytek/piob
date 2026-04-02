from odoo import fields, models

class StockTransferAudit(models.Model):
    _name = 'stock.transfer.audit'
    _description = 'Registro de Auditoría de Transferencias'
    _order = 'date desc, id desc'
    _log_access = False  # manage timestamps manually

    picking_id = fields.Many2one('stock.picking', string='Traslado',
        required=True, ondelete='cascade', index=True)

    move_line_id = fields.Many2one('stock.move.line', string='Línea de Movimiento',
        ondelete='set null', index=True)
    
    action = fields.Selection(selection=[
            ('validate_diff', 'Validado con Diferencia'),
            ('manual_entry', 'Captura Manual'),
            ('add_line', 'Línea Agregada Manualmente'),
            ('delete_line', 'Línea Eliminada'),
            ('validate_no_scan', 'Validado sin Escaneo'),
            ('supervisor_override', 'Autorización de Supervisor'),
            ('location_change', 'Ubicación Modificada'),
            ('operation_change', 'Operación Modificada'),
        ], string='Acción', required=True)
    
    user_id = fields.Many2one('res.users', string='Usuario', 
        required=True, default=lambda self: self.env.user, index=True)
    authorized_by_id = fields.Many2one('res.users', string='Autorizado Por', index=True)
    reason = fields.Text(string='Motivo / Nota')
    
    product_id = fields.Many2one('product.product', string='Producto')
    qty_expected = fields.Float(string='Cantidad Esperada', digits='Product Unit of Measure')
    qty_done = fields.Float(string='Cantidad Realizada', digits='Product Unit of Measure')
    location_id = fields.Many2one('stock.location', string='Ubicación de Origen')
    location_dest_id = fields.Many2one('stock.location', string='Ubicación de Destino')
    date = fields.Datetime(string='Fecha',required=True,default=fields.Datetime.now,index=True)
