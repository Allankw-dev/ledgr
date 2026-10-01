"""
Backs up Ledgr's data (the `public` schema) to a single compressed file.

Usage (from the backend folder):
    python -m scripts.backup_db                  # -> backups/ledgr-YYYYmmdd-HHMMSS.dump
    python -m scripts.backup_db --out D:\\ledgr-backups --keep 30

Needs PostgreSQL's command-line tools (pg_dump / pg_restore), version 15 or newer
and at least as new as your Supabase database. See BACKUPS.md for install,
scheduling and — most important — how to RESTORE.

Which database: BACKUP_DATABASE_URL, else DATABASE_URL (from the environment or
backend/.env). Use the *postgres-role* connection string (the session pooler one
on port 5432), the same as DATABASE_URL on Render.

A dump holds every student's and parent's personal data: keep the folder private
and never commit it (backups/ and *.dump are git-ignored).
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _read_env_file(key: str) -> str | None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def get_database_url() -> str:
    for key in ("BACKUP_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key) or _read_env_file(key)
        if value:
            # SQLAlchemy-style prefix -> plain libpq URL that pg_dump understands
            return re.sub(r"^postgresql\+\w+://", "postgresql://", value)
    sys.exit("No database URL found. Set BACKUP_DATABASE_URL (or DATABASE_URL) in the environment or backend/.env.")


def mask(url: str) -> str:
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:****@", url)


def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":  # PostgreSQL's installer doesn't add itself to PATH
        candidates = glob.glob(rf"C:\Program Files\PostgreSQL\*\bin\{name}.exe")
        if candidates:
            return sorted(candidates, key=lambda p: [int(x) for x in re.findall(r"\d+", p.split("PostgreSQL")[1])[:1]])[-1]
    sys.exit(
        f"Could not find {name}. Install the PostgreSQL command-line tools (see BACKUPS.md) "
        "or add their bin folder to PATH."
    )


def run_backup(out_dir: Path, keep: int) -> Path:
    url = get_database_url()
    pg_dump, pg_restore = find_tool("pg_dump"), find_tool("pg_restore")
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    final = out_dir / f"ledgr-{stamp}.dump"
    partial = out_dir / f"ledgr-{stamp}.dump.partial"  # never mistaken for a good backup

    print(f"Backing up {mask(url)} ...")
    proc = subprocess.run(
        [pg_dump, "--format=custom", "--schema=public", "--no-owner", "--no-acl", f"--file={partial}", f"--dbname={url}"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        partial.unlink(missing_ok=True)
        err = proc.stderr.strip()
        hint = "\nHint: your pg_dump is older than the database — install a newer PostgreSQL client." if "version mismatch" in err else ""
        sys.exit(f"pg_dump failed:\n{err.replace(url, mask(url))}{hint}")

    # Prove the file is readable and actually contains tables, before trusting it.
    check = subprocess.run([pg_restore, "--list", str(partial)], capture_output=True, text=True)
    table_entries = [ln for ln in check.stdout.splitlines() if " TABLE DATA " in ln]
    if check.returncode != 0 or not table_entries or partial.stat().st_size == 0:
        partial.unlink(missing_ok=True)
        sys.exit("Backup file failed verification (unreadable or empty) — it was discarded.")

    partial.rename(final)
    print(f"OK: {final}  ({final.stat().st_size / 1024:.0f} KB, {len(table_entries)} tables)")

    old = sorted(out_dir.glob("ledgr-*.dump"))[:-keep] if keep > 0 else []
    for f in old:
        f.unlink()
    if old:
        print(f"Removed {len(old)} old backup(s); keeping the newest {keep}.")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up the Ledgr database to a compressed dump file.")
    parser.add_argument("--out", default=str(BACKEND_DIR / "backups"), help="folder to write backups to (default: backend/backups)")
    parser.add_argument("--keep", type=int, default=14, help="how many recent backups to keep (default 14, 0 = keep all)")
    args = parser.parse_args()
    run_backup(Path(args.out), args.keep)
