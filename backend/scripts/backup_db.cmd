@echo off
rem Runs the Ledgr database backup. Used by Windows Task Scheduler (see BACKUPS.md).
cd /d "%~dp0.."
if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe -m scripts.backup_db %*
) else (
  python -m scripts.backup_db %*
)
