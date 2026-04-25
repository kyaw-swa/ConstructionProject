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
    total_cost = fields.Float(
        compute='_compute_total_cost', store=True, digits=(16, 2),
    )
    notes = fields.Text()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    @api.depends('line_ids.total_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(rec.line_ids.mapped('total_cost'))

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
    unit = fields.Char(string='Unit')
    ac_id = fields.Many2one(
        'construction.ac', string='Abstract of Cost',
        required=True, ondelete='restrict',
    )
    measurement_id = fields.Many2one(
        'construction.measurement', string='Measurement Type',
        ondelete='set null',
        domain="[('ac_id', '=', ac_id)]",
    )
    quantity = fields.Float(digits=(16, 4), default=1.0)

    # ── Computed breakdown (read-only, not stored as columns) ───────────────
    unit_material_cost = fields.Float(
        compute='_compute_costs', digits=(16, 4),
    )
    unit_labour_cost = fields.Float(
        compute='_compute_costs', digits=(16, 4),
    )
    unit_cost = fields.Float(
        compute='_compute_costs', digits=(16, 4),
    )
    total_cost = fields.Float(
        compute='_compute_costs', store=True, digits=(16, 2),
    )

    @api.depends('ac_id', 'ac_id.material_line_ids.line_cost',
                 'ac_id.labour_line_ids.line_cost', 'quantity')
    def _compute_costs(self):
        for line in self:
            if line.ac_id:
                mat = sum(line.ac_id.material_line_ids.mapped('line_cost'))
                lab = sum(line.ac_id.labour_line_ids.mapped('line_cost'))
            else:
                mat = lab = 0.0
            line.unit_material_cost = mat
            line.unit_labour_cost = lab
            line.unit_cost = mat + lab
            line.total_cost = line.unit_cost * line.quantity

    @api.onchange('ac_id')
    def _onchange_ac_id(self):
        self.measurement_id = False
