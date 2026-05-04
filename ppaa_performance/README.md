# PPAA Performance Dashboard (Backend)

## Fix: "relation \"performance_objectives\" does not exist"

This error means the database tables for the Performance Dashboard have not been created yet. Run migrations:

**Option 1 – with virtual environment (recommended)**

```bash
cd ppaa-internal-portal-backend
source venv/bin/activate   # or: source .venv/bin/activate
python manage.py migrate ppaa_performance
```

**Option 2 – script (tries to activate venv for you)**

```bash
cd ppaa-internal-portal-backend
chmod +x run_migrate_performance.sh
./run_migrate_performance.sh
```

**Option 3 – Docker**

```bash
docker-compose exec web python manage.py migrate ppaa_performance
# or replace "web" with your Django service name
```

After this, the `performance_objectives`, `performance_targets`, `performance_activities`, and related tables will exist and the error should go away.

---

## Migrations (reference)

From the backend project root, with your virtual environment activated:

```bash
python manage.py migrate ppaa_performance
```

To create new migrations after model changes:

```bash
python manage.py makemigrations ppaa_performance
python manage.py migrate
```

## APIs

- **Objectives/Targets/Activities** – CRUD and list under `/api/performance-dashboard/`
- **Quarterly data, KPI actuals, Activity documents** – CRUD
- **Approval** – `POST .../objectives/<uid>/approval` with `{ "action": "approve"|"return", "comment": "..." }`
- **Summary** – `GET .../summary?financial_year=2024/2025`
- **Analytics (charts)** – `GET .../analytics?financial_year=2024/2025`

## Calculation engine

See `calculations.py` for institutional, objective, target and activity-level formulas (SRS).
