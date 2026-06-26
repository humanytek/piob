# -*- coding: utf-8 -*-
{
    'name': "ALX Purchase PIT",
    'summary': "Extensión de líneas de OC: inicializa ficha de producto nuevo al registrar compra.",
    'description': """
        Agrega campos de categoría y precio de venta en las líneas de orden de compra.
        Al guardar, si el producto es nuevo (costo = 0), propaga los valores al producto
        automáticamente, sin necesidad de editar el producto por separado.
    """,
    'author': "Leonel Gutiérrez",
    'license': 'LGPL-3',
    'category': 'Purchase',
    'version': '19.0.1.0.0',
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
