"""Part 3 adversarial test: cross-tenant supersession attempt.

Demonstrates the vulnerability this feature would have WITHOUT scope
validation (by writing directly to the database, bypassing the store's
checks), then demonstrates that the actual code path correctly blocks
the same attack.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from s13code.core.memory import MemoryKind, MemoryRecord, MemoryScope, MemoryStore, Principal, SourceRef
from s13code.core.memory.embeddings import DeterministicEmbedder


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "memory.sqlite"
        store = MemoryStore(db_path, embedder=DeterministicEmbedder(64))

        victim_scope = MemoryScope(tenant_id="tenant-a", project_id="p", user_id="victim")
        attacker_scope = MemoryScope(tenant_id="tenant-b", project_id="p", user_id="attacker")
        principal = Principal("gateway", "gateway")

        victim_fact = store.write(MemoryRecord(
            MemoryKind.FACT, victim_scope, "Victim's secret budget is $500,000.",
            [SourceRef("api://agent/runs", "victim")], principal,
        ))
        print(f"Victim fact written: {victim_fact.id} (tenant-a, status={victim_fact.status})")

        # --- BEFORE: simulate what happens with NO scope validation ---
        # Bypass store.write() entirely and write straight to SQLite, as an
        # attacker would if the validation in store.write() did not exist.
        print("\n--- Simulating attack WITHOUT the scope guard (raw DB write) ---")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE records SET status='superseded' WHERE id=?", (victim_fact.id,)
        )
        conn.commit()
        conn.close()
        unguarded_check = store.get(victim_fact.id)
        assert unguarded_check is not None
        print(f"FAIL (expected, this is the vulnerability): victim fact status is now "
              f"'{unguarded_check.status}' -- an attacker who could write directly to "
              f"storage, or call a hypothetical unguarded API, could silently erase "
              f"another tenant's fact.")

        # restore victim fact to current for the real test below
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE records SET status='current' WHERE id=?", (victim_fact.id,))
        conn.commit()
        conn.close()

        # --- AFTER: the actual code path, which IS guarded ---
        print("\n--- Running the real attack through store.write() (the actual, "
              "guarded code path used by remember_explicit) ---")
        forged = MemoryRecord(
            MemoryKind.FACT, attacker_scope, "Victim's secret budget is $1.",
            [SourceRef("api://agent/runs", "attacker")], principal,
            supersedes_id=victim_fact.id,
        )
        try:
            store.write(forged)
            print("FAIL: cross-tenant supersession was NOT blocked -- vulnerability present.")
        except ValueError as exc:
            print(f"PASS: cross-tenant supersession correctly rejected: {exc}")

        reloaded = store.get(victim_fact.id)
        assert reloaded is not None
        assert reloaded.status == "current", f"expected current, got {reloaded.status}"
        print(f"Victim fact confirmed unchanged: status={reloaded.status}")

        store.close()


if __name__ == "__main__":
    main()