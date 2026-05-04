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
    reference = fields.Char(
        string='Ref Code',
        help='BOQ reference shown next to the work item, e.g. P1/Sr1(A).',
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

    manual_qty = fields.Float(
        string='Manual Qty', digits=(16, 4),
        help='If set, overrides the computed area/volume as the base quantity.',
    )

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
        string='Base Qty',
        compute='_compute_dimensions', store=True, digits=(16, 4),
    )

    # ── Detail child rows (per-resource breakdown) ────────────────────────────
    material_detail_ids = fields.One2many(
        'construction.estimate.line.material', 'line_id',
        string='Materials',
    )
    labour_detail_ids = fields.One2many(
        'construction.estimate.line.labour', 'line_id',
        string='Labours',
    )

    # ── Totals (rolled up from children) ─────────────────────────────────────
    material_total = fields.Float(
        string='Mat. Total',
        compute='_compute_totals', store=True, digits=(16, 2),
    )
    labour_total = fields.Float(
        string='Lab. Total',
        compute='_compute_totals', store=True, digits=(16, 2),
    )
    total_cost = fields.Float(
        string='Line Total',
        compute='_compute_totals', store=True, digits=(16, 2),
    )

    @api.depends(
        'measurement_id.measurement_type',
        'manual_qty',
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
            elif line.measurement_type == 'sqft':
                line.area = l * b
                line.volume = 0.0
            else:
                line.area = 0.0
                line.volume = 0.0

            if line.manual_qty:
                line.base_qty = line.manual_qty
            elif line.measurement_type == 'cuft':
                line.base_qty = line.volume
            elif line.measurement_type == 'sqft':
                line.base_qty = line.area
            else:
                line.base_qty = 0.0

    @api.depends(
        'material_detail_ids.amount',
        'labour_detail_ids.amount',
    )
    def _compute_totals(self):
        for line in self:
            line.material_total = sum(line.material_detail_ids.mapped('amount'))
            line.labour_total = sum(line.labour_detail_ids.mapped('amount'))
            line.total_cost = line.material_total + line.labour_total

    # ── A/C → detail copy ────────────────────────────────────────────────────
    def _populate_details_from_ac(self):
        """Replace material/labour detail rows with the A/C template.

        Each detail row stores the template's Std. Qty and Base Qty so that
        Suggested Qty can be recomputed live as the line's dimensions change:

            Suggested Qty = (line.base_qty / template_base_qty) * template_qty
        """
        for line in self:
            line.material_detail_ids = [(5, 0, 0)]
            line.labour_detail_ids = [(5, 0, 0)]
            if not line.ac_id:
                continue
            template_base = line.ac_id.base_quantity or 1.0
            mat_cmds = [
                (0, 0, {
                    'sequence': ac_mat.sequence,
                    'material_id': ac_mat.material_id.id,
                    'template_qty': ac_mat.quantity,
                    'template_base_qty': template_base,
                    'rate': ac_mat.rate,
                    'per': 1.0,
                })
                for ac_mat in line.ac_id.material_line_ids
            ]
            lab_cmds = [
                (0, 0, {
                    'sequence': ac_lab.sequence,
                    'labour_id': ac_lab.labour_id.id,
                    'template_qty': ac_lab.quantity,
                    'template_base_qty': template_base,
                    'rate': ac_lab.rate,
                    'per': 1.0,
                })
                for ac_lab in line.ac_id.labour_line_ids
            ]
            if mat_cmds:
                line.material_detail_ids = mat_cmds
            if lab_cmds:
                line.labour_detail_ids = lab_cmds

    def action_recompute_from_ac(self):
        self._populate_details_from_ac()
        return True

    @api.onchange('ac_id')
    def _onchange_ac_id(self):
        self.measurement_id = False
        self.uom_id = False
        self._populate_details_from_ac()

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
                  'height_ft', 'height_in', 'manual_qty')
    def _onchange_dimensions(self):
        for line in self:
            if line.manual_qty:
                line.base_qty = line.manual_qty
                continue
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


