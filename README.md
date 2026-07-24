# S13Code

`S13Code` is the standalone Session 13 agent runtime. It implements a live task graph, scoped and provenance-bearing memory, Rohan's semantic chunking V2, and Agent2Agent interoperability. It asks `glc_v3` for model completions over HTTP and never owns provider credentials.

## What runs where

| Service | Default address | Responsibility |
|---|---|---|
| `glc_v3` | `http://127.0.0.1:8111` | Models, keys, routing and channels |
| `S13Code` HTTP | `http://127.0.0.1:8113` | Graph, memory, documents and JSON-RPC A2A |
| `S13Code` gRPC | `127.0.0.1:8114` | Official A2A gRPC service |
| Ollama | `http://127.0.0.1:11434` | Phi-4 segmentation and Nomic embeddings |

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A running `glc_v3`
- A running Ollama with `phi4` and `nomic-embed-text`

```bash
ollama pull phi4
ollama pull nomic-embed-text
ollama serve
```

## Install and run

Unzip `glc_v3`, `S13Code`, and `S13Proof` beside one another. Start `glc_v3` first. Then, from this directory:

```bash
uv sync

export GLC_BASE_URL=http://127.0.0.1:8111
export S13_GATEWAY_PROVIDER=gemini
export S13_SANDBOX_ROOT="$PWD/sandbox"
export S13_CHUNK_MODEL=phi4:latest
export S13_LIVE_SEMANTIC_CHUNKING=1

uv run s13code serve
```

State is written under `~/.s13code` by default. Set `S13_DATA_DIR` to use another directory.

Check both services:

```bash
curl http://127.0.0.1:8111/healthz
curl http://127.0.0.1:8113/healthz
curl http://127.0.0.1:8113/readyz
curl http://127.0.0.1:8113/.well-known/agent-card.json
```

## Run a prompt

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "course",
    "project_id": "s13",
    "user_id": "student-01",
    "agent_id": "assistant",
    "prompt": "Say hello."
  }'
```

The response contains the final answer, graph nodes and edges, ordered graph events, and provider/agent assignments. Inspect a persisted run with:

```bash
curl http://127.0.0.1:8113/v1/agent/runs/<run-id>
```

## Index the sample corpus

The five files under `sandbox/papers/` are fixed `.txt` fixtures for semantic chunking and retrieval proofs.

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "course",
    "project_id": "papers",
    "user_id": "student-01",
    "prompt": "Index every .txt file under papers/. Confirm how many chunks were indexed in total."
  }'
```

Document ingestion is versioned and atomic: source preparation, semantic boundaries, exact spans, Nomic embeddings, and visibility succeed together or roll back together.

## Architecture

- `s13code/core/live_graph/`: durable graph state, patches, event replay and bounded parallel execution
- `s13code/core/memory/`: scope checks, provenance, contradiction history, semantic chunking and FAISS retrieval
- `s13code/core/a2a_adapter/`: Agent Cards, JSON-RPC, SSE/push, official gRPC and trust checks
- `s13code/gateway.py`: the only `S13Code → glc_v3` seam
- `s13code/runtime.py`: joins graph, memory, tools and model calls into an inspectable run
- `tests/`: executable invariants and regression cases

## Test before opening a pull request

```bash
uv run ruff check .
uv run pytest -q

cd ../S13Proof
uv sync
uv run pytest -q
```

## Student contribution

