# © 2015 FactorLibre (http://www.factorlibre.com)
#        Ismael Calvo <ismael.calvo@factorlibre.com>
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp import fields, models


class SeurConfig(models.Model):
    _name = 'seur.config'

    name = fields.Char('Name', required=True)
    is_test = fields.Boolean('Is a test?', default=False)
    vat = fields.Char('VAT', required=True)
    integration_code = fields.Char('Integration Code', required=True)
    accounting_code = fields.Char('Accounting Code', required=True)
    franchise_code = fields.Char('Franchise Code', required=True)
    cit_username = fields.Char(
        'Username CIT', required=True,
        help="Used for cit.seur.com webservice (generate labels)")
    cit_password = fields.Char(
        'Password CIT', required=True,
        help="Used for cit.seur.com webservice (generate labels)")
    ws_username = fields.Char(
        'Username WS',
        help="Used for ws.seur.com webservice (pickup services)")
    ws_password = fields.Char(
        'Password WS',
        help="Used for ws.seur.com webservice (pickup services)")
    file_type = fields.Selection([
        ('pdf', 'PDF'),
        ('txt', 'TXT')
    ], string="File type", required=True)
    default_weight = fields.Float(
        'Default Weight', default=1,
        help="SEUR requires a default weight of 1. If the product has a "
        "specific weight, will be applied this.")
    seur_expedition_sequence = fields.Many2one('ir.sequence',
                                               "SEUR Expedition Sequence",
                                               required=True)