class EstimateLineMaterial(models.Model):
    _name = 'construction.estimate.line.material'
    _description = 'Estimation Line — Material Detail'
    _order = 'sequence, id'

    line_id = fields.Many2one(
        'construction.estimate.line', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    reference = fields.Char(string='Ref Code')
    material_id = fields.Many2one(
        'construction.material', required=True, ondelete='restrict',
    )

    # ── Ratio inputs copied from the A/C template ────────────────────────────
    template_qty = fields.Float(
        string='Std. Qty', digits=(16, 4),
        help='Standard quantity from the A/C template (per Template Base Qty).',
    )
    template_base_qty = fields.Float(
        string='Template Base', digits=(16, 4), default=1.0,
        help='Base quantity the Std. Qty is expressed against (e.g. 1000 Sqft).',
    )

    # ── Ratio output ─────────────────────────────────────────────────────────
    suggested_qty = fields.Float(
        string='Suggested Qty',
        compute='_compute_suggested_qty', store=True, digits=(16, 4),
        help='Auto-calculated as (Calculated Qty / Template Base) × Std. Qty.',
    )
    is_manual = fields.Boolean(
        string='Manual Override',
        help='When set, the Quantity below is locked and will not be '
             'recalculated when the parent dimensions change.',
    )
    quantity = fields.Float(
        string='Manual Qty',
        compute='_compute_quantity', store=True, readonly=False, digits=(16, 4),
        help='Quantity used in costing. Defaults to Suggested Qty; edit to '
             'override (which sets Manual Override).',
    )

    uom_id = fields.Many2one(
        'construction.uom', related='material_id.uom_id',
        string='UOM', store=True, readonly=True,
    )
    rate = fields.Float(string='Rate', digits=(16, 4))
    per = fields.Float(
        string='Per', default=1.0, digits=(16, 4),
        help='Rate is "per X" units (e.g. per 100 nos). Defaults to 1.',
    )
    amount = fields.Float(
        string='Amount',
        compute='_compute_amount', store=True, digits=(16, 2),
    )

    @api.depends('line_id.base_qty', 'template_qty', 'template_base_qty')
    def _compute_suggested_qty(self):
        for d in self:
            base = d.template_base_qty or 1.0
            parent_qty = d.line_id.base_qty if d.line_id else 0.0
            d.suggested_qty = (parent_qty / base) * d.template_qty

    @api.depends('suggested_qty', 'is_manual')
    def _compute_quantity(self):
        for d in self:
            if not d.is_manual:
                d.quantity = d.suggested_qty

    @api.depends('quantity', 'rate', 'per')
    def _compute_amount(self):
        for d in self:
            divisor = d.per or 1.0
            d.amount = (d.quantity * d.rate) / divisor

    @api.onchange('quantity')
    def _onchange_quantity(self):
        for d in self:
            if d.quantity and abs(d.quantity - d.suggested_qty) > 1e-6:
                d.is_manual = True

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id and not self.rate:
            self.rate = self.material_id.default_rate

    def action_reset_to_suggested(self):
        for d in self:
            d.is_manual = False
            d.quantity = d.suggested_qty
        return True


class EstimateLineLabour(models.Model):
    _name = 'construction.estimate.line.labour'
    _description = 'Estimation Line — Labour Detail'
    _order = 'sequence, id'

    line_id = fields.Many2one(
        'construction.estimate.line', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    reference = fields.Char(string='Ref Code')
    labour_id = fields.Many2one(
        'construction.labour', required=True, ondelete='restrict',
    )

    template_qty = fields.Float(
        string='Std. Qty', digits=(16, 4),
        help='Standard quantity from the A/C template (per Template Base Qty).',
    )
    template_base_qty = fields.Float(
        string='Template Base', digits=(16, 4), default=1.0,
        help='Base quantity the Std. Qty is expressed against.',
    )

    suggested_qty = fields.Float(
        string='Suggested Qty',
        compute='_compute_suggested_qty', store=True, digits=(16, 4),
        help='Auto-calculated as (Calculated Qty / Template Base) × Std. Qty.',
    )
    is_manual = fields.Boolean(
        string='Manual Override',
        help='When set, the Quantity below is locked and will not be '
             'recalculated when the parent dimensions change.',
    )
    quantity = fields.Float(
        string='Manual Qty',
        compute='_compute_quantity', store=True, readonly=False, digits=(16, 4),
        help='Quantity used in costing. Defaults to Suggested Qty; edit to '
             'override (which sets Manual Override).',
    )

    uom_id = fields.Many2one(
        'construction.uom', related='labour_id.uom_id',
        string='UOM', store=True, readonly=True,
    )
    rate = fields.Float(string='Rate', digits=(16, 4))
    per = fields.Float(
        string='Per', default=1.0, digits=(16, 4),
        help='Rate is "per X" units. Defaults to 1.',
    )
    amount = fields.Float(
        string='Amount',
        compute='_compute_amount', store=True, digits=(16, 2),
    )

    @api.depends('line_id.base_qty', 'template_qty', 'template_base_qty')
    def _compute_suggested_qty(self):
        for d in self:
            base = d.template_base_qty or 1.0
            parent_qty = d.line_id.base_qty if d.line_id else 0.0
            d.suggested_qty = (parent_qty / base) * d.template_qty

    @api.depends('suggested_qty', 'is_manual')
    def _compute_quantity(self):
        for d in self:
            if not d.is_manual:
                d.quantity = d.suggested_qty

    @api.depends('quantity', 'rate', 'per')
    def _compute_amount(self):
        for d in self:
            divisor = d.per or 1.0
            d.amount = (d.quantity * d.rate) / divisor

    @api.onchange('quantity')
    def _onchange_quantity(self):
        for d in self:
            if d.quantity and abs(d.quantity - d.suggested_qty) > 1e-6:
                d.is_manual = True

    @api.onchange('labour_id')
    def _onchange_labour_id(self):
        if self.labour_id and not self.rate:
            self.rate = self.labour_id.default_rate

    def action_reset_to_suggested(self):
        for d in self:
            d.is_manual = False
            d.quantity = d.suggested_qty
        return True
