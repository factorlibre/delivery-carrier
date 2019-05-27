# © 2015 FactorLibre - Ismael Calvo <ismael.calvo@factorlibre.com>
#   2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Seur Deliveries WebService",
    "summary": "Allows to generate shipping label for SEUR shipments.",
    "version": "11.0.1.0.0",
    "category": "Delivery",
    "website": "http://factorlibre.com",
    "author": "FactorLibre",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "external_dependencies": {
        "python": ['seur'],
    },
    "depends": [
        "delivery",
        "delivery_pickup_change",
        "delivery_tracking_status_history",
        "base_delivery_carrier_label",
        "base_delivery_carrier_label_options_extra"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/delivery_carrier_template_option_data.xml",
        "data/delivery_carrier_seur_crons.xml",
        "view/seur_config_view.xml",
        "view/delivery_view.xml",
        "view/stock_view.xml"
    ]
}
