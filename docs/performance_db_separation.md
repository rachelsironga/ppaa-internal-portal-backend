# Performance Dashboard vs PPAA Portal in pgAdmin

## They are separate databases

In **pgAdmin** you have two different databases:

| Database                     | Purpose                          | Tables |
|-----------------------------|----------------------------------|--------|
| **ppaa_internal_portal**    | Main portal, auth, documents…   | Portal + auth tables only (no `performance_*`) |
| **performance_dashboard_db** | Performance dashboard only       | Only `performance_*` tables      |

The app uses a **database router** so that:

- All performance models (Objectives, Targets, Activities, etc.) read and write to **performance_dashboard_db**.
- All other portal models use **ppaa_internal_portal**.

So in pgAdmin:

1. Expand your server (e.g. localhost).
2. Under **Databases** you see:
   - **ppaa_internal_portal** → main app DB
   - **performance_dashboard_db** → performance-only DB
3. Each is a separate node; they are already separated.

---

## If you see performance_* tables in ppaa_internal_portal

That can happen if migration `0007_performance_tables` was applied to the default DB before the router was in place. To have a clean separation (performance only in `performance_dashboard_db`), you can remove those tables from the portal DB.

**Run this only on the `ppaa_internal_portal` database** (not on performance_dashboard_db):

In pgAdmin: connect to **ppaa_internal_portal** → Query Tool → run:

```sql
-- Drop performance tables from portal DB (only if they exist here)
-- Data in performance_dashboard_db is unchanged.
DROP TABLE IF EXISTS performance_audit_logs CASCADE;
DROP TABLE IF EXISTS performance_activity_documents CASCADE;
DROP TABLE IF EXISTS performance_kpi_actuals CASCADE;
DROP TABLE IF EXISTS performance_quarterly_data CASCADE;
DROP TABLE IF EXISTS performance_activities CASCADE;
DROP TABLE IF EXISTS performance_targets CASCADE;
DROP TABLE IF EXISTS performance_objectives CASCADE;
```

After this:

- **ppaa_internal_portal**: only portal/auth tables.
- **performance_dashboard_db**: all performance_* tables.

No code changes are required; this is just an optional one-time cleanup in pgAdmin so the two databases are clearly separated.
