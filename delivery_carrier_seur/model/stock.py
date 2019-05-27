# © 2015 FactorLibre (http://www.factorlibre.com)
#        Ismael Calvo <ismael.calvo@factorlibre.com>
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import logging

from openerp import models, fields, api, exceptions
from openerp.tools.translate import _
from unidecode import unidecode
from datetime import timedelta
from xml.dom.minidom import parseString

_logger = logging.getLogger(__name__)
try:
    from seur.picking import Picking
except ImportError:
    _logger.debug('Can not `from seur.picking import Picking`.')


FINAL_SEUR_TRACKING_STATES = [
    'ENTREGA EFECTUADA',
    'ENTREGADO EN PUNTO',
    'ENTREGADO CAMBIO SIN RETORNO',
]


class ShippingLabel(models.Model):
    _inherit = 'shipping.label'

    @api.model
    def _get_file_type_selection(self):
        """ To inherit to add file type """
        res = super(ShippingLabel, self)._get_file_type_selection()
        res.append(('txt', 'TXT'))
        res = list(set(res))
        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # seur_service_code = fields.Selection(
    #     selection='_get_seur_services', string='Seur Service Code',
    #     default=False)
    # seur_product_code = fields.Selection(
    #     selection='_get_seur_products', string='Seur Product Code',
    #     default=False)
    # is_change = fields.Boolean(
    #     'Is a change', default=False,
    #     help="Indicates whether it is a change and the carrier must carry a "
    #          "package to the customer and pick up another to bring it back.")
    # is_pickup = fields.Boolean('Is a pickup service', default=False)
    # pickup_date = fields.Date('Pickup Date')
    pickup_morning_hour_from = fields.Selection(selection=[
        ('09:00', '09:00'),
        ('09:30', '09:30'),
        ('10:00', '10:00'),
        ('10:30', '10:30'),
        ('11:00', '11:00'),
        ('11:30', '11:30'),
        ('12:00', '12:00'),
        ('12:30', '12:30'),
        ('13:00', '13:00'),
        ('13:30', '13:30'),
        ('14:00', '14:00')
    ], default='09:00', string='Pickup morning hour from', help="""
        - The 'to' hour has to be greater than 'from'
        - Must have a two hours margin at least.
        - The range can start in the morning and end in the afternoon.

        Examples:
         - Morning from: 10:30 to: 12:30
         - Evening from: 16:00 to 18:00
         or
         - Morning from: 14:00 to: 'empty'
         - Evening from: 'empty' to 16:00""")
    pickup_morning_hour_to = fields.Selection(selection=[
        ('12:00', '12:00'),
        ('12:30', '12:30'),
        ('13:00', '13:00'),
        ('13:30', '13:30'),
        ('14:00', '14:00')
    ], string='Pickup morning hour to')
    pickup_evening_hour_from = fields.Selection(selection=[
        ('16:00', '16:00'),
        ('16:30', '16:30'),
        ('17:00', '17:00'),
        ('17:30', '17:30'),
        ('18:00', '18:00'),
        ('18:30', '18:30'),
        ('19:00', '19:00'),
        ('19:30', '19:30'),
        ('20:00', '20:00')
    ], string='Pickup evening hour from', help="""
        - The 'to' hour has to be greater than 'from'
        - Must have a two hours margin at least.
        - The range can start in the morning and end in the afternoon.

        Examples:
         - Morning from: 10:30 to: 12:30
         - Evening from: 16:00 to 18:00
         or
         - Morning from: 14:00 to: 'empty'
         - Evening from: 'empty' to 16:00""")
    pickup_evening_hour_to = fields.Selection(selection=[
        ('16:00', '16:00'),
        ('16:30', '16:30'),
        ('17:00', '17:00'),
        ('17:30', '17:30'),
        ('18:00', '18:00'),
        ('18:30', '18:30'),
        ('19:00', '19:00'),
        ('19:30', '19:30'),
        ('20:00', '20:00')
    ], default='20:00', string='Pickup evening hour to')
    # pickup_num = fields.Char('Pickup number', readonly=True)
    # pickup_ref = fields.Char('Pickup reference', readonly=True)
    # pickup_amount = fields.Float('Pickup amount', readonly=True)
    # tracking_status = fields.Char('Tracking status', readonly=True)
    # tracking_status_history = fields.Text(
    #     'Tracking status history',
    #     readonly=True)

    @api.multi
    def _get_carrier_tracking_url(self):
        """Get tracking url for Seur."""
        # "http://www.seur.com/seguimiento-online.do?segOnlineIdentificador="
        for picking in self:
            if picking.carrier_id.carrier_type == 'seur':
                if picking.carrier_id.carrier_tracking_web and\
                        picking.carrier_tracking_ref:
                    picking.carrier_tracking_url =\
                        "%s%s" % (
                            picking.carrier_id.carrier_tracking_web,
                            picking.carrier_tracking_ref)
                else:
                    picking.carrier_tracking_url = False
            else:
                super(StockPicking, picking)._get_carrier_tracking_url()

    @api.model
    def create(self, vals):
        res = super(StockPicking, self).create(vals)
        if 'carrier_id' in vals:
            res.carrier_id_change()
        return res

    @api.one
    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if 'carrier_id' in vals:
            self.carrier_id_change()
        return res

    def _get_seur_services(self):
        return self.env['delivery.carrier'].SEUR_SERVICES

    def _get_seur_products(self):
        return self.env['delivery.carrier'].SEUR_PRODUCTS

    @api.onchange('carrier_id')
    def carrier_id_change(self):
        super(StockPicking, self).carrier_id_change()
        if not self.carrier_id or self.carrier_id.carrier_type != 'seur':
            return

    @api.multi
    def check_tracking_status(self):
        self.ensure_one()
        if self.carrier_id.carrier_type == 'seur':
            ref = self.carrier_tracking_ref
            if ref:
                config = self.carrier_id.seur_config_id
                seur_picking = Picking(
                    config.ws_username,
                    config.ws_password,
                    config.vat,
                    config.franchise_code,
                    'Odoo',  # seurid
                    config.integration_code,
                    config.accounting_code
                )
                result = seur_picking.info({'reference': ref})
                res = parseString(result)
                msg = ''
                status = False
                for situations in res.getElementsByTagName('SITUACIONES'):
                    for sit in situations.getElementsByTagName('SITUACION'):
                        date = sit.getElementsByTagName(
                            'FECHA_SITUACION')[0].firstChild.data
                        desc = sit.getElementsByTagName(
                            'DESCRIPCION_CLIENTE')[0].firstChild.data
                        msg += "%s | %s\n" % (date, desc)
                        status = desc

                if status:
                    self.tracking_status_history = msg
                    self.tracking_status = status
            return True
        return super(StockPicking, self).check_tracking_status()

    @api.multi
    def _check_tracking_status_seur_cron(self, days=6):
        picks = self.search([
            ('carrier_type', '=', 'seur'),
            ('carrier_tracking_ref', '!=', False),
            ('tracking_status', 'not in', FINAL_SEUR_TRACKING_STATES),
            ('date_done', '>', fields.Date.to_string(
                fields.Date.from_string(fields.Date.today(self)) -
                timedelta(days=days)))
        ])
        if picks:
            picks.check_tracking_status()

    @api.multi
    def _generate_seur_label(self, package_ids=None):
        self.ensure_one()
        if self.is_pickup:
            if self.pickup_ref or self.pickup_num:
                raise exceptions.Warning(
                    "This pickup service is already created.")
            self._generate_seur_pickup()
            return []
        if not self.carrier_id.seur_config_id:
            raise exceptions.Warning(_('No SEUR Config defined in carrier'))
        if not self.picking_type_id.warehouse_id.partner_id:
            raise exceptions.Warning(
                _('Please define an address in the %s warehouse') % (
                    self.warehouse_id.name))

        config = self.carrier_id.seur_config_id

        seur_context = {
            'printer': 'ZEBRA',
            'printer_model': 'LP2844-Z',
            'ecb_code': '2C',
        }

        if config.file_type == 'pdf':
            seur_context['pdf'] = True

        seur_picking = Picking(
            config.cit_username,
            config.cit_password,
            config.vat,
            config.franchise_code,
            'Odoo',  # seurid
            config.integration_code,
            config.accounting_code,
            is_test_config=config.is_test,
            context=seur_context
        )

        # try:
        #     connect = seur_picking.test_connection()
        #     if connect != 'Connection successfully':
        #         raise exceptions.Warning(
        #             _('Error connecting with SEUR:\n%s') % connect)
        # except HTTPError, e:
        #     raise exceptions.Warning(
        #         _('Error connecting with SEUR try later:\n%s') % e)

        data = self._get_label_data()
        tracking_ref, label, error = seur_picking.create(data)

        if error:
            err_title = 'Error sending label to SEUR'
            err_msg = ''
            try:
                error = error.replace('</erroresEnvio>', '')
                res = parseString(error.encode('ascii', 'replace'))
                err_title = res.getElementsByTagName('main')[0].firstChild.data
                for error_val in res.getElementsByTagName('errorVal'):
                    err_code = error_val.\
                        getElementsByTagName('codigo')[0].firstChild.data
                    err_descr = error_val.\
                        getElementsByTagName('descripcion')[0].firstChild.data
                    err_name = error_val.\
                        getElementsByTagName('nombreCampo')[0].firstChild.data
                    err_msg += "{0} - ({1}, {2})\n".format(
                        err_descr, err_code, err_name
                    )
            except:
                err_msg = err_msg or error
            raise exceptions.Warning(
                _('{0}\n\n{1}').format(err_title, err_msg))

        tracking_num = data['referencia_expedicion']
        self.carrier_tracking_ref = tracking_num

        if config.file_type == 'pdf':
            label = base64.b64decode(label)
        else:
            label = label.replace('CI10', 'CI28').encode()

        return [{
            'name': self.name + '_' + tracking_num + '.' + config.file_type,
            'file': label,
            'file_type': config.file_type
        }]

    def get_service_and_product(self):
        self.ensure_one()
        service_code = False
        product_code = False
        warn_msg = "This picking (%s) has a wrong number of carrier options." \
            " You have to select a product and a service options." % self.name
        if len(self.option_ids) != 2:
            raise exceptions.Warning(warn_msg)
        for option in self.option_ids:
            if option.option_type == 'service':
                service_code = option.code
            if option.option_type == 'product':
                product_code = option.code
        if not service_code or not product_code:
            raise exceptions.Warning(warn_msg)
        return service_code, product_code

    def _get_label_data(self):
        partner = self.partner_id
        partner_name = partner.name
        if not partner.is_company and partner.parent_id:
            partner_name += ', %s' % partner.parent_id.name
        service_code, product_code = self.get_service_and_product()
        if not service_code or not product_code:
            raise exceptions.Warning(_(
                'Please select SEUR service and product codes in picking'))
        international = False
        warehouse = self.picking_type_id and \
            self.picking_type_id.warehouse_id or False

        if self.partner_id and self.partner_id.country_id and \
            self.partner_id.country_id.code and warehouse and \
            warehouse.partner_id and warehouse.partner_id.country_id and \
            warehouse.partner_id.country_id.code and \
            self.partner_id.country_id.code != warehouse.partner_id.\
                country_id.code:
                international = True

        config = self.carrier_id.seur_config_id
        default_weight = config.default_weight
        expedition_ref = "%s%s" % (
            config.accounting_code,
            config.seur_expedition_sequence.next_by_id())

        self.carrier_tracking_ref = False

        data = {
            'servicio': service_code,
            'product': product_code,
            'total_bultos': self.number_of_packages or 1,
            'total_kilos': self.weight or default_weight,
            'peso_bulto': (
                (self.weight or default_weight * (
                    self.number_of_packages or 1)) /
                (self.number_of_packages or 1)),
            'observaciones': self.note or '',
            'referencia_expedicion': expedition_ref,
            'ref_bulto': '',
            'clave_portes': 'F',
            'clave_reembolso': '',
            'valor_reembolso': '',
            'es_cambio': 'S' if self.is_change else 'N',
            'cliente_nombre': partner.name,
            'cliente_direccion': ((partner.street or '') +
                                  (' ' + (partner.street2 or ''))),
            'cliente_tipovia': 'CL',
            'cliente_tnumvia': 'N',
            'cliente_numvia': ' ',
            'cliente_escalera': '',
            'cliente_piso': '',
            'cliente_puerta': '',
            'cliente_poblacion': partner.city,
            'cliente_cpostal': ((partner.zip and
                                 partner.zip.replace(" ", "")) or
                                self.warn(_('ZIP'), _('partner'))),
            'cliente_pais': partner.country_id.code,
            'cliente_email': partner.email or '',
            'cliente_telefono': (partner.mobile or partner.phone or
                                 partner.commercial_partner_id.mobile or
                                 partner.commercial_partner_id.phone),
            'cliente_atencion': (partner.commercial_partner_id.name or
                                 partner.name),
            'id_mercancia': international and '400' or '',
        }
        return data

    def get_pickup_hours(self):
        err_msg = _("""
            PICKUP TIMES ERROR

             - The 'to' hour has to be greater than 'from'
             - Must have a two hours margin at least.
             - The range can start in the morning and end in the afternoon.

            Examples:
             - Morning from: 10:30 to: 12:30
             - Evening from: 16:00 to 18:00
             or
             - Morning from: 14:00 to: 'empty'
             - Evening from: 'empty' to 16:00
            """)
        morn_from = self.pickup_morning_hour_from
        morn_to = self.pickup_morning_hour_to
        even_from = self.pickup_evening_hour_from
        even_to = self.pickup_evening_hour_to
        if not morn_from or not even_to:
            raise exceptions.Warning(err_msg)
        if morn_to and even_from:
            if int(morn_to[:2]) - int(morn_from[:2]) < 2 or \
                    int(even_to[:2]) - int(even_from[:2]) < 2:
                raise exceptions.Warning(err_msg)
        else:
            if int(even_to[:2]) - int(morn_from[:2]) < 2:
                raise exceptions.Warning(err_msg)
        if not morn_to or not even_from:
            morn_to = False
            even_from = False
        return morn_from, morn_to, even_from, even_to

    def _generate_seur_pickup(self):
        self.ensure_one()
        if not self.carrier_id.seur_config_id:
            raise exceptions.Warning(_('No SEUR Config defined in carrier'))
        if not self.picking_type_id.warehouse_id.partner_id:
            raise exceptions.Warning(
                _('Please define an address in the %s warehouse') % (
                    self.warehouse_id.name))

        config = self.carrier_id.seur_config_id

        seur_picking = Picking(
            config.cit_username,
            config.cit_password,
            config.vat,
            config.franchise_code,
            'Odoo',  # seurid
            config.integration_code,
            config.accounting_code,
            ws_username=config.ws_username,
            ws_password=config.ws_password,
            is_test_config=config.is_test
        )

        data = self._get_pickup_data(seur_picking)
        pickup_ref, pickup_num, amount, error_code, error_description = \
            seur_picking.pickup_service(data)
        if error_code:
            raise exceptions.Warning(
                _("Error: %s\n\n%s") % (error_code, error_description))
        self.carrier_tracking_ref = data['num_referencia']
        self.pickup_ref = pickup_ref
        self.pickup_num = pickup_num
        self.pickup_amount = float(amount)
        return True

    @api.multi
    def cancel_shipment(self):
        if self.carrier_type == 'seur' and self.is_pickup:
            return self.cancel_pickup()
        return super(StockPicking, self).cancel_shipment()

    @api.multi
    def cancel_pickup(self):
        if not self.pickup_ref or not self.pickup_num:
            raise exceptions.Warning(
                "The pickup number and reference are both required to cancel "
                "a pickup service.")
        config = self.carrier_id.seur_config_id
        seur_picking = Picking(
            config.cit_username,
            config.cit_password,
            config.vat,
            config.franchise_code,
            'Odoo',  # seurid
            config.integration_code,
            config.accounting_code,
            ws_username=config.ws_username,
            ws_password=config.ws_password,
            is_test_config=config.is_test
        )
        info, error = seur_picking.cancel_pickup(self.pickup_num,
                                                 self.pickup_ref)
        if error:
            raise exceptions.Warning(info)
        self.pickup_ref = False
        self.pickup_num = False
        self.pickup_amount = False

    def _get_pickup_data(self, seur_picking):
        warehouse = self.picking_type_id.warehouse_id and \
            self.picking_type_id.warehouse_id.partner_id
        if not warehouse:
            raise exceptions.Warning(
                "The address for the warehouse '%s' is not defined" % (
                    self.picking_type_id.warehouse_id.name))
        nif_ordenante = self.company_id.vat
        if nif_ordenante and len(nif_ordenante) == 11:
            nif_ordenante = nif_ordenante[-9:]
        elif nif_ordenante and len(nif_ordenante) != 9:
            raise exceptions.Warning('El nif del ordenante no es correcto')

        partner = self.partner_id
        partner_name = partner.name
        if not partner.is_company and partner.parent_id:
            partner_name += ', %s' % partner.parent_id.name
        nif_origen = partner.vat or partner.parent_id.vat or 'ESB00000000'
        if nif_origen and len(nif_origen) == 11:
            nif_origen = nif_origen[-9:]
        elif nif_origen and len(nif_origen) != 9:
            raise exceptions.Warning('El nif del cliente no es correcto')

        pickup_date = fields.Datetime.from_string(self.pickup_date)
        if not pickup_date:
            raise exceptions.Warning('The pickup date has not been set.')
        morn_from, morn_to, even_from, even_to = self.get_pickup_hours()

        pref_tel_ordenante, tel_ordenante = \
            self.get_prefix_and_tel(self.company_id.phone)
        if not tel_ordenante:
            raise exceptions.Warning(
                _("The phone for your company is required"))
        # pref_fax_ordenante, fax_ordenante = \
        #     self.get_prefix_and_tel(self.company_id.fax)
        pref_tel_origen, tel_recogida_origen = \
            self.get_prefix_and_tel(partner.phone or partner.mobile)
        if not tel_recogida_origen:
            raise exceptions.Warning(_("The customer phone is required"))
        pref_tel_destino, tel_destino = self.get_prefix_and_tel(
            warehouse.phone or warehouse.mobile or (
                warehouse.parent_id and (
                    warehouse.parent_id.phone or
                    warehouse.partner_id.mobile)
            ))

        service_code, product_code = self.get_service_and_product()

        config = self.carrier_id.seur_config_id
        ref_num = self.carrier_tracking_ref
        if not ref_num:
            ref_num = "%s%s" % (config.accounting_code,
                                config.seur_expedition_sequence.next_by_id())
        company_seur_data = seur_picking.zip(self.company_id.zip)
        partner_seur_data = seur_picking.zip(partner.zip)
        warehouse_seur_data = seur_picking.zip(warehouse.zip)
        data_partner = {}
        for partner_zip in partner_seur_data:
            city = partner_zip['NOM_POBLACION']
            partner_city = unidecode(partner.city).strip().upper()
            if city == partner_city:
                data_partner = partner_zip
        if not data_partner:
            raise exceptions.Warning(
                _("Province %s the client %s ,not found in the seur system") % (
                    partner.city, partner.name))
        data = {
            'nombre_empresa': self.company_id.name or '',
            'razon_social': self.company_id.name or '',

            'ccc_ordenante': (config.accounting_code + '-' +
                              config.franchise_code),
            'pais_nif_ordenante': self.company_id.country_id.code,
            'nif_ordenante': nif_ordenante,
            'nombre_ordenante': self.company_id.name or '',
            'apellidos_ordenante': '.',
            'cp_ordenante': company_seur_data[0]['CODIGO_POSTAL'],
            'tipo_via_ordenante': 'CL',
            'calle_ordenante':
                self.company_id.street + ' ' +
                self.company_id.street2 if self.company_id.street2 else
                self.company_id.street or '',
            'tipo_num_ordenante': 'N.',
            'num_ordenante': '.',
            'escalera_ordenante': '.',
            'piso_ordenante': '.',
            'puerta_ordenante': '.',
            'poblacion_ordenante': company_seur_data[0]['NOM_POBLACION'] or '',
            'provincia_ordenante':
                company_seur_data[0]['NOM_PROVINCIA'] or '',
            'pais_ordenante': company_seur_data[0]['COD_PAIS_ISO'] or '',
            'idioma_ordenante': self.company_id.country_id.code,
            'pref_fax_ordenante': "34",
            'fax_ordenante': "",
            'mail_ordenante': self.company_id.email or '',
            'pref_tel_ordenante': pref_tel_ordenante,
            'tel_ordenante': tel_ordenante,

            'razon_social_origen': partner.name or '',
            'pais_nif_origen': partner.country_id.code,
            'nif_origen': nif_origen,
            'nombre_origen': partner.name or '',
            'cp_origen': data_partner['CODIGO_POSTAL'],
            'tipo_via_origen': 'CL',
            'calle_origen':
                partner.street + ' ' +
                partner.street2 if partner.street2 else
                partner.street or '',
            'tipo_num_origen': 'IN',
            'num_origen': '.',
            'escalera_origen': '.',
            'piso_origen': '.',
            'puerta_origen': '.',
            'poblacion_origen': data_partner['NOM_POBLACION'] or '',
            'provincia_origen': data_partner['NOM_PROVINCIA'] or '',
            'pais_origen': data_partner['COD_PAIS_ISO'] or '',
            'pref_tel_origen': pref_tel_origen,
            'tel_recogida_origen': tel_recogida_origen,

            'razon_social_destino': warehouse.name or '',
            'nombre_destino': warehouse.name or '',
            'apellidos_destino': '.',
            'cp_destino': warehouse_seur_data[0]['CODIGO_POSTAL'],
            'tipo_via_destino': 'CL',
            'calle_destino':
                warehouse.street + ' ' +
                warehouse.street2 if warehouse.street2 else
                warehouse.street or '',
            'tipo_num_destino': 'IN',
            'num_destino': '.',
            'escalera_destino': '.',
            'piso_destino': '.',
            'puerta_destino': '.',
            'poblacion_destino': warehouse_seur_data[0]['NOM_POBLACION'] or '',
            'provincia_destino': warehouse_seur_data[0]['NOM_PROVINCIA'] or '',
            'pais_destino': warehouse_seur_data[0]['COD_PAIS_ISO'] or '',
            'pref_tel_destino': pref_tel_destino,
            'tel_destino': tel_destino,

            'mercancia': '2',
            'num_bultos': self.number_of_packages if
            self.number_of_packages > 0 else '1',
            'lista_bultos': '1;1;1;1;1/',
            'tipo_porte': 'D',
            'producto': int(product_code),
            'servicio': int(service_code),

            'dia_recogida': '{:%d}'.format(pickup_date),
            'mes_recogida': '{:%m}'.format(pickup_date),
            'anyo_recogida': pickup_date.year,
            'hora_manana_de': self.pickup_morning_hour_from,
            'hora_manana_a': self.pickup_morning_hour_to or '',
            'hora_tarde_de': self.pickup_evening_hour_from or '',
            'hora_tarde_a': self.pickup_evening_hour_to,

            'ultima_recogida_dia': '',
            'tipo_recogida': 'R',
            'tipo_envio': 'N',
            'aviso': 'S',
            'tipo_aviso': 'E',
            'entrega_nave': 'N',
            'entrega_sabado': 'N',
            'num_referencia': ref_num,
            'notas': self.note or '',
            'comprobante_entrega_tipo': '.',
            'entrega_identificador': '.',
            'seur_plus': '.',
            'valor_asegurado': '.',
            'valor_reembolso': '0',
            'valor_declarado': '0'}
        return data

    def get_prefix_and_tel(self, tel):
        if not tel:
            return '34', ''
        tel = tel.replace(' ', '')
        has_prefix = tel.find('+')
        prefix = '34'
        telf = tel
        if has_prefix == 0:
            prefix = tel[1:has_prefix + 3]
            telf = tel[has_prefix + 3:]
        return prefix, telf

    def warn(self, field, for_str):
        raise exceptions.Warning(
            _('Please, enter a %s for %s') % (field, for_str))

    @api.multi
    def generate_shipping_labels(self, package_ids=None):
        """ Add label generation for SEUR """
        self.ensure_one()
        if self.carrier_id.carrier_type == 'seur':
            return self._generate_seur_label(package_ids=package_ids)
        return super(StockPicking, self).generate_shipping_labels(
            package_ids=package_ids)
