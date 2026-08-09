# Lean Dev Router — L3 Test Task

**Idempotent POST /orders (duplicate-submit protection under concurrency)**

This is a single, self-contained **L3 (complex)** task for comparing:

| Group | Setup |
|-------|--------|
| **A. Direct Sol** | `gpt-5.6-sol` only |
| **B. Direct Luna** | `gpt-5.6-luna` (max) only |
| **C. Lean Router** | `$lean-dev-router` (`sol_planner` → `luna_worker` → `terra_auditor`) |

Use the **same task packet text** for every group. Reset to the same baseline commit between groups.

---

## Why this task

- Crosses handler / service / store
- Requires backward compatibility (clients without a key must keep working)
- Requires correct HTTP semantics (201 vs 200 vs 400 vs 409)
- Requires a real concurrency story (same key, two concurrent creates → one order)
- Forces design trade-offs; pure Luna often misses locks or conflict rules; Sol is stronger but costlier; Lean exposes escalation and handoff quality

---

## 0. Scaffold (build once, then baseline)

```bash
mkdir -p lean-test-idempotent/{handlers,service,tests}
cd lean-test-idempotent
```

### `service/store.py`

```python
# In-memory store. Tests may reset this module-level state.
ORDERS: dict[int, dict] = {}
NEXT_ID = 1
```

### `service/order.py`

```python
from service import store

def create_order(payload: dict) -> dict:
    if "item" not in payload or not str(payload["item"]).strip():
        raise ValueError("item is required")
    oid = store.NEXT_ID
    store.NEXT_ID += 1
    order = {
        "id": oid,
        "item": str(payload["item"]).strip(),
        "status": "created",
    }
    store.ORDERS[oid] = order
    return order
```

### `handlers/orders.py`

```python
from service.order import create_order

def post_orders(body: dict) -> tuple[int, dict]:
    try:
        result = create_order(body)
        return 201, result
    except ValueError as e:
        return 400, {"error": str(e)}
```

### `tests/test_order.py`

```python
from handlers.orders import post_orders
from service import store

def setup_function():
    store.ORDERS.clear()
    store.NEXT_ID = 1

def test_create_ok():
    code, data = post_orders({"item": "book"})
    assert code == 201
    assert data["item"] == "book"
    assert data["id"] == 1

def test_missing_item():
    code, data = post_orders({})
    assert code == 400
```

### Verify baseline

```bash
python -m pytest tests/ -q
git init   # if needed
git add -A
git commit -m "baseline: orders without idempotency"
# record the commit hash
```

Optional: add the concurrency test skeleton from §3 to the baseline as a **failing** test so the agent must make it pass.

---

## 1. Standard task packet (copy verbatim for all groups)

```text
[Goal]
Add optional idempotency support to POST /orders so duplicate submissions with the same key do not create duplicate orders, including under concurrent requests.

[Scope]
Allowed:
- handlers/orders.py
- service/order.py
- service/store.py
- tests/test_order.py
Forbidden: any other files; no new third-party dependencies

[Constraints]
1) Backward compatible:
   - Requests WITHOUT idempotency_key must keep working exactly as today (new order, 201).
2) Optional field in body: "idempotency_key" (string).
   - If present, strip surrounding whitespace.
   - Empty / whitespace-only key is invalid → 400.
   - Key length must be 1..128; longer → 400.
3) Idempotent behavior:
   - First successful create with key K stores the created order and associates it with K.
   - Later requests with the same K must return 200 (not 201) and the SAME order payload (same id and fields), without creating a second order.
4) Conflict behavior:
   - If the same K is reused with a DIFFERENT item (or otherwise different create intent), return 409 with an error payload. Do not overwrite the original order.
5) Concurrency:
   - Two concurrent creates with the same valid K must result in exactly one stored order for that K.
   - It is acceptable for one caller to receive 201 and the other 200, or both to observe a single canonical order, as long as ORDERS contains one order for that logical create and both responses refer to that same id.
6) Storage:
   - You may extend the in-memory store in service/store.py (e.g. maps/locks).
   - Must be process-local only; no DB, no network, no new packages.
   - If you add module-level idempotency state, update test setup so every test resets it deterministically.
7) Do not break existing tests for plain create / missing item.
8) Keep the change minimal and readable; no unrelated refactors.

[Acceptance]
Run:
  python -m pytest tests/ -q

Required tests (add them if missing; all must pass):
A) Legacy path: {"item":"book"} → 201, creates id=1; second legacy create → 201 with a new id.
B) Idempotent replay: first {"item":"book","idempotency_key":"k1"} → 201; second same body → 200; same id; only one order for that logical create as asserted by tests.
C) Invalid keys: missing item still 400; idempotency_key "" / "   " / len>128 → 400.
D) Conflict: first k2+item A succeeds; later k2+item B → 409; original order unchanged.
E) Concurrency: two threads both POST the same key+item at the same time; after both finish, exactly one order exists for that create, and both responses refer to the same order id; no exception escapes the handler.
F) Scope evidence includes `git diff --name-only --no-renames <baseline> --`, `git ls-files --others --exclude-standard`, and `git ls-files --others --ignored --exclude-standard`; every reported tracked, standard untracked, and ignored untracked path is allowed.

[Forbidden]
New dependencies, file I/O, real HTTP server, unnecessary public API renames, drive-by refactors, extra features (auth, pagination, etc.).

[Baseline]
Starting commit hash: <paste yours>
```

