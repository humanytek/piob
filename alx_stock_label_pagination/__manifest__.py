{
    'name': 'ALX Stock — Etiquetas con Paginación',
    'version': '19.0.1.1.0',
    'category': 'Inventory',
    'summary': 'Impresión masiva de etiquetas de inventario con paginación (ZIP, rango y AbstractModel)',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'report/report_actions.xml',
        'report/label_pagination_templates.xml',
        'views/wizard_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
