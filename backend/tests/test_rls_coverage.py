"""Every table must be covered by sql/enable_rls.sql.

guardian_invites (parents' emails and phone numbers) was once missing from that file, which left it readable through
Supabase's public Data API. This fails when a new model/table is added without a line in enable_rls.sql, and when a
table with its own school_id column is enabled but never given a tenant policy.
"""

import re
from pathlib import Path

from app.core.database import Base
import app.models  # noqa: F401
import app.models.ml  # noqa: F401

SQL = (Path(__file__).resolve().parent.parent / "sql" / "enable_rls.sql").read_text()
ENABLED = {m.lower() for m in re.findall(r"ALTER TABLE\s+(\w+)\s+ENABLE ROW LEVEL SECURITY", SQL, re.I)}
POLICIES = {m.lower() for m in re.findall(r"CREATE POLICY\s+\w+\s+ON\s+(\w+)", SQL, re.I)}
# Enabled on purpose with NO policy (deny-all for the app role; only the owner connection touches them).
DENY_ALL = {"refresh_tokens", "school_mpesa_accounts"}  # see the owner-only notes in enable_rls.sql


def test_every_table_has_row_level_security_enabled():
    missing = sorted(set(Base.metadata.tables) - ENABLED)
    assert not missing, f"Add ALTER TABLE ... ENABLE ROW LEVEL SECURITY (and a policy) to sql/enable_rls.sql for: {missing}"


def test_every_table_with_its_own_school_id_has_a_tenant_policy():
    needs = {name for name, t in Base.metadata.tables.items() if "school_id" in t.columns and name not in DENY_ALL}
    missing = sorted(needs - POLICIES)
    assert not missing, f"These tables have a school_id but no CREATE POLICY in sql/enable_rls.sql: {missing}"
