"""Part 3 adversarial test: cross-tenant supersession attempt.

Simulates an attacker who has learned another tenant's memory record id
(e.g. leaked via logs or a bug elsewhere) and tries to use the new
contradiction-handling supersede path to overwrite that tenant's fact from
a different tenant. The store must refuse this regardless of how the
supersedes_id was obtained.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from s13code.core.memory import MemoryKind, MemoryRecord, MemoryScope, MemoryStore, Principal, SourceRef
from s13code.core.memory.embeddings import DeterministicEmbedder


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = MemoryStore(Path(tmp) / "memory.sqlite", embedder=DeterministicEmbedder(64))

        victim_scope = MemoryScope(tenant_id="tenant-a", project_id="p", user_id="victim")
        attacker_scope = MemoryScope(tenant_id="tenant-b", project_id="p", user_id="attacker")
        principal = Principal("gateway", "gateway")

        victim_fact = store.write(MemoryRecord(
            MemoryKind.FACT, victim_scope, "Victim's secret budget is $500,000.",
            [SourceRef("api://agent/runs", "victim")], principal,
        ))
        print(f"Victim fact written: {victim_fact.id} (tenant-a, status={victim_fact.status})")

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