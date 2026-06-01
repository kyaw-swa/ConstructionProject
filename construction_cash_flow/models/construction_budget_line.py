from odoo import api, fields, models


class ConstructionBudgetLine(models.Model):
    """Budget vs Actual vs Committed, per project + cost category.

    Actual and committed amounts are produced with a single ``read_group``
    (the SUMIFS-equivalent) over the transaction table -- they auto-expand as
    rows are added and never depend on hardcoded ranges.
    """
    _name = 'construction.budget.line'
    _description = 'Construction Budget Line'
    _order = 'project_id, cost_category_id'

    project_id = fields.Many2one(
        'construction.project', string='Project',
        required=True, ondelete='cascade', index=True,
    )
    cost_category_id = fields.Many2one(
        'construction.cost.category', string='Cost Category',
        required=True, ondelete='restrict', index=True,
    )
    budget_amount = fields.Monetary(
        string='Budget', currency_field='currency_id',
    )
    actual_amount = fields.Monetary(
        string='Actual (Paid)', currency_field='currency_id',
        compute='_compute_amounts', store=True,
    )
    committed_amount = fields.Monetary(
        string='Committed (Approved)', currency_field='currency_id',
        compute='_compute_amounts', store=True,
    )
    variance = fields.Monetary(
        string='Variance', currency_field='currency_id',
        compute='_compute_amounts', store=True,
        help="Budget - (Actual + Committed).",
    )
    variance_pct = fields.Float(
        string='Variance %', compute='_compute_amounts', store=True,
    )

    company_id = fields.Many2one(related='project_id.company_id', store=True)
    currency_id = fields.Many2one(related='project_id.currency_id', store=True)

    _project_category_uniq = models.Constraint(
        'unique(project_id, cost_category_id)',
        'A budget line for this category already exists on this project.',
    )

    @api.depends(
        'budget_amount', 'cost_category_id', 'project_id',
        'project_id.transaction_ids.amount',
        'project_id.transaction_ids.status',
        'project_id.transaction_ids.cost_category_id',
        'project_id.transaction_ids.txn_type',
    )
    def _compute_amounts(self):
        # Aggregate expenses once per (project, category, status) via read_group.
        pairs = self.filtered(lambda b: b.project_id and b.cost_category_id)
        totals = {}
        if pairs:
            groups = self.env['construction.transaction']._read_group(
                domain=[
                    ('txn_type', '=', 'expense'),
                    ('project_id', 'in', pairs.project_id.ids),
                    ('cost_category_id', 'in', pairs.cost_category_id.ids),
                ],
                groupby=['project_id', 'cost_category_id', 'status'],
                aggregates=['amount:sum'],
            )
            for project, category, status, amount in groups:
                totals[(project.id, category.id, status)] = amount or 0.0
        for rec in self:
            pid = rec.project_id.id
            cid = rec.cost_category_id.id
            actual = totals.get((pid, cid, 'paid'), 0.0)
            committed = totals.get((pid, cid, 'approved'), 0.0)
            rec.actual_amount = actual
            rec.committed_amount = committed
            rec.variance = (rec.budget_amount or 0.0) - (actual + committed)
            rec.variance_pct = (
                ((actual + committed) / rec.budget_amount * 100.0)
                if rec.budget_amount else 0.0
            )
