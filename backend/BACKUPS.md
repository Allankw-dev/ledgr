# Ledgr backups & restore

Fee records are the one thing you can't rebuild. This is how to keep a copy you control.

## 1. What Supabase gives you
- **Free plan:** Supabase's pricing page lists automatic backups as *not included*. Treat it as **no backups** — a dropped table or a deleted project is gone.
- **Pro plan ($25/mo):** daily backups kept 7 days (restore from Dashboard → Database → Backups). Point-in-time recovery is a paid add-on.
- Either way, keep your own copy too (section 2): it's off Supabase, it survives a deleted project, and you can open it yourself.

## 2. Your own backups (works on any plan)
**One-time setup (Windows):**
1. Install the PostgreSQL command-line tools: download the installer from postgresql.org → Download → Windows (EDB). Choose version **17** (it must be as new as your Supabase database) and tick **only "Command Line Tools"** during install.
2. Make sure `backend\.env` has `DATABASE_URL` set to the **session pooler, postgres-role** string (the same one Render uses). Optionally set `BACKUP_DATABASE_URL` to override it.

**Run a backup:**
```powershell
cd C:\Users\Admin\ledgr\backend
.\venv\Scripts\Activate.ps1
python -m scripts.backup_db
```
It writes `backend\backups\ledgr-<date>.dump`, checks the file is readable and contains tables (a bad file is deleted, never kept), and keeps the newest 14. Options: `--out D:\ledgr-backups`, `--keep 30`.

**Run it automatically every day** (the laptop must be on at that time):
```powershell
schtasks /Create /SC DAILY /ST 20:00 /TN "Ledgr DB backup" /TR "C:\Users\Admin\ledgr\backend\scripts\backup_db.cmd" /F
```
Then open **Task Scheduler** → *Ledgr DB backup* → Properties → Settings → tick **"Run task as soon as possible after a scheduled start is missed"**.

**Keep copies somewhere else too:** copy the newest dump to an external drive or a private cloud folder now and then. A backup that lives only on the machine that broke isn't a backup.

## 3. Restoring (practise this once, before you need it)
Restore into a **new, empty** database — a fresh Supabase project, or a local Postgres — never straight over live data.
```powershell
pg_restore --no-owner --no-acl --dbname "<connection string of the NEW database>" "C:\Users\Admin\ledgr\backend\backups\ledgr-XXXX.dump"
```
- One message — `schema "public" already exists` — is expected and harmless.
- A dump has no database permissions in it. After restoring into a new project, run `sql/enable_rls.sql` in its SQL editor (set the `ledgr_app` password first). That recreates the app role, the row-level security and the append-only audit log.
- Then point the backend's `DATABASE_URL` / `APP_DATABASE_URL` at the new database.

## 4. Keep dumps private
A dump contains every student's and parent's personal details.
- `backups/` and `*.dump` are git-ignored — don't change that, and never upload a dump to GitHub (your repo is public).
- Keep the folder on an encrypted disk (BitLocker) and don't share it.
