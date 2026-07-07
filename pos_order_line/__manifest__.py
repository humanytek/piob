{
    "name": "PoS Order ALX",
    "version": "19.0.1.0.0",
    "author": "Arca Labs",
    'summary': 'This module helps to fix and add pos functionalities.',
    'description': """This module provides fixes for the PoS order functionalities.
    - We get the product name in the order line as per the current language of the user. This is done by adding a computed field to the pos.order.line model that retrieves the product name in the user's language.
    """,
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
    ],
    "data": [
        "views/pos_order_line.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
