# Construction Project Estimation

An Odoo 19 module for BOQ-based (Bill of Quantities) cost estimation of construction projects. It models the catalog of materials, labour, and "Abstract of Cost" (A/C) work-item templates, then uses those templates to scale a per-line estimate from a few field-measured dimensions (Ft/In length, breadth, height) into a full material + labour cost breakdown.

- **Module:** `construction_estimation`
- **Tech:** Odoo 19, Python 3.12
- **Author:** Phoe Ku
- **License:** LGPL-3

---

## 1. Domain glossary

| Term | Meaning |
|------|---------|
| **UOM** | Unit of measure (Sqft, Cuft, Bags, Nos, Man-days …). Tagged as `material`, `labour`, or `both`. |
| **Material** | A consumable resource with a default rate and a UOM (e.g. Cement, Bags, 8500). |
| **Labour** | A workforce role with a default rate and a UOM (e.g. Mason, Man-days, 18000). |
| **Abstract of Cost (A/C)** | A reusable work-item template ("Brick wall 9″", "RCC slab"). Holds a *Base Quantity* (e.g. 1000 Sqft) plus the standard material and labour required per that base. Also fixes whether the work item is measured by **area** (`sqft`) or **volume** (`cuft`). |
| **Project Estimate** | A document for one customer/job, containing many lines. Has draft/confirmed/cancelled states and rolls up totals. |
| **Estimation Line** | One BOQ row inside an estimate. Picks an A/C, captures L/B/H in feet+inches, and produces a scaled material/labour breakdown by ratio against the A/C's base. |

---

## 2. Project flow (user perspective)

```
   Configuration                          Operations
   ─────────────                          ──────────
   1. Create UOMs (seeded)
   2. Create Materials   ──┐
   3. Create Labours     ──┤
   4. Build A/C templates ─┘──▶  5. Create Project Estimate
                                       │
                                       ▼
                                 6. Add Estimation Lines
                                       (pick A/C, enter L×B×H)
                                       │
                                       ▼
                                 7. System auto-scales
                                       material + labour rows
                                       │
                                       ▼
                                 8. Confirm + print BOQ PDF
```

### Step-by-step

1. **UOMs** — seeded by `data/construction_uom_data.xml`. Sqft, Cuft, Bags, Nos, Man-days, etc. Add custom ones under *Construction → Configuration*.
2. **Materials** (`Construction → Configuration → Materials`) — each with a UOM and `default_rate`.
3. **Labours** (`Construction → Configuration → Labours`) — same shape as material.
4. **Abstract of Cost** (`Construction → Configuration → Abstract of Cost`):
   - Set `name`, `Base Quantity` (e.g. 1000), `Base UOM` (e.g. Sqft), and **Measurement Type** (`sqft` or `cuft`).
   - Add Material lines: each row's *Std. Qty* is the quantity required per the *Base Quantity*. Example: 4 bags of cement per 1000 Sqft of brick wall.
   - Add Labour lines the same way.
5. **Project Estimate** (`Construction → Estimations → Project Estimates`) — header captures customer, date, notes.
6. **Estimation Line** — for each BOQ row:
   - Pick the **Work Item (A/C)**. The line inherits the A/C's `measurement_type` automatically (read-only).
   - Enter dimensions in feet/inches. Height appears only when `measurement_type = cuft`.
   - The line auto-computes **Area** or **Volume**, sets **Base Qty**, and copies the A/C's material/labour template into detail rows.
   - Each detail row's **Suggested Qty** = `(line.base_qty / template_base_qty) × template_qty`.
7. **Manual override** on any detail row: editing *Manual Qty* flips `is_manual=True` so the row stops auto-recalculating when dimensions change. *Reset to Suggested* clears the override.
8. **Confirm** the estimate and print *Project Estimate (BOQ)* PDF from the print menu.

---

## 3. Code flow & architecture

### 3.1 File map

```
construction_estimation/
├── __manifest__.py            ← module metadata, data file order
├── __init__.py                ← imports models package
├── data/
│   └── construction_uom_data.xml
├── models/
│   ├── __init__.py
│   ├── construction_uom.py    ← construction.uom
│   ├── material.py            ← construction.material
│   ├── labour.py              ← construction.labour
│   ├── abstract_of_cost.py    ← construction.ac + .ac.material + .ac.labour
│   ├── project_estimate.py    ← construction.project.estimate
│   │                            + construction.estimate.line
│   │                            + construction.estimate.line.material
│   │                            + construction.estimate.line.labour
│   └── ir_asset_windows_fix.py ← Windows-safe override of ir.asset._get_paths
├── views/
│   ├── material_views.xml
│   ├── labour_views.xml
│   ├── abstract_of_cost_views.xml
│   ├── project_estimate_views.xml
│   └── menus.xml
├── report/
│   └── project_estimate_report.xml   ← QWeb PDF (BOQ)
├── security/
│   └── ir.model.access.csv
└── README.md
```

### 3.2 Model graph

