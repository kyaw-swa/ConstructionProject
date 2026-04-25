from odoo import fields, models


class ConstructionMeasurement(models.Model):
    _name = 'construction.measurement'
    _description = 'Measurement Type'
    _order = 'ac_id, sequence'

    ac_id = fields.Many2one(
        'construction.ac', string='Abstract of Cost',
        required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(string='Type', required=True, help='e.g. F1, F2, RW1, RW2')
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'construction.measurement', string='Parent Measurement',
        ondelete='set null', index=True,
        help='Set when this measurement is a sub-item (e.g. RW1 span under RW1)',
    )
    child_ids = fields.One2many(
        'construction.measurement', 'parent_id', string='Sub-Measurements',
    )
    description = fields.Char()
