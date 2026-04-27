from odoo import fields, models


class ConstructionUom(models.Model):
    _name = 'construction.uom'
    _description = 'Construction Unit of Measure'
    _order = 'name'

    name = fields.Char(required=True)
    uom_type = fields.Selection(
        [('material', 'Material'), ('labour', 'Labour'), ('both', 'Both')],
        string='Type', default='both', required=True,
    )
    active = fields.Boolean(default=True)
