from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ConstructionCostCategory(models.Model):
    """WBS cost category master.

    Replaces the spreadsheet's free-text ``Material Code`` column. Every
    transaction references one of these by FK, so a typo can no longer
    silently drop a row out of a total. Codes are normalised (trimmed +
    upper-cased) so trailing-space variants such as ``'Y '`` collapse onto
    the canonical record.
    """
    _name = 'construction.cost.category'
    _description = 'Construction Cost Category (WBS)'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    complete_name = fields.Char(
        compute='_compute_complete_name', store=True, recursive=True,
        string='Full Category',
    )
    parent_id = fields.Many2one(
        'construction.cost.category', string='Parent Category',
        ondelete='restrict', index=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'construction.cost.category', 'parent_id', string='Sub-Categories',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Char()

    _code_uniq = models.Constraint(
        'unique(code)', 'The cost category code must be unique.',
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f'{rec.parent_id.complete_name} / {rec.name}'
            else:
                rec.complete_name = rec.name

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

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if self._has_cycle():
            raise ValidationError('A cost category cannot be its own ancestor.')

    @api.model
    def resolve_code(self, raw_code):
        """Return the category matching a raw (possibly dirty) source code,
        or ``False`` if none matches. Used by the importer and integrity check.
        """
        norm = self._normalize_code(raw_code)
        if not norm:
            return self.browse()
        return self.search([('code', '=', norm)], limit=1)
