{
    'name': 'Construction Cash Flow',
    'version': '19.0.1.0.0',
    'category': 'Construction',
    'summary': 'Normalized cash-flow ledger for construction projects',
    'description': """
Construction Cash Flow
======================
Enterprise, normalized cash-flow module for construction projects:

* One ledger table for ALL projects (no duplicated sheets), keyed by project.
* WBS cost-category master with referential integrity (no free-text codes).
* Cash-holder petty-cash reconciliation (advanced / spent / returned / balance).
* Budget vs Actual vs Committed with variance, via read_group aggregation.
* Approval workflow (draft -> approved -> paid) with full audit trail.
* Pivot / graph analytics: spend-by-category, budget burn (S-curve),
  cash position. MMK locale and UTF-8 (Burmese) support.
""",
    'author': 'Global Connect',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/construction_masters.xml',
        'data/construction_project_data.xml',
        'data/construction.transaction.csv',
        'data/construction.cash.advance.csv',
        'views/construction_cost_category_views.xml',
        'views/construction_cash_holder_views.xml',
        'views/construction_transaction_views.xml',
        'views/construction_budget_views.xml',
        'views/construction_project_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
