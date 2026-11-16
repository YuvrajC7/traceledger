# TraceLedger

**Payment failure replay and counterexample reduction.** Runnable engineering prototype with a local browser demo, FastAPI endpoints, automated tests, and reproducible synthetic evaluation.

## Run locally

Use Python 3.13. From the repository directory:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python benchmark.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the interactive JSON demo or /docs for API schemas. The demo's Run button calls POST /demo. No API key is needed for the default path. Services are local demonstration applications without production authentication or rate limiting.

## Design and boundaries

A timeout after a committed transfer can provoke a duplicate retry. TraceLedger makes that ambiguity reproducible with an integer-minor-unit journal, command fingerprints, a transactional outbox, and a deduplicating consumer inbox.

`seeded trace -> transactional journal/outbox -> retry -> inbox -> reference comparison`

The simulator injects exceptions before commit, after commit, and after consumer commit but before acknowledgement. Connections reopen after failures. A separate faulty duplicate handler supplies a counterexample for delta debugging; the reducer returns a 1-minimal failing trace. Concurrent same-key retries and conflicting payloads have dedicated tests.

This is a local single-currency accounting simulator. It does not authorize funds, enforce available balances, contact a payment processor, or demonstrate distributed exactly-once delivery. Exceptions are not machine power failures. SQLite serializes writers; these results do not establish PostgreSQL or distributed-system behavior.

## Evaluation

The checked-in [benchmark report](reports/benchmark.json) contains measured results, source hashes, environment metadata, and scope notes. Run `python benchmark.py` to regenerate it; timing varies by machine. The test suite contains **16 passing cases** in the recorded local run. CI reruns tests and benchmarks on Ubuntu.

All generated transactions, documents, labels, and API fixtures are synthetic. Generators are in core.py and experiment definitions in benchmark.py. The generator plus fixed seeds is the reproducible data source; no private user, employer, or customer data is included. Finite passing checks do not prove universal correctness.

## Source map

| File | Responsibility |
| --- | --- |
| core.py | Domain logic and seeded fixtures |
| app.py | Validated API requests and demo routes |
| ui.py | Lightweight browser interface |
| tests/ | Regression and domain checks |
| benchmark.py | Reproducible evaluation workload |
| reports/benchmark.json | Measured local evidence |

## Development

Created with AI coding assistance. Claims describe the code and bounded evaluations in this repository. MIT licensed; see LICENSE.