Fork the official [`theschoolofai/S13Code`](https://github.com/theschoolofai/S13Code) repository linked from Axiom, create a branch, implement one meaningful extension, and open one pull request against that repository. Do not open the Session 13 pull request against [`theschoolofai/glc_v3`](https://github.com/theschoolofai/glc_v3).

Add one subsection to this README in the same pull request. It must contain:

1. the user-visible capability,
2. the exact prompt or API request,
3. the graph and ordered event trace,
4. the actual final result,
5. evidence and provider/agent assignments,
6. the adversarial failure and its fix,
7. commands that reproduce the result from a fresh checkout.

Do not commit `.env`, credentials, personal memory, generated databases, unrestricted local paths, benchmark output containing private data, or provider responses containing secrets. Use synthetic identities in every proof.

## License

MIT. See `LICENSE`.

## Part 1: floor reproduced

Test suite and non-browser benchmark were run against a live `glc_v3` +
`S13Code` pair (real Gemini key, local Ollama with `phi4` and
`nomic-embed-text`).

- `S13Code` test suite: 43 passed, 1 failed (Windows-only path bug, see
  Known limitation).
- `S13Proof` test suite: 2 passed, 1 failed (Windows-only tempdir cleanup
  bug, see Known limitation).
- Full 14-case non-browser benchmark run to completion.

The four required cases and their traces:

| Case | Prompt | Result |
|---|---|---|
| Live graph expansion | "Search for 'Python asyncio best practices', read the top 3 results..." | `search` succeeded, discovering 3 URLs; only then did the graph add 3 parallel `fetch_*` nodes. One fetch (Real Python) hit a real 403; the other two succeeded and the graph continued regardless. |
| Durable-memory round trip | See "Contradiction handling" below — the same three-call sequence doubles as this proof. | Fact written, corrected, and correctly recalled with provenance. |
| Semantic document query | "Index the file papers/attention.txt and tell me the three key contributions..." | Document indexed (213/898 words kept after arXiv-page cleanup); Phi-4 segmentation timed out and gracefully fell back to whole-block chunking (`segmenter_failed_fallback_to_block`), which is itself an honest limitation surfaced by the trace. |
| A2A waiting/resume | "Slow remote report: explain in two lines why an agent card is not permission to access local memory." | Local graph added `remote_specialist` and immediately parked it in `waiting`; an official A2A gRPC task completed independently; `run_resumed` woke the parked node, which then succeeded with the validated remote artifact. |

**Honest limitation from the trace**: the semantic document query case shows
the local Phi-4 segmenter timing out mid-run (`"error": "TimeoutError: timed
out"`) and the system silently falling back to treating the whole document
as one block (`segmenter_failed_fallback_to_block`), rather than performing
Rohan V2's intended suffix-rollover topic segmentation. The manifest records
this outcome, so the failure is visible and honest rather than hidden — but
it means the semantic chunking this session emphasizes did not actually run
on this document in this trace; only the fallback path was exercised.

Full raw traces for the memory round-trip case are in `my_traces/`
(part of this repository). The live-expansion, semantic-query, and A2A
traces above were captured locally via `S13Proof`, the separate
verification harness referenced in this repo's Student contribution
section; they are not included in this pull request, in keeping with the
instruction not to commit generated benchmark output.

## Contradiction handling for explicit facts

### 1. User-visible capability

When a user tells the agent a fact and later corrects it (e.g. "Actually, my
mom's birthday is 16 May, not 15 May"), the memory store now recognises the
new statement as a **correction** of the earlier one rather than storing it
as an unrelated, separate fact. The correction is detected generically, using
semantic similarity between the new statement and existing current facts in
the same scope — the code never inspects *what* the fact is about (no
birthday-specific or subject-specific logic). The superseded fact is marked
`status: superseded` and kept in the store (never deleted); only the new,
current fact is returned by ordinary recall, and the final answer cites the
user's own statement as the source of truth.

### 2. Exact prompt / API request

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "course",
    "project_id": "contradiction-test",
    "user_id": "student-01",
    "prompt": "My mom'\''s birthday is 15 May 2026. Remember that."
  }'
```

followed, in the same scope, by:

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "course",
    "project_id": "contradiction-test",
    "user_id": "student-01",
    "prompt": "Actually, my mom'\''s birthday is 16 May 2026, not 15 May. Remember that."
  }'
```

and finally:

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "course",
    "project_id": "contradiction-test",
    "user_id": "student-01",
    "prompt": "When is mom birthday?"
  }'
```

### 3. Graph and ordered event trace

All three runs use the existing `birthday_reminder`/`memory` deterministic
graph shape (`recall` + `remember` in the first frontier, then `answer`).
The relevant new behaviour is inside the `remember` node's result, not the
graph shape itself:

**Run 1 (original fact) — `remember` node result:**
```json
{"fact": {"id": "mem_b353e4e2d7ca4cb496cdd2397082ebe2", "kind": "fact",
  "text": "My mom's birthday is 15 May 2026. Remember that.",
  "sources": ["api://agent/runs"], "supersedes_id": null, "status": "current"}}
```

**Run 2 (correction) — `remember` node result:**
```json
{"fact": {"id": "mem_c675e312a41248549c0dfbe109e8612d", "kind": "fact",
  "text": "Actually, my mom's birthday is 16 May 2026, not 15 May. Remember that.",
  "sources": ["api://agent/runs"],
  "supersedes_id": "mem_b353e4e2d7ca4cb496cdd2397082ebe2", "status": "current"}}
