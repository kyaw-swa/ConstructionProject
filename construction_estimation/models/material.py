from odoo import api, fields, models


class ConstructionMaterial(models.Model):
    _name = 'construction.material'
    _description = 'Construction Material'
    _order = 'name'

    name = fields.Char(required=True, index=True)
    uom_id = fields.Many2one(
        'construction.uom', string='Unit of Measure',
        domain="[('uom_type', 'in', ['material', 'both'])]",
    )
    default_rate = fields.Float(digits=(16, 4))
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Material name must be unique.'),
    ]