```
construction.uom
    ▲
    │ uom_id
    │
construction.material ──────────┐
construction.labour  ──────────┐│
                               ▼▼
construction.ac (Abstract of Cost)
  ├── material_line_ids → construction.ac.material
  ├── labour_line_ids   → construction.ac.labour
  └── measurement_type  (sqft | cuft)
        ▲
        │ ac_id (Many2one)
        │
construction.estimate.line
  ├── measurement_type  ◀── related, stored, readonly (= ac_id.measurement_type)
  ├── material_detail_ids → construction.estimate.line.material
  └── labour_detail_ids   → construction.estimate.line.labour
        ▲
        │ estimate_id
        │
construction.project.estimate
```

### 3.3 Computation pipeline

The heart of the module is the chain of `@api.depends` computes that turn raw L/B/H entries into a final amount. For one estimation line:

```
length_ft, length_in, breadth_ft, breadth_in, height_ft, height_in,
manual_qty, measurement_type
        │
        ▼  _compute_dimensions   (project_estimate.py)
area, volume, base_qty
        │
        ▼  _compute_suggested_qty   (per detail row, mat & lab)
suggested_qty   = (base_qty / template_base_qty) × template_qty
        │
        ▼  _compute_quantity   (skipped if is_manual)
quantity        = suggested_qty
        │
        ▼  _compute_amount
amount          = (quantity × rate) / per
        │
        ▼  _compute_totals   (per line)
material_total, labour_total, total_cost
        │
        ▼  _compute_total_cost   (per estimate)
total_material_cost, total_labour_cost, total_cost (Grand Total)
```

Key design points:

- **Stored computes** all the way up — totals are queryable in list views, used for `sum=` aggregates and report performance.
- **`store=True` related field** — `estimate.line.measurement_type = related('ac_id.measurement_type', store=True, readonly=True)`. Changing the A/C's type propagates to all dependent lines without manual sync.
- **Manual override pattern** — `is_manual` boolean shields `quantity` from being overwritten by `_compute_quantity`. `_onchange_quantity` flips the flag whenever the user types a value that diverges from `suggested_qty`.
- **Template copy** — `_populate_details_from_ac` runs on `@api.onchange('ac_id')` and rewrites detail rows with `(5,0,0)` followed by `(0,0,{...})` commands so the user always sees a fresh breakdown when they pick a different work item.

### 3.4 Onchange handlers (UX glue)

Onchange runs only in the form view; it doesn't replace `@api.depends`, it complements it.

| Handler | Trigger | What it does |
|---------|---------|--------------|
| `EstimationLine._onchange_ac_id` | User picks a Work Item | Defaults `uom_id` to *Sqft* / *Cuft* based on A/C's measurement type, then calls `_populate_details_from_ac()` to copy material/labour rows. |
| `EstimationLine._onchange_dimensions` | Any L/B/H/manual_qty edit | Recomputes `base_qty` for instant feedback before save. |
| `*Detail._onchange_quantity` | User edits Manual Qty | Sets `is_manual=True` if the value differs from suggested. |
| `*Detail._onchange_material_id` / `_onchange_labour_id` | Resource picked | Defaults the rate from the resource's `default_rate`. |

### 3.5 Data integrity

- `construction.ac.material` and `construction.ac.labour` enforce one row per (A/C, resource) via `_sql_constraints`.
- `construction.material` and `construction.labour` names are unique.
- `ondelete='cascade'` on parent FKs (estimate→line→detail) so removing an estimate cleans up the whole subtree; `ondelete='restrict'` on resource refs prevents accidental deletion of catalog rows that are in use.

### 3.6 Reporting

`report/project_estimate_report.xml` declares one QWeb-PDF action bound to `construction.project.estimate`. It iterates each line, then nests material and labour detail rows under it with subtotals and a final material / labour / grand-total trio. The print button appears under the form's *Print* dropdown via `binding_model_id`.

### 3.7 Windows compatibility shim

`ir_asset_windows_fix.py` overrides `ir.asset._get_paths` because Odoo's default implementation compares paths case-sensitively, which breaks on Windows when the addons path mixes `c:\…` and `C:\…`. The override normalizes case before the static-prefix check.

---

## 4. Install & upgrade

```bash
# place repo under your Odoo addons path, then:
odoo --addons-path=...,ConstructionProject -d <db> -i construction_estimation

# after pulling schema/field changes:
odoo --addons-path=... -d <db> -u construction_estimation
```

After a pull that changes a field's storage shape (e.g. converting a Selection to a `related` stored field), bump the version in `__manifest__.py` and run `-u construction_estimation` so Odoo refreshes the registry and recomputes stored values.

---

## 5. Extending

- **New measurement type** — add an option to the `measurement_type` Selection on both `construction.ac` and `construction.estimate.line`, then extend `_compute_dimensions` with the new geometry rule.
- **Per-customer pricing** — add a `pricelist_id` on `construction.project.estimate` and override `_compute_amount` on detail models to look up rates instead of pulling from `material.default_rate`.
- **Subcontractor cost** — add a third detail model symmetrical to `construction.estimate.line.labour` and a third notebook page on the line form. Roll its sum into `_compute_totals` alongside material and labour.

---

## 6. Menu reference

```
Construction
├── Estimations
│   └── Project Estimates
└── Configuration
    ├── Abstract of Cost
    ├── Materials
    └── Labours
```
