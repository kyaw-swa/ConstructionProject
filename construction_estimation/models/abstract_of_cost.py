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
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self._default_currency(),
    )

    @api.model
    def _default_currency(self):
        """Default to Myanmar Kyat (MMK); fall back to the company currency."""
        mmk = self.env.ref('base.MMK', raise_if_not_found=False)
        return mmk or self.env.company.currency_id

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
    currency_id = fields.Many2one(
        related='ac_id.currency_id', store=True, readonly=True,
        string='Currency',
    )
    rate = fields.Monetary(
        currency_field='currency_id',
        help='Standard rate, entered manually (no default/auto-fill).',
    )
    line_cost = fields.Monetary(
        compute='_compute_line_cost', store=True, currency_field='currency_id',
    )

    @api.depends('quantity', 'rate')
    def _compute_line_cost(self):
        for line in self:
            line.line_cost = line.quantity * line.rate

    _ac_material_unique = models.Constraint(
        'unique(ac_id, material_id)',
        'The material already exists on this A/C.',
    )


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
    currency_id = fields.Many2one(
        related='ac_id.currency_id', store=True, readonly=True,
        string='Currency',
    )
    rate = fields.Monetary(
        currency_field='currency_id',
        help='Standard rate, entered manually (no default/auto-fill).',
    )
    line_cost = fields.Monetary(
        compute='_compute_line_cost', store=True, currency_field='currency_id',
    )

    @api.depends('quantity', 'rate')
    def _compute_line_cost(self):
        for line in self:
            line.line_cost = line.quantity * line.rate

    _ac_labour_unique = models.Constraint(
        'unique(ac_id, labour_id)',
        'The labour already exists on this A/C.',
    )
