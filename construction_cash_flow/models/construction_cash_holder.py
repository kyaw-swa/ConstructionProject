from odoo import api, fields, models


class ConstructionCashHolder(models.Model):
    """A person who fronts / holds project cash (e.g. a site manager).

    Replaces the spreadsheet's two hardcoded "who paid" columns (Y / K).
    Adding a third cash holder is now a master-data record, not a new column.
    """
    _name = 'construction.cash.holder'
    _description = 'Construction Cash Holder'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(
        index=True,
        help="Short code as used in the source ledger (e.g. Y, K).",
    )
    user_id = fields.Many2one('res.users', string='Related User')
    partner_id = fields.Many2one('res.partner', string='Related Contact')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)', 'The cash holder code must be unique.',
    )

    @api.model
    def _normalize_code(self, code):
        return (code or '').strip().upper()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = self._normalize_code(vals['code'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = self._normalize_code(vals['code'])
        return super().write(vals)

    @api.model
    def resolve_code(self, raw_code):
        norm = self._normalize_code(raw_code)
        if not norm:
            return self.browse()
        return self.search([('code', '=', norm)], limit=1)
