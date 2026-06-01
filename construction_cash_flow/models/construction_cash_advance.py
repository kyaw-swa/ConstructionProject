from odoo import fields, models


class ConstructionCashAdvance(models.Model):
    """Cash advanced to a cash holder for a project.

    Maps the spreadsheet's "Advance for Project" (column M) into its own
    normalized table, keyed by project + cash holder.
    """
    _name = 'construction.cash.advance'
    _description = 'Construction Cash Advance'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', default='/', copy=False)
    project_id = fields.Many2one(
        'construction.project', string='Project',
        required=True, ondelete='cascade', index=True,
    )
    cash_holder_id = fields.Many2one(
        'construction.cash.holder', string='Cash Holder',
        required=True, ondelete='restrict', index=True,
    )
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    amount_advanced = fields.Monetary(
        string='Amount Advanced', currency_field='currency_id',
    )
    note = fields.Char()

    company_id = fields.Many2one(related='project_id.company_id', store=True)
    currency_id = fields.Many2one(related='project_id.currency_id', store=True)
