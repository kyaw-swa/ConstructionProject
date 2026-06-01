from odoo import fields, models, tools


class ConstructionPettyCash(models.Model):
    """Per cash-holder petty-cash reconciliation (read-only SQL view).

    One row per (project, cash holder):
        advanced  - total cash advanced to the holder
        spent     - total expenses the holder paid for
        returned  - cash returned (modelled as negative advances)
        balance   - advanced - spent - returned  (cash still in hand)

    Built as an ``auto=False`` SQL view so it always reflects live data and
    auto-expands -- no stored aggregates, no hardcoded ranges.
    """
    _name = 'construction.petty.cash'
    _description = 'Construction Petty Cash Reconciliation'
    _auto = False
    _rec_name = 'cash_holder_id'

    project_id = fields.Many2one('construction.project', readonly=True)
    cash_holder_id = fields.Many2one('construction.cash.holder', readonly=True)
    advanced = fields.Monetary(readonly=True, currency_field='currency_id')
    returned = fields.Monetary(readonly=True, currency_field='currency_id')
    spent = fields.Monetary(readonly=True, currency_field='currency_id')
    balance = fields.Monetary(
        string='Current Balance', readonly=True, currency_field='currency_id',
    )
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH adv AS (
                    SELECT project_id, cash_holder_id,
                           SUM(CASE WHEN amount_advanced > 0
                                    THEN amount_advanced ELSE 0 END) AS advanced,
                           SUM(CASE WHEN amount_advanced < 0
                                    THEN -amount_advanced ELSE 0 END) AS returned
                    FROM construction_cash_advance
                    GROUP BY project_id, cash_holder_id
                ),
                spt AS (
                    SELECT project_id, paid_by_id AS cash_holder_id,
                           SUM(amount) AS spent
                    FROM construction_transaction
                    WHERE txn_type = 'expense' AND paid_by_id IS NOT NULL
                    GROUP BY project_id, paid_by_id
                ),
                keys AS (
                    SELECT project_id, cash_holder_id FROM adv
                    UNION
                    SELECT project_id, cash_holder_id FROM spt
                )
                SELECT
                    row_number() OVER () AS id,
                    k.project_id,
                    k.cash_holder_id,
                    COALESCE(a.advanced, 0)  AS advanced,
                    COALESCE(a.returned, 0)  AS returned,
                    COALESCE(s.spent, 0)     AS spent,
                    COALESCE(a.advanced, 0) - COALESCE(a.returned, 0)
                        - COALESCE(s.spent, 0) AS balance,
                    p.currency_id,
                    p.company_id
                FROM keys k
                LEFT JOIN adv a
                    ON a.project_id = k.project_id
                   AND a.cash_holder_id = k.cash_holder_id
                LEFT JOIN spt s
                    ON s.project_id = k.project_id
                   AND s.cash_holder_id = k.cash_holder_id
                JOIN construction_project p ON p.id = k.project_id
            )
        """)
