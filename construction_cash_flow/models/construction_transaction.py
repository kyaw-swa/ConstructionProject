from odoo import api, fields, models


class ConstructionTransaction(models.Model):
    """Single ledger table for ALL projects (no duplicated sheets).

    One row = one income or expense entry. The cost category is a hard FK
    (no free-text codes) and "who paid" is a FK to the cash-holder master.
    Category-wise totals are produced by ``read_group`` aggregation, never by
    fan-out columns or hardcoded ranges.
    """
    _name = 'construction.transaction'
    _description = 'Construction Cash Flow Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date, id'
    _rec_name = 'voucher_no'

    voucher_no = fields.Char(
        string='Voucher No', required=True, copy=False, index=True,
        default=lambda self: '/', tracking=True,
    )
    project_id = fields.Many2one(
        'construction.project', string='Project',
        required=True, ondelete='cascade', index=True, tracking=True,
    )
    date = fields.Date(
        required=True, default=fields.Date.context_today, index=True,
        tracking=True,
    )
    txn_type = fields.Selection(
        [('income', 'Income'), ('expense', 'Expense')],
        string='Type', required=True, default='expense', index=True,
        tracking=True,
    )
    payee_id = fields.Many2one(
        'res.partner', string='Payee / Vendor', tracking=True,
        help="Client for income, vendor/supplier for expense.",
    )
    cost_category_id = fields.Many2one(
        'construction.cost.category', string='Cost Category',
        ondelete='restrict', index=True, tracking=True,
    )
    name = fields.Char(string='Description', required=True, tracking=True)

    qty = fields.Float(string='Qty', default=1.0)
    unit_price = fields.Monetary(string='Unit Price', currency_field='currency_id')
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
        compute='_compute_amount', store=True, readonly=False, tracking=True,
    )
    signed_amount = fields.Monetary(
        string='Signed Amount', currency_field='currency_id',
        compute='_compute_signed_amount', store=True,
        help="+ income, - expense. Used for cash-position aggregation.",
    )

    paid_by_id = fields.Many2one(
        'construction.cash.holder', string='Paid By (Cash Holder)',
        ondelete='restrict', index=True, tracking=True,
    )
    status = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved'), ('paid', 'Paid')],
        string='Status', default='draft', required=True, index=True,
        tracking=True,
    )
    entered_by = fields.Many2one(
        'res.users', string='Entered By', default=lambda self: self.env.user,
        readonly=True, tracking=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'construction_transaction_attachment_rel',
        'transaction_id', 'attachment_id', string='Attachments', copy=False,
    )

    running_balance = fields.Monetary(
        string='Running Balance', currency_field='currency_id',
        compute='_compute_running_balance',
    )
    category_warning = fields.Boolean(
        string='Category Issue', compute='_compute_category_warning',
        store=True,
        help="Set when an expense has no valid cost category linked.",
    )

    company_id = fields.Many2one(related='project_id.company_id', store=True)
    currency_id = fields.Many2one(related='project_id.currency_id', store=True)

    @api.depends('qty', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = (rec.qty or 0.0) * (rec.unit_price or 0.0)

    @api.depends('amount', 'txn_type')
    def _compute_signed_amount(self):
        for rec in self:
            sign = 1.0 if rec.txn_type == 'income' else -1.0
            rec.signed_amount = sign * (rec.amount or 0.0)

    @api.depends('txn_type', 'cost_category_id')
    def _compute_category_warning(self):
        for rec in self:
            rec.category_warning = (
                rec.txn_type == 'expense' and not rec.cost_category_id
            )

    @api.depends(
        'project_id', 'date', 'signed_amount',
        'project_id.transaction_ids.signed_amount',
        'project_id.transaction_ids.date',
    )
    def _compute_running_balance(self):
        cache = {}
        for rec in self:
            if not rec.project_id:
                rec.running_balance = 0.0
                continue
            pid = rec.project_id.id
            if pid not in cache:
                lines = self.search([('project_id', '=', pid)], order='date, id')
                running = 0.0
                snapshot = {}
                for line in lines:
                    running += line.signed_amount
                    snapshot[line.id] = running
                cache[pid] = snapshot
            rec.running_balance = cache[pid].get(rec.id, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('voucher_no', '/') in (False, '/', None):
                vals['voucher_no'] = self.env['ir.sequence'].next_by_code(
                    'construction.transaction'
                ) or '/'
        return super().create(vals_list)

    @api.onchange('txn_type')
    def _onchange_txn_type(self):
        if self.txn_type == 'income':
            self.cost_category_id = False
            self.paid_by_id = False

    # --- approval workflow -------------------------------------------------
    def action_approve(self):
        self.filtered(lambda r: r.status == 'draft').write({'status': 'approved'})

    def action_mark_paid(self):
        self.filtered(lambda r: r.status in ('draft', 'approved')).write(
            {'status': 'paid'}
        )

    def action_reset_draft(self):
        self.write({'status': 'draft'})
