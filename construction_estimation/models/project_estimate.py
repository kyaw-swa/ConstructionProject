from odoo import api, fields, models


class ProjectEstimate(models.Model):
    _name = 'construction.project.estimate'
    _description = 'Construction Project Estimate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name'

    name = fields.Char(string='Estimate Name', required=True, tracking=True)
    customer_id = fields.Many2one('res.partner', string='Customer', tracking=True)
    date = fields.Date(default=fields.Date.today, tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')],
        default='draft', tracking=True,
    )
    line_ids = fields.One2many(
        'construction.estimate.line', 'estimate_id', string='Estimation Lines',
    )
    total_material_cost = fields.Float(
        compute='_compute_total_cost', store=True, digits=(16, 2),
        string='Total Material Cost',
    )
    total_labour_cost = fields.Float(
        compute='_compute_total_cost', store=True, digits=(16, 2),
        string='Total Labour Cost',
    )
    total_cost = fields.Float(
        compute='_compute_total_cost', store=True, digits=(16, 2),
        string='Grand Total',
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    @api.depends('line_ids.material_total', 'line_ids.labour_total')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_material_cost = sum(rec.line_ids.mapped('material_total'))
            rec.total_labour_cost = sum(rec.line_ids.mapped('labour_total'))
            rec.total_cost = rec.total_material_cost + rec.total_labour_cost

    def action_confirm(self):
        self.state = 'confirmed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_reset_draft(self):
        self.state = 'draft'

    def action_import_boq(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import BOQ from Excel',
            'res_model': 'construction.import.boq.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_estimate_id': self.id},
        }


class EstimationLine(models.Model):
    _name = 'construction.estimate.line'
    _description = 'Estimation Line'
    _order = 'sequence, id'

    estimate_id = fields.Many2one(
        'construction.project.estimate', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)

    # ── Work item (AC) and measurement context ────────────────────────────────
    ac_id = fields.Many2one(
        'construction.ac', string='Work Item (A/C)',
        required=True, ondelete='restrict',
    )
    measurement_id = fields.Many2one(
        'construction.measurement', string='Measurement Type',
        ondelete='set null',
        domain="[('ac_id', '=', ac_id)]",
    )
    measurement_type = fields.Selection(
        related='measurement_id.measurement_type',
        string='Meas. Type', store=True, readonly=True,
    )
    uom_id = fields.Many2one(
        'construction.uom', string='UOM',
    )

    # ── Dimension inputs (reference only — Ft/In to Decimal conversion) ───────
    length_ft = fields.Float(string='L Ft', digits=(16, 4))
    length_in = fields.Float(string='L In', digits=(16, 4))
    breadth_ft = fields.Float(string='B Ft', digits=(16, 4))
    breadth_in = fields.Float(string='B In', digits=(16, 4))
    height_ft = fields.Float(string='H Ft', digits=(16, 4))
    height_in = fields.Float(string='H In', digits=(16, 4))

    # ── Calculated reference quantities (read-only) ───────────────────────────
    area = fields.Float(
        string='Area (Sqft)',
        compute='_compute_dimensions', store=True, digits=(16, 4),
    )
    volume = fields.Float(
        string='Volume (Cuft)',
        compute='_compute_dimensions', store=True, digits=(16, 4),
    )
    base_qty = fields.Float(
        string='Base Qty (ref)',
        compute='_compute_dimensions', store=True, digits=(16, 4),
    )

    # ── Material section (quantities entered manually by user) ────────────────
    material_qty = fields.Float(string='Mat. Qty', digits=(16, 4))
    material_unit_cost = fields.Float(string='Mat. Rate', digits=(16, 4))
    material_total = fields.Float(
        string='Mat. Total',
        compute='_compute_costs', store=True, digits=(16, 2),
    )

    # ── Labour section (quantities entered manually by user) ──────────────────
    labour_qty = fields.Float(string='Lab. Qty', digits=(16, 4))
    labour_unit_cost = fields.Float(string='Lab. Rate', digits=(16, 4))
    labour_total = fields.Float(
        string='Lab. Total',
        compute='_compute_costs', store=True, digits=(16, 2),
    )

    # ── Grand total ───────────────────────────────────────────────────────────
    total_cost = fields.Float(
        string='Line Total',
        compute='_compute_costs', store=True, digits=(16, 2),
    )

    @api.depends(
        'measurement_id.measurement_type',
        'length_ft', 'length_in',
        'breadth_ft', 'breadth_in',
        'height_ft', 'height_in',
    )
    def _compute_dimensions(self):
        for line in self:
            l = line.length_ft + line.length_in / 12.0
            b = line.breadth_ft + line.breadth_in / 12.0
            h = line.height_ft + line.height_in / 12.0
            if line.measurement_type == 'cuft':
                line.area = 0.0
                line.volume = l * b * h
                line.base_qty = line.volume
            elif line.measurement_type == 'sqft':
                line.area = l * b
                line.volume = 0.0
                line.base_qty = line.area
            else:
                line.area = 0.0
                line.volume = 0.0
                line.base_qty = 0.0

    @api.depends(
        'material_qty', 'material_unit_cost',
        'labour_qty', 'labour_unit_cost',
    )
    def _compute_costs(self):
        for line in self:
            line.material_total = line.material_qty * line.material_unit_cost
            line.labour_total = line.labour_qty * line.labour_unit_cost
            line.total_cost = line.material_total + line.labour_total

    @api.onchange('ac_id')
    def _onchange_ac_id(self):
        self.measurement_id = False
        self.uom_id = False
        if self.ac_id:
            self.material_unit_cost = sum(
                self.ac_id.material_line_ids.mapped('line_cost')
            )
            self.labour_unit_cost = sum(
                self.ac_id.labour_line_ids.mapped('line_cost')
            )
        else:
            self.material_unit_cost = 0.0
            self.labour_unit_cost = 0.0

    @api.onchange('measurement_id')
    def _onchange_measurement_id(self):
        m_type = self.measurement_id.measurement_type if self.measurement_id else False
        if m_type == 'sqft':
            self.uom_id = self.env.ref(
                'construction_estimation.uom_sqft', raise_if_not_found=False,
            )
        elif m_type == 'cuft':
            self.uom_id = self.env.ref(
                'construction_estimation.uom_cuft', raise_if_not_found=False,
            )
        else:
            self.uom_id = False

    @api.onchange('length_ft', 'length_in', 'breadth_ft', 'breadth_in',
                  'height_ft', 'height_in')
    def _onchange_dimensions(self):
        for line in self:
            l = line.length_ft + line.length_in / 12.0
            b = line.breadth_ft + line.breadth_in / 12.0
            h = line.height_ft + line.height_in / 12.0
            m_type = line.measurement_id.measurement_type if line.measurement_id else False
            if m_type == 'cuft':
                line.base_qty = l * b * h
            elif m_type == 'sqft':
                line.base_qty = l * b
            else:
                line.base_qty = 0.0
