# SPISM — Strategic Performance Management Information System

This app implements the **Strategic Performance Management Information System (SPISM)** (formerly Performance Dashboard). Data is stored in the `performance_dashboard` database (see `ppaa_portal/db_router.py`).

## If you get "relation \"performance_objectives\" does not exist"

The app writes to the **performance_dashboard** database. If that database has no tables yet, you will see this error when saving an objective (or any SPISM entity).

**Fix (run with your virtualenv activated):**

```bash
python manage.py migrate --database=performance_dashboard
```

This creates only the `performance_*` tables (no auth tables needed; SPISM uses the same auth as the portal and stores user ids as integers, like Maoni).

**Check tables:** `python manage.py check_performance_tables` — prints whether the tables exist and reminds you to run the migrate command if not.

## Drop all performance tables and re-run migrations

If the Financial Year table (or any table) is missing, or you want a clean slate:

1. **Drop all tables** in the performance_dashboard database (this removes all `performance_*` tables and migration history for that DB):

   ```bash
   python manage.py drop_performance_tables
   ```
   (Use `--no-input` to skip the confirmation prompt.)

2. **Re-run migrations** to recreate all tables, including `performance_financial_years`:

   ```bash
   python manage.py migrate --database=performance_dashboard
   ```

After this, you should see in pgAdmin (under the performance_dashboard database): `performance_objectives`, `performance_targets`, `performance_activities`, `performance_quarterly_data`, `performance_kpi_actuals`, `performance_activity_documents`, `performance_audit_logs`, `performance_financial_years`, and `django_migrations`.

## Workflow (lifecycle)

1. **Setup** — ICT Admin: financial year, thresholds, users & roles.
2. **Planning** — Head of Planning / Head of Unit: Objectives → Targets (KPI) → Activities; weights; submit for approval.
3. **Approval** — Executive Secretary: Approve or Return with comment.
4. **Implementation** — Head of Unit: Quarterly actuals, KPI actuals, supporting documents.
5. **Calculation** — System: Activity % → Target operational/KPI → Objective % → Institutional % (see `calculations.py`).
6. **Dashboard & Analytics** — Executive/Management: view performance, trends, drill-down.
7. **Reports** — Quarterly, annual, KPI, objective reports.
8. **Audit** — Audit trail and version history.

## Roles (Django Groups)

Assign these groups to users in **Administration > Users & Roles** (internal portal auth module):

- **SPISM Head of Planning**
- **SPISM Head of Unit**
- **SPISM Executive Secretary**
- **SPISM ICT Administrator**
- **SPISM Internal Audit**
- **SPISM Read-Only**

Create the groups if they do not exist:

```bash
python manage.py ensure_spism_groups
python manage.py spism_permissions
```

Role names are defined in `ppaa_performance/constants.py`.

### Permissions (same style as internal portal)

SPISM uses Django `Permission` codenames like the internal portal: **`can_view_*`**, **`can_add_*`**, **`can_edit_*`**, **`can_delete_*`**, plus **`can_approve_spism_*`** for approvals. Examples: `can_view_spism_objective`, `can_edit_spism_target`, `can_approve_spism_planning`.

Running **`python manage.py spism_permissions`** creates those permissions, assigns them to the SPISM role groups, and **migrates legacy `spism_*` codenames off groups** (direct user permissions are not auto-migrated — re-assign in Admin if needed).

## APIs (under `/api/performance-dashboard/`)

- **Planning:** `objectives`, `targets`, `activities` (CRUD); `.../<uid>/approval` (approve/return).
- **Implementation:** `quarterly-data`, `kpi-actuals`, `activity-documents`.
- **Dashboard:** `summary`, `analytics`.
- **SPISM:** `pending-approvals`, `audit-logs`, `reports`, `config`.

## Performance calculation

- **Activity AI%** = (Actual / Planned) × 100 (capped at 100). Stored on `QuarterlyData.computed_ai_percent`.
- **Target operational score** = sum over activities of (AI% × activity weight / 100).
- **Target KPI score** = from `KPIActual.computed_kpi_percent` (direction applied: increase/decrease favorable).
- **Objective score** = sum over targets of (target score × target weight / 100).
- **Institutional performance** = sum over objectives of (objective score × objective weight / 100).

See `ppaa_performance/calculations.py` and the calculation calls in `views.py` (e.g. `_compute_activity_ai_percent`, `_compute_kpi_percent`).
