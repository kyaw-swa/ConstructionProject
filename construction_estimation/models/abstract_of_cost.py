from odoo import api, fields, models


class AbstractOfCost(models.Model):
    _name = 'construction.ac'
    _description = 'Abstract of Cost (A/C)'
    _order = 'name'

    name = fields.Char(required=True, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)

    base_quantity = fields.Float(
        string='Base Quantity', digits=(16, 4), default=1.0,
        help='Standard reference quantity for this Work Item, e.g. 1000 (Sqft). '
             'Each Material/Labour Std. Qty below is the amount required to '
             'execute one Base Quantity. The Estimation Line uses the ratio '
             '(Calculated Qty / Base Quantity) to scale these.',
    )
    base_uom_id = fields.Many2one(
        'construction.uom', string='Base UOM',
        help='UOM the Base Quantity is expressed in (typically Sqft or Cuft).',
    )
    measurement_type = fields.Selection(
        [('sqft', 'Sqft (Area)'), ('cuft', 'Cuft (Volume)')],
        string='Measurement Type', default='sqft', required=True,
    )

    material_line_ids = fields.One2many(
        'construction.ac.material', 'ac_id', string='Material Lines',
    )
    labour_line_ids = fields.One2many(
        'construction.ac.labour', 'ac_id', string='Labour Lines',
    )

    material_count = fields.Integer(compute='_compute_counts')
    labour_count = fields.Integer(compute='_compute_counts')

    @api.depends('material_line_ids', 'labour_line_ids')
    def _compute_counts(self):
        for rec in self:
            rec.material_count = len(rec.material_line_ids)
            rec.labour_count = len(rec.labour_line_ids)


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
    quantity = fields.Float(
        string='Std. Qty', digits=(16, 6), default=1.0,
        help='Standard quantity required per the A/C Base Quantity '
             '(e.g. 4 units of this material per 1000 Sqft).',
    )
    uom_id = fields.Many2one(
        'construction.uom', related='material_id.uom_id',
        string='UOM', store=True,
    )
    rate = fields.Float(
        digits=(16, 0),
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
    quantity = fields.Float(
        string='Std. Qty', digits=(16, 6), default=1.0,
        help='Standard labour quantity required per the A/C Base Quantity.',
    )
    uom_id = fields.Many2one(
        'construction.uom', related='labour_id.uom_id',
        string='UOM', store=True,
    )
    rate = fields.Float(digits=(16, 0))
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
