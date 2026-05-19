from odoo import api, fields, models
from odoo.exceptions import UserError


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

    @api.onchange('line_ids')
    def _onchange_line_ids_renumber(self):
        for i, line in enumerate(self.line_ids, 1):
            line.reference = i

    def _renumber_lines(self):
        for rec in self:
            for i, line in enumerate(rec.line_ids, 1):
                line.reference = i

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._renumber_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'line_ids' in vals:
            self._renumber_lines()
        return res

    def get_bq_summary(self):
        """Aggregate material and labour detail rows across all estimation
        lines, grouped by material_id / labour_id.

        Returns a dict with `materials` and `labours` lists (each row carries
        name, uom, rate, per, total_qty, total_amount) plus subtotals and the
        grand total. Used by the BQ summary report.
        """
        self.ensure_one()
        materials = {}
        for line in self.line_ids:
            for m in line.material_detail_ids:
                key = m.material_id.id
                row = materials.setdefault(key, {
                    'material': m.material_id,
                    'name': m.material_id.name,
                    'uom': m.uom_id.name or '',
                    'rate': m.rate,
                    'per': m.per or 1.0,
                    'total_qty': 0.0,
                    'total_amount': 0.0,
                })
                row['total_qty'] += m.suggested_qty
                row['total_amount'] += m.amount

        labours = {}
        for line in self.line_ids:
            for lab in line.labour_detail_ids:
                key = lab.labour_id.id
                row = labours.setdefault(key, {
                    'labour': lab.labour_id,
                    'name': lab.labour_id.name,
                    'uom': lab.uom_id.name or '',
                    'rate': lab.rate,
                    'per': lab.per or 1.0,
                    'total_qty': 0.0,
                    'total_amount': 0.0,
                })
                row['total_qty'] += lab.suggested_qty
                row['total_amount'] += lab.amount

        material_rows = sorted(materials.values(), key=lambda r: r['name'])
        labour_rows = sorted(labours.values(), key=lambda r: r['name'])
        material_subtotal = sum(r['total_amount'] for r in material_rows)
        labour_subtotal = sum(r['total_amount'] for r in labour_rows)
        return {
            'materials': material_rows,
            'labours': labour_rows,
            'material_subtotal': material_subtotal,
            'labour_subtotal': labour_subtotal,
            'grand_total': material_subtotal + labour_subtotal,
        }

    def action_confirm(self):
        self.state = 'confirmed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_reset_draft(self):
        self.state = 'draft'


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
        'construction.ac', string='Particular',
        required=True, ondelete='restrict',
    )
    reference = fields.Integer(string='No.')
    measurement_type = fields.Selection(
        related='ac_id.measurement_type',
        string='Measurement Type',
        store=True, readonly=True,
    )
    uom_id = fields.Many2one(
        'construction.uom', string='UOM',
    )

    # ── Dimension inputs (reference only — Ft/In to Decimal conversion) ───────
    length_ft = fields.Float(string='L Ft', digits=(16, 2))
    length_in = fields.Float(string='L In', digits=(16, 2))
    breadth_ft = fields.Float(string='B Ft', digits=(16, 2))
    breadth_in = fields.Float(string='B In', digits=(16, 2))
    height_ft = fields.Float(string='H Ft', digits=(16, 2))
    height_in = fields.Float(string='H In', digits=(16, 2))

    # ── Detailed measurement (Detail of Measurement sheet) ────────────────────
    use_detailed_measurement = fields.Boolean(
        string='Use Detailed Measurement',
        help='When enabled, Base Qty is the sum of all measurement rows '
             'across Sections → Sub-elements → Measurement rows, like a '
             'traditional Detail of Measurement sheet. The single-rectangle '
             'L/B/H above becomes informational only.',
    )
    section_ids = fields.One2many(
        'construction.estimate.line.section', 'line_id',
        string='Sections',
    )
    detailed_total = fields.Float(
        string='Detailed Total',
        compute='_compute_detailed_total', store=True, digits=(16, 2),
        help='Sum of all Section subtotals (which roll up Sub-element and '
             'Measurement-row totals).',
    )

    # ── Calculated reference quantities (read-only) ───────────────────────────
    area = fields.Float(
        string='Area (Sqft)',
        compute='_compute_dimensions', store=True, digits=(16, 2),
    )
    volume = fields.Float(
        string='Volume (Cuft)',
        compute='_compute_dimensions', store=True, digits=(16, 2),
    )
    base_qty = fields.Float(
        string='Base Qty',
        compute='_compute_dimensions', store=True, digits=(16, 2),
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

    @api.depends('section_ids.subtotal')
    def _compute_detailed_total(self):
        for line in self:
            line.detailed_total = sum(line.section_ids.mapped('subtotal'))

    @api.depends(
        'measurement_type',
        'length_ft', 'length_in',
        'breadth_ft', 'breadth_in',
        'height_ft', 'height_in',
        'use_detailed_measurement',
        'detailed_total',
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

            if line.use_detailed_measurement:
                line.base_qty = line.detailed_total
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

    def action_copy_sections_from_line(self):
        """Open the copy-structure wizard pre-targeted at this line."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Copy Structure From Another Line',
            'res_model': 'construction.estimate.line.copy.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_target_line_id': self.id,
            },
        }

    @api.onchange('ac_id')
    def _onchange_ac_id(self):
        m_type = self.ac_id.measurement_type if self.ac_id else False
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
        self._populate_details_from_ac()

    @api.onchange('length_ft', 'length_in', 'breadth_ft', 'breadth_in',
                  'height_ft', 'height_in',
                  'use_detailed_measurement', 'detailed_total')
    def _onchange_dimensions(self):
        for line in self:
            if line.use_detailed_measurement:
                line.base_qty = line.detailed_total
                continue
            l = line.length_ft + line.length_in / 12.0
            b = line.breadth_ft + line.breadth_in / 12.0
            h = line.height_ft + line.height_in / 12.0
            if line.measurement_type == 'cuft':
                line.base_qty = l * b * h
            elif line.measurement_type == 'sqft':
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
    material_id = fields.Many2one(
        'construction.material', required=True, ondelete='restrict',
    )

    # ── Ratio inputs copied from the A/C template ────────────────────────────
    template_qty = fields.Float(
        string='Std. Qty', digits=(16, 6),
        help='Standard quantity from the A/C template (per Template Base Qty).',
    )
    template_base_qty = fields.Float(
        string='Template Base', digits=(16, 6), default=1.0,
        help='Base quantity the Std. Qty is expressed against (e.g. 1000 Sqft).',
    )

    # ── Ratio output ─────────────────────────────────────────────────────────
    suggested_qty = fields.Float(
        string='Qty',
        compute='_compute_suggested_qty', store=True, digits=(16, 6),
        help='Auto-calculated as (Base Qty / Template Base) × Std. Qty.',
    )

    uom_id = fields.Many2one(
        'construction.uom', related='material_id.uom_id',
        string='UOM', store=True, readonly=True,
    )
    rate = fields.Float(string='Rate', digits=(16, 2))
    per = fields.Float(
        string='Per', default=1.0, digits=(16, 2),
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

    @api.depends('suggested_qty', 'rate', 'per')
    def _compute_amount(self):
        for d in self:
            divisor = d.per or 1.0
            d.amount = (d.suggested_qty * d.rate) / divisor

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id and not self.rate:
            self.rate = self.material_id.default_rate


class EstimateLineLabour(models.Model):
    _name = 'construction.estimate.line.labour'
    _description = 'Estimation Line — Labour Detail'
    _order = 'sequence, id'

    line_id = fields.Many2one(
        'construction.estimate.line', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    labour_id = fields.Many2one(
        'construction.labour', required=True, ondelete='restrict',
    )

    template_qty = fields.Float(
        string='Std. Qty', digits=(16, 6),
        help='Standard quantity from the A/C template (per Template Base Qty).',
    )
    template_base_qty = fields.Float(
        string='Template Base', digits=(16, 6), default=1.0,
        help='Base quantity the Std. Qty is expressed against.',
    )

    suggested_qty = fields.Float(
        string='Qty',
        compute='_compute_suggested_qty', store=True, digits=(16, 6),
        help='Auto-calculated as (Base Qty / Template Base) × Std. Qty.',
    )

    uom_id = fields.Many2one(
        'construction.uom', related='labour_id.uom_id',
        string='UOM', store=True, readonly=True,
    )
    rate = fields.Float(string='Rate', digits=(16, 2))
    per = fields.Float(
        string='Per', default=1.0, digits=(16, 2),
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

    @api.depends('suggested_qty', 'rate', 'per')
    def _compute_amount(self):
        for d in self:
            divisor = d.per or 1.0
            d.amount = (d.suggested_qty * d.rate) / divisor

    @api.onchange('labour_id')
    def _onchange_labour_id(self):
        if self.labour_id and not self.rate:
            self.rate = self.labour_id.default_rate


# ─────────────────────────────────────────────────────────────────────────────
#  Detailed Measurement: Section → Sub-element → Measurement row
#  Models a traditional Quantity-Surveyor "Detail of Measurement" sheet.
# ─────────────────────────────────────────────────────────────────────────────


class EstimateLineSection(models.Model):
    _name = 'construction.estimate.line.section'
    _description = 'Estimation Line — Detailed Measurement Section'
    _order = 'line_id, sequence, id'

    line_id = fields.Many2one(
        'construction.estimate.line', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Section', required=True,
        help='Free-text group label, e.g. "For Footing", "18\" Thk Wall / In Footing".',
    )
    subelement_ids = fields.One2many(
        'construction.estimate.line.subelement', 'section_id',
        string='Sub-elements',
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal', store=True, digits=(16, 2),
    )

    @api.depends('subelement_ids.subtotal')
    def _compute_subtotal(self):
        for s in self:
            s.subtotal = sum(s.subelement_ids.mapped('subtotal'))


class EstimateLineSubelement(models.Model):
    _name = 'construction.estimate.line.subelement'
    _description = 'Estimation Line — Detailed Measurement Sub-element'
    _order = 'section_id, sequence, id'

    section_id = fields.Many2one(
        'construction.estimate.line.section', required=True,
        ondelete='cascade', index=True,
    )
    line_id = fields.Many2one(
        'construction.estimate.line',
        related='section_id.line_id', store=True, index=True, readonly=True,
    )
    measurement_type = fields.Selection(
        related='line_id.measurement_type', store=True, readonly=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Sub-element', required=True,
        help='Free-text element label, e.g. "F1", "RW2", "FB3 (12x18)".',
    )
    measurement_ids = fields.One2many(
        'construction.estimate.line.measurement', 'subelement_id',
        string='Measurements',
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal', store=True, digits=(16, 2),
        help='Sum of measurement-row Content (deduction is already netted out '
             'of each row\'s Content).',
    )

    @api.depends('measurement_ids.content')
    def _compute_subtotal(self):
        for se in self:
            se.subtotal = sum(se.measurement_ids.mapped('content'))


class EstimateLineMeasurement(models.Model):
    _name = 'construction.estimate.line.measurement'
    _description = 'Estimation Line — Detailed Measurement Row'
    _order = 'subelement_id, sequence, id'

    subelement_id = fields.Many2one(
        'construction.estimate.line.subelement', required=True,
        ondelete='cascade', index=True,
    )
    line_id = fields.Many2one(
        'construction.estimate.line',
        related='subelement_id.line_id', store=True, index=True, readonly=True,
    )
    measurement_type = fields.Selection(
        related='line_id.measurement_type', store=True, readonly=True,
    )
    uom_label = fields.Char(
        string='Unit',
        compute='_compute_uom_label',
    )

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Particular',
        help='Optional row label, e.g. "140\'-0\" Span". Blank is fine.',
    )

    nos = fields.Integer(string='Nos', default=1)
    multiplier = fields.Integer(string='×', default=1)

    length_ft = fields.Float(string='L Ft', digits=(16, 2))
    length_in = fields.Float(string='L In', digits=(16, 2))
    breadth_ft = fields.Float(string='B Ft', digits=(16, 2))
    breadth_in = fields.Float(string='B In', digits=(16, 2))
    height_ft = fields.Float(string='H Ft', digits=(16, 2))
    height_in = fields.Float(string='H In', digits=(16, 2))

    deduction = fields.Float(string='Deduction', default=0.0, digits=(16, 2))

    content = fields.Float(
        string='Content',
        compute='_compute_content', store=True, digits=(16, 2),
    )

    # TODO: cross-row dimension reuse (`source_measurement_id` self-ref) —
    # deferred. Shape: M2o self-ref filtered to same estimate; when set, pull
    # length_ft/in and breadth_ft/in from the source via stored compute; H and
    # deduction stay independent. UI gated behind a per-row toggle so the form
    # stays clean.

    _sql_constraints = [
        (
            'length_in_lt_12',
            'CHECK (length_in >= 0 AND length_in < 12)',
            'Length inches must be in [0, 12).',
        ),
        (
            'breadth_in_lt_12',
            'CHECK (breadth_in >= 0 AND breadth_in < 12)',
            'Breadth inches must be in [0, 12).',
        ),
        (
            'height_in_lt_12',
            'CHECK (height_in >= 0 AND height_in < 12)',
            'Height inches must be in [0, 12).',
        ),
    ]

    @api.depends('measurement_type')
    def _compute_uom_label(self):
        for r in self:
            if r.measurement_type == 'cuft':
                r.uom_label = 'Cft'
            elif r.measurement_type == 'sqft':
                r.uom_label = 'Sft'
            else:
                r.uom_label = ''

    @api.depends(
        'nos', 'multiplier',
        'length_ft', 'length_in',
        'breadth_ft', 'breadth_in',
        'height_ft', 'height_in',
        'deduction', 'measurement_type',
    )
    def _compute_content(self):
        for r in self:
            L = r.length_ft + r.length_in / 12.0
            B = r.breadth_ft + r.breadth_in / 12.0
            raw = (r.nos or 0) * (r.multiplier or 0) * L * B
            if r.measurement_type == 'cuft':
                H = r.height_ft + r.height_in / 12.0
                raw *= H
            r.content = round(raw - (r.deduction or 0.0), 2)


# ─────────────────────────────────────────────────────────────────────────────
#  Wizard: copy section/sub-element skeleton from another line
# ─────────────────────────────────────────────────────────────────────────────


class EstimateLineCopyWizard(models.TransientModel):
    _name = 'construction.estimate.line.copy.wizard'
    _description = 'Copy Detailed-Measurement Structure From Another Line'

    target_line_id = fields.Many2one(
        'construction.estimate.line', required=True, ondelete='cascade',
    )
    target_estimate_id = fields.Many2one(
        'construction.project.estimate',
        related='target_line_id.estimate_id', readonly=True,
    )
    source_line_id = fields.Many2one(
        'construction.estimate.line', string='Copy From',
        required=True, ondelete='cascade',
        domain="[('estimate_id', '=', target_estimate_id),"
               " ('id', '!=', target_line_id),"
               " ('use_detailed_measurement', '=', True)]",
    )
    replace_existing = fields.Boolean(
        string='Replace Existing Sections',
        default=True,
        help='If on, the target line\'s current sections are wiped before '
             'copying. If off, copied sections are appended.',
    )

    def action_copy(self):
        self.ensure_one()
        target = self.target_line_id
        source = self.source_line_id
        if not source.section_ids:
            raise UserError(
                "The selected source line has no sections to copy."
            )
        if self.replace_existing:
            target.section_ids = [(5, 0, 0)]

        section_cmds = []
        for sec in source.section_ids:
            sub_cmds = [
                (0, 0, {
                    'sequence': se.sequence,
                    'name': se.name,
                    # measurement_ids intentionally left empty — names only.
                })
                for se in sec.subelement_ids
            ]
            section_cmds.append((0, 0, {
                'sequence': sec.sequence,
                'name': sec.name,
                'subelement_ids': sub_cmds,
            }))
        target.section_ids = section_cmds
        if not target.use_detailed_measurement:
            target.use_detailed_measurement = True
        return {'type': 'ir.actions.act_window_close'}