---

## 2. Group openers

Paste the opener, then the full task packet.

### Group A — Direct Sol

```text
Use only gpt-5.6-sol. Do not use lean-dev-router or spawn other agents.
Complete the following task end-to-end.
```

### Group B — Direct Luna

```text
Use only gpt-5.6-luna with max reasoning effort. Do not use lean-dev-router or spawn other agents.
Complete the following task end-to-end.
```

### Group C — Lean Router

```text
Use $lean-dev-router. Follow its routing policy and compact handoff rules.
Complete the following task end-to-end.
```

Between groups:

```bash
git reset --hard <baseline-commit>
```

---

## 3. Optional concurrency test skeleton

You may place this in `tests/test_order.py` before the run (as a failing test) or require the agent to add equivalent coverage.

```python
import threading
from handlers.orders import post_orders
from service import store

def test_concurrent_same_key_one_order():
    store.ORDERS.clear()
    store.NEXT_ID = 1
    rounds = 25

    for round_id in range(rounds):
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait()
                results.append(post_orders({
                    "item": "book",
                    "idempotency_key": f"same-{round_id}",
                }))
            except BaseException as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        barrier.wait()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not t1.is_alive()
        assert not t2.is_alive()

        assert not errors
        assert len(results) == 2
        assert sorted(r[0] for r in results) == [200, 201]
        ids = [r[1]["id"] for r in results]
        assert len(set(ids)) == 1

    assert len(store.ORDERS) == rounds
```

---

## 4. What to record

```text
Task: L3 idempotent POST /orders
Group: A Sol | B Luna | C Lean
Baseline commit:

Turns:
Sol calls:
Luna calls:
Terra calls:
Escalations (Luna→Terra / Terra→Sol):

Input tokens:
Output tokens:
Total tokens:          # or consistent proxy (turns / tool calls)

git diff --stat:
git diff --name-only --no-renames <baseline> --:
git ls-files --others --exclude-standard:
git ls-files --others --ignored --exclude-standard:

Acceptance:
  A Legacy path: PASS | FAIL
  B Idempotent replay: PASS | FAIL
  C Invalid keys: PASS | FAIL
  D Conflict 409: PASS | FAIL
  E Concurrency: PASS | FAIL
  F Scope only allowed files: PASS | FAIL

Quality scores (0–2 each, max 12):
  Correctness:
  Scope control:
  Tests:
  Safety / boundaries:
  Maintainability:
  Completeness:
Quality total: /12

Notes:
```

### Quality rubric (0–2)

| Dimension | 2 | 1 | 0 |
|-----------|---|---|---|
| Correctness | All acceptance checks pass | Partial | Fail |
| Scope control | Only allowed files | Minor noise | Clear expansion |
| Tests | Required cases present and passing | Weak / incomplete | Missing |
| Safety / boundaries | Sound concurrency and conflict handling | Minor gap | Race or silent overwrite |
| Maintainability | Minimal, clear change | Messy but readable | Confusing structure |
| Completeness | Fully delivered per packet | Runnable but incomplete | Half-finished |

**Degradation rule of thumb**

- Lean ≥ Sol − 1 and acceptance passes → no meaningful degradation
- Lean ≤ Sol − 2 or acceptance fails → quality risk
- Many escalations with total cost near Sol → limited savings on this L3 task (valid finding)

---

## 5. What gaps this task usually reveals

| Group | Typical pattern |
|-------|-----------------|
| **A Sol** | Higher correctness on concurrency/conflict; higher token cost |
| **B Luna** | Lower cost; more failures on locks, 200 vs 201, or 409 overwrite bugs |
| **C Lean** | Watch whether design escalates to Terra/Sol, whether handoffs stay compact, and whether total cost sits between A and B without quality loss |

Failure modes worth noting explicitly:

- Replay still returns 201 and creates a second order
- Same key + different item overwrites instead of 409
- Concurrent same key creates two orders
- Legacy path without key breaks
- Diff touches files outside the allow-list
- Lean ignores compact handoff rules or escalates every step to Sol

---

## 6. Minimal run order

1. Build scaffold, commit baseline, record hash  
2. Run **Group A** with packet + opener → record metrics → reset  
3. Run **Group B** → record → reset  
4. Run **Group C** → record  
5. Fill acceptance + quality scores  
6. Compute savings vs Sol:

```text
Savings rate ≈ 1 - (Lean total tokens / Sol total tokens)
```

Only compare runs that used the **same** packet text and baseline.

---

## 7. Optional harder variant (same repo)

If A/B/C all pass too easily, add **one** extra constraint without changing the rest of the packet:

```text
Additional constraint:
- Idempotency keys are case-sensitive.
- A simultaneous replay must never return two different order ids.
- Document in a short code comment how the critical section is protected.
```

Do not add this mid-run for only one group.

---

## License note

This document is a test protocol only. Adapt paths and commands to your environment freely.