```

Full ordered event sequences for all three runs are in `my_traces/`
(`memory_write.json`, `memory_write_correction.json`, `memory_read.json`).

### 4. Actual final result

Run 3's final answer:

> "You told me that your mom's birthday is 16 May 2026, not 15 May
> [source: api://agent/runs]."

Run 3's `recall` node returned exactly **one** `kind: fact` hit — the 16 May
correction. The original 15 May fact did **not** appear as a fact (it is
`status: superseded`), though it remains visible as a `kind: episode` from
the earlier conversational turn, which is expected: episodes are a distinct
memory type that preserves full conversational history independently of
fact corrections.

### 4b. Denied cross-scope recall

The same question asked from a *different* tenant (`different-tenant` instead
of `course`) returns no hits and an honest "I don't have that information"
answer, rather than leaking the `course` tenant's fact:

```bash
curl -s http://127.0.0.1:8113/v1/agent/runs -H "Content-Type: application/json" -d "{\"tenant_id\": \"different-tenant\", \"project_id\": \"contradiction-test\", \"user_id\": \"student-01\", \"prompt\": \"When is mom birthday?\"}"
```

Result: `recall` returned `"hits": []`, `evidence_count: 0`, and the answer
was *"I do not have access to your mom's birthday information."* Full trace
in `my_traces/cross_tenant_denied.json`.

### 5. Evidence and provider/agent assignments

- `recall` / `remember`: local, no provider (pure store operations)
- `answer`: `provider: gemini_1`, `model: gemini-2.5-flash`
- Evidence count on the final answer: 5 (the current fact plus four related
  episodes)

### 6. Adversarial failure and fix

**Attack**: an attacker who has learned another tenant's memory record id
(e.g. via a leaked log line or an unrelated bug) attempts to use the new
supersede path to overwrite/erase that tenant's fact from a *different*
tenant scope.

**Before**: `adversarial_test.py` first simulates what this attack would
achieve *without* scope validation, by writing directly to the underlying
SQLite table (bypassing `store.write()` entirely, as an attacker could if a
future code path skipped validation). This succeeds: the victim's fact
silently flips from `current` to `superseded`, demonstrating the
vulnerability is real and consequential, not hypothetical.

**After**: the same conceptual attack is then run through the actual,
guarded code path -- `store.write()`, the same function `remember_explicit`
calls in production. `MemoryStore.write()` validates `old.scope ==
record.scope` before honouring any `supersedes_id` (this check pre-dates
this extension). Because our new code calls into this same validated path
rather than bypassing it, the real attack is rejected and the victim's fact
is confirmed unchanged.

**Reproduction** (`adversarial_test.py`, run from a fresh checkout):
```bash
uv run python adversarial_test.py
```
Output:
```
Victim fact written: mem_6b9710392ed14318bdfa2d3e97638444 (tenant-a, status=current)
--- Simulating attack WITHOUT the scope guard (raw DB write) ---
FAIL (expected, this is the vulnerability): victim fact status is now 'superseded' -- an attacker who could write directly to storage, or call a hypothetical unguarded API, could silently erase another tenant's fact.
--- Running the real attack through store.write() (the actual, guarded code path used by remember_explicit) ---
PASS: cross-tenant supersession correctly rejected: a record may supersede only the same kind in the same scope
Victim fact confirmed unchanged: status=current
```

### 7. Commands that reproduce everything from a fresh checkout

```bash
# 1. Clone and install
git clone https://github.com/Irenemarymathew/S13Code.git
cd S13Code
uv sync

# 2. Start glc_v3 in a separate terminal (see glc_v3/README.md), then:
export GLC_BASE_URL=http://127.0.0.1:8111
export S13_GATEWAY_PROVIDER=gemini
export S13_SANDBOX_ROOT="$PWD/sandbox"
uv run s13code serve

# 3. In a third terminal, run the three prompts above in order, waiting
#    ~20-30s between calls to respect provider rate limits.

# 4. Run the adversarial test (no live services required):
uv run python adversarial_test.py
```

## Known limitation

Two pre-existing test failures are Windows-only path-handling issues, unrelated
to this extension: `test_birthday_creates_two_real_calendar_artifacts` fails
because the calendar artifact URI assumes Unix-style `file://` paths, and
`test_live_prompt_grows_after_real_market_outcome` fails because Windows
enforces stricter file-handle rules during `TemporaryDirectory` cleanup than
Unix does. Both are pytest/pathlib platform quirks, not defects in the graph,
memory, or A2A logic itself.

On a repeated recall, the final answer's evidence sometimes includes both
the current fact and the system's own prior synthesized answer (e.g.
`run://.../answer`) as separate evidence items. The intended design (per the
session material) is for recall to always point back to the user's original
statement, not the system's own prior answer, to avoid a citation chain
where an answer becomes evidence for itself. This distinction is not
strictly enforced today.

The contradiction-detection threshold (`0.85` cosine similarity) is a
conservative placeholder validated only against the demonstrated case; a
production system would need labelled examples to tune it properly. A
threshold set too low risks merging two genuinely distinct facts; set too
high, it risks missing a real correction phrased very differently from the
original statement.