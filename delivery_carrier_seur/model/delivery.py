# © 2015 FactorLibre (http://www.factorlibre.com)
#        Ismael Calvo <ismael.calvo@factorlibre.com>
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp import models, fields, api


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    @api.model
    def _get_carrier_type_selection(self):
        """ Add SEUR carrier type """
        res = super(DeliveryCarrier, self)._get_carrier_type_selection()
        res.append(('seur', 'SEUR'))
        return res

    seur_config_id = fields.Many2one('seur.config', string='SEUR Config')
