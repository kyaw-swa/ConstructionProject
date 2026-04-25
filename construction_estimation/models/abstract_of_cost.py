from odoo import api, fields, models


class AbstractOfCost(models.Model):
    _name = 'construction.ac'
    _description = 'Abstract of Cost (A/C)'
    _order = 'name'

    name = fields.Char(required=True, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)

    material_line_ids = fields.One2many(
        'construction.ac.material', 'ac_id', string='Material Lines',
    )
    labour_line_ids = fields.One2many(
        'construction.ac.labour', 'ac_id', string='Labour Lines',
    )
    measurement_ids = fields.One2many(
        'construction.measurement', 'ac_id', string='Measurement Types',
    )

    material_count = fields.Integer(compute='_compute_counts')
    labour_count = fields.Integer(compute='_compute_counts')

    @api.depends('material_line_ids', 'labour_line_ids')
    def _compute_counts(self):
        for rec in self:
            rec.material_count = len(rec.material_line_ids)
            rec.labour_count = len(rec.labour_line_ids)

    def get_unit_cost(self):
        """Return total unit cost = sum of all material + labour line costs."""
        self.ensure_one()
        material_cost = sum(
            line.quantity * line.rate for line in self.material_line_ids
        )
        labour_cost = sum(
            line.quantity * line.rate for line in self.labour_line_ids
        )
        return material_cost + labour_cost



class AcMaterialLine(models.Model):
    _name = 'construction.ac.material'
    _description = 'A/C Material Line'
    _order = 'ac_id, sequence'

    ac_id = fields.Many2one(
        'construction.ac', required=True, ondelete='cascade', index=True,
    )
    material_id = fields.Many2one(
        'construction.material', required=True, ondelete='restrict',
    )
    sequence = fields.Integer(default=10)
    quantity = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    unit = fields.Char(related='material_id.unit', store=True)
    rate = fields.Float(
        digits=(16, 4),
        help='Defaults from material; override per A/C if needed.',
    )
    line_cost = fields.Float(compute='_compute_line_cost', store=True, digits=(16, 4))

    @api.depends('quantity', 'rate')
    def _compute_line_cost(self):
        for line in self:
            line.line_cost = line.quantity * line.rate

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            self.rate = self.material_id.default_rate

    _sql_constraints = [
        (
            'ac_material_unique',
            'unique(ac_id, material_id)',
            'The material already exists on this A/C.',
        ),
    ]


class AcLabourLine(models.Model):
    _name = 'construction.ac.labour'
    _description = 'A/C Labour Line'
    _order = 'ac_id, sequence'

    ac_id = fields.Many2one(
        'construction.ac', required=True, ondelete='cascade', index=True,
    )
    labour_id = fields.Many2one(
        'construction.labour', required=True, ondelete='restrict',
    )
    sequence = fields.Integer(default=10)
    quantity = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    unit = fields.Char(related='labour_id.unit', store=True)
    rate = fields.Float(digits=(16, 4))
    line_cost = fields.Float(compute='_compute_line_cost', store=True, digits=(16, 4))

    @api.depends('quantity', 'rate')
    def _compute_line_cost(self):
        for line in self:
            line.line_cost = line.quantity * line.rate

    @api.onchange('labour_id')
    def _onchange_labour_id(self):
        if self.labour_id:
            self.rate = self.labour_id.default_rate

    _sql_constraints = [
        (
            'ac_labour_unique',
            'unique(ac_id, labour_id)',
            'The labour already exists on this A/C.',
        ),
    ]
