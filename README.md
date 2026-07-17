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
