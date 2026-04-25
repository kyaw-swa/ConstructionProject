from odoo import fields, models


class ConstructionMaterial(models.Model):
    _name = 'construction.material'
    _description = 'Construction Material'
    _order = 'name'

    name = fields.Char(required=True, index=True)
    unit = fields.Char(string='Unit of Measure')
    default_rate = fields.Float(digits=(16, 4))
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Material name must be unique.'),
    ]
