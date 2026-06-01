from odoo import api, fields, models


class ConstructionProject(models.Model):
    _name = 'construction.project'
    _description = 'Construction Cash Flow Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'

    name = fields.Char(string='Project Name', required=True, tracking=True)
    code = fields.Char(string='Reference', tracking=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True)
    project_manager_id = fields.Many2one(
        'res.users', string='Project Manager',
        default=lambda self: self.env.user, tracking=True,
    )
    start_date = fields.Date(default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True,
    )
    color = fields.Integer(default=0)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('on_hold', 'On Hold'),
            ('done', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft', tracking=True, required=True,
    )
    description = fields.Text()

    transaction_ids = fields.One2many(
        'construction.transaction', 'project_id', string='Transactions',
    )
    budget_line_ids = fields.One2many(
        'construction.budget.line', 'project_id', string='Budget Lines',
    )
    advance_ids = fields.One2many(
        'construction.cash.advance', 'project_id', string='Cash Advances',
    )

    # Headline budget = sum of budget lines (single source of truth).
    planned_budget = fields.Monetary(
        string='Planned Budget', currency_field='currency_id',
        compute='_compute_budget', store=True,
    )

    total_income = fields.Monetary(
        compute='_compute_cash', store=True, currency_field='currency_id',
        string='Total Income',
    )
    total_expense = fields.Monetary(
        compute='_compute_cash', store=True, currency_field='currency_id',
        string='Total Expense',
    )
    cash_position = fields.Monetary(
        compute='_compute_cash', store=True, currency_field='currency_id',
        string='Cash Position', help="Income - Expense.",
    )
    committed_expense = fields.Monetary(
        compute='_compute_cash', store=True, currency_field='currency_id',
        string='Committed (Approved)',
    )
    budget_used_percent = fields.Float(
        compute='_compute_cash', store=True, string='Budget Used (%)',
    )

    transaction_count = fields.Integer(compute='_compute_counts')
    advance_total = fields.Monetary(
        compute='_compute_counts', currency_field='currency_id',
        string='Total Advanced',
    )

    @api.depends('budget_line_ids.budget_amount')
    def _compute_budget(self):
        for rec in self:
            rec.planned_budget = sum(rec.budget_line_ids.mapped('budget_amount'))

    @api.depends(
        'transaction_ids.signed_amount', 'transaction_ids.txn_type',
        'transaction_ids.amount', 'transaction_ids.status', 'planned_budget',
    )
    def _compute_cash(self):
        # One read_group across the ledger: income vs expense, plus committed.
        data = {}
        if self.ids:
            groups = self.env['construction.transaction']._read_group(
                domain=[('project_id', 'in', self.ids)],
                groupby=['project_id', 'txn_type', 'status'],
                aggregates=['amount:sum'],
            )
            for project, txn_type, status, amount in groups:
                amount = amount or 0.0
                d = data.setdefault(project.id, {'income': 0.0, 'expense': 0.0, 'committed': 0.0})
                if txn_type == 'income':
                    d['income'] += amount
                else:
                    d['expense'] += amount
                    if status == 'approved':
                        d['committed'] += amount
        for rec in self:
            d = data.get(rec.id, {'income': 0.0, 'expense': 0.0, 'committed': 0.0})
            rec.total_income = d['income']
            rec.total_expense = d['expense']
            rec.committed_expense = d['committed']
            rec.cash_position = d['income'] - d['expense']
            rec.budget_used_percent = (
                (d['expense'] / rec.planned_budget * 100.0)
                if rec.planned_budget else 0.0
            )

    @api.depends('transaction_ids', 'advance_ids.amount_advanced')
    def _compute_counts(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)
            rec.advance_total = sum(rec.advance_ids.mapped('amount_advanced'))

    # --- state workflow ----------------------------------------------------
    def action_set_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_set_on_hold(self):
        self.write({'state': 'on_hold'})

    def action_set_done(self):
        self.write({'state': 'done'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_set_cancelled(self):
        self.write({'state': 'cancelled'})

    def action_open_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'construction.transaction',
            'view_mode': 'list,form,pivot,graph',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
