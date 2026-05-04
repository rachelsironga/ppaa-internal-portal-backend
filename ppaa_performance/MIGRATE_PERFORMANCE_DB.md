# Create performance_dashboard tables (fix "relation does not exist")

The error `relation "performance_objectives" does not exist` means the performance tables were never created in the `performance_dashboard` database.

Performance models have foreign keys to User (`ppaa_auth.User`, table `auth_user`), so **the `performance_dashboard` database must have auth and `ppaa_auth` tables created first.** The db router allows `auth`, `contenttypes`, `sessions`, `admin`, `token_blacklist`, and `ppaa_auth` to migrate to `performance_dashboard` (see `ppaa_portal/db_router.py`).

**Run in the backend project root with your virtualenv activated.**

1. **Apply all migrations to `performance_dashboard`** (creates `auth_user` and other shared tables, then performance tables):
   ```bash
   python manage.py migrate --database=performance_dashboard
   ```

2. **If you already rolled back and only want to re-apply ppaa_performance:**
   After step 1, if `ppaa_performance.0002` is still pending, it will run in the same command. If you had previously applied 0002 with `--fake` and then rolled back to 0001, step 1 is enough.

After this, uploading an objective should work.
