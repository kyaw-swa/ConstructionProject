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
    default_rate = fields.Float(
        digits=(16, 4), string='Reference Rate',
        help='Informational reference only. NOT auto-applied to A/C or '
             'estimation lines — rates are entered manually there.',
    )
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        'unique(name)', 'Material name must be unique.',
    )
