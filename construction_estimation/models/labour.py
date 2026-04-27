from odoo import api, fields, models


class ConstructionLabour(models.Model):
    _name = 'construction.labour'
    _description = 'Construction Labour'
    _order = 'name'

    name = fields.Char(required=True, index=True)
    uom_id = fields.Many2one(
        'construction.uom', string='Unit of Measure',
        domain="[('uom_type', 'in', ['labour', 'both'])]",
    )
    default_rate = fields.Float(digits=(16, 4))
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Labour name must be unique.'),
    ]
