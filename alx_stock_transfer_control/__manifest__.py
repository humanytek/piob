{
    'name': 'Stock Transfer Control',
    'version': '19.0.0.0.1',
    'category': 'Inventory',
    'summary': 'Strict WMS-style control for internal stock transfers using the Barcode App.',
    'description': """
        Controls who can see and modify internal stock transfers.
        Operators can only scan; supervisors can authorize exceptions;
        admins configure everything. All deviations are audited.

        Features:
        - Barcode-only quantity capture for operators
        - Warehouse-based access control
        - Block manual qty, location, and operation changes for operators
        - Block adding/deleting lines for operators
        - Exact-quantity enforcement (operators cannot validate with differences)
        - Full audit log of exceptions and supervisor overrides
        - Multi-company compatible
    """,
    'author': 'Leonel Gutiérrez',
    'company': 'Arca Labs',
    'maintainer': 'Arca Labs',
    'website': "https://www.arcalabs.com",
    'depends': ['base', 'stock', 'stock_barcode', 'point_of_sale', 'sale_stock'],
    'data': [
        "security/security_groups.xml",
        "security/stock_move_line_rules.xml",
        "security/stock_picking_rules.xml",
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'alx_stock_transfer_control/static/src/components/line_patch.xml',
        ],
    },
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
