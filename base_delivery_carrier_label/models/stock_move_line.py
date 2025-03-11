# Copyright 2016 Hpar
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import fields, models
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    weight = fields.Float(digits="Stock Weight", help="Weight of the pack_operation")

    def get_weight(self):
        """Calc and save weight of pack.operations.

        Warning: Type conversion not implemented
                it will return False if at least one uom or uos not in kg
        return:
            the sum of the weight of [self]
        """
        total_weight = 0
        kg = self.env.ref("uom.product_uom_kgm").id
        units = self.env.ref("uom.product_uom_unit").id
        precision_digits = self.env["decimal.precision"].precision_get("Stock Weight")
        allowed = (False, kg, units)
        cant_calc_total = False
        for operation in self:
            product = operation.product_id

            # if not defined we assume it's in kg
            if product.uom_id.id not in allowed:
                _logger.warning(
                    "Type conversion not implemented for product %s", product.id
                )
                cant_calc_total = True
            # reserved_qty may be 0 if you don't set move line
            # individually but directly validate the picking
            qty = operation.qty_done or operation.reserved_qty
            product_total_weight = product.weight * qty

            if (
                float_compare(
                    product_total_weight,
                    operation.weight,
                    precision_rounding=precision_digits,
                )
                != 0
            ):
                operation.weight = product_total_weight

            total_weight += operation.weight

        if cant_calc_total:
            return False
        return total_weight
