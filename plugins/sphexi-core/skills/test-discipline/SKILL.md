---
name: test-discipline
description: How much to test, how to keep a suite fast, and how to run it during a session without burning the session on re-runs. Use when writing or reviewing tests, when a suite has grown slow, when deciding whether a test is worth keeping, when pruning redundant coverage, or when planning how many times a suite will be run during a piece of work. Covers pytest, Docker-backed integration tests, and database test isolation.
---

# Test Discipline

The hard rules are in every agent definition and in `~/.claude/CLAUDE.md`, inlined from
`shared/code-standards.md`. This skill is the working reference: how to size a suite, how
to make it fast, and how to run it during a session.

Three failure modes it exists to prevent:

- A suite sized to hit a line-count ratio rather than to catch failures.
- A suite whose runtime is fixture setup that nobody has profiled.
- A session that spends four hours re-running a 25-minute suite after each one-line edit.

## Sizing a suite

**A test earns its place only if deleting it would make a realistic failure materially
harder to catch.** Not a hypothetical failure — one the product, an operator, a caller, or
the data could actually produce.

Nothing else justifies a test. Not symmetry with the test above it, not a coverage
percentage, not a ratio.

| Tier | Test LOC : code LOC | Scope |
|---|---|---|
| Light | ~0.85 : 1 | Happy path, reachable error paths, config and boundary parsing |
| Standard | ~1.0–1.2 : 1 | Plus edge cases, partial failure, retry and backoff behaviour |
| Heavy | ~1.5 : 1 | Plus adversarial input, concurrency, recovery paths |

### The ratio is a diagnostic, not a target

A suite far outside its band is worth a look. A suite inside its band is not thereby good.
Two specific errors follow from treating the ratio as the goal:

- **Adding tests to reach it** produces duplicate coverage, which costs maintenance on
  every future change and catches nothing new.
- **Deleting tests to reach it** removes coverage for reasons unrelated to what the tests
  were protecting.

A test is removed because it is redundant with another test. Never because a file is long.

### What redundancy actually looks like

- Two tests whose assertions both fail for exactly the same class of defect.
- A parametrised case that varies an input the code under test does not branch on.
- A test of a private helper, where the public caller's test already covers the path.
- Several files split by *who wrote them* or *when*, rather than by behaviour. Merge by
  behaviour; one test module per source module.
- A test asserting framework behaviour rather than your own code.

## Speed, and where runtime actually goes

### The cost model

Tests do not cost the same, and the difference is not marginal:

| Kind | Typical cost |
|---|---|
| Pure, in-process | ~1 ms |
| Database-backed | ~100–400 ms |
| Container or subprocess | seconds |

Three orders of magnitude. Every efficiency decision falls out of that table.

**Reduce the count of expensive tests. Nothing else moves the clock.** Trimming lines from
a pure test saves nothing measurable; deleting one redundant database test saves as much as
deleting three hundred pure ones.

### The parametrisation trap

Consolidating several expensive test bodies into one parametrised test *looks* like a
reduction and is **runtime-neutral**: the framework pays fixture setup once per case, not
once per function. A pass that does this reports a large drop in test functions and almost
no drop in wall clock.

The correct moves, in order of value:

1. Merge expensive tests that share setup into **one test with several assertions**. This
   is the case where the usual one-assert-per-test guidance is outweighed — the setup cost
   is the thing being amortised, and the tests were already asserting on one arrangement.
2. **De-parametrise** an expensive test whose cases only vary data, keeping the one or two
   cases that represent distinct behaviour.
3. **Parametrise pure tests freely.** A table of cases is the right shape there and costs
   nothing.
4. **Move the assertion where it is cheap.** Test the logic behind a seam in-process; leave
   one expensive test to prove the wiring.

### Measure first

Never optimise a suite you have not profiled. The slow part is almost always setup.

```bash
pytest --durations=25                     # slowest tests, sequential
pytest --collect-only --noconftest        # is collection or conftest the cost?
python -X importtime -m pytest            # heavy imports at startup
```

A worked example of what profiling finds: a suite spending 24 minutes had almost all of it
in fixture setup, because the connection pool was created with library defaults — ten
connections opened per test to use one. Sizing the pool explicitly for tests took that
fixture from 748 ms to 74 ms, with no change to production behaviour, because the
production defaults were left as the function's defaults.

### pytest levers, in rough order of payoff

```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = ["docs", "*.egg-info", ".git", ".venv"]
markers = [
    "fast: no external resource; safe in the inner loop",
    "db: requires the test database",
    "serial: must not run under xdist",
]
```

- **Split by marker** so the inner loop is seconds. Derive the marker from which fixtures a
  test requests rather than hand-labelling, so it cannot drift.
- **Parallelise**: `-n auto`. Use `--dist loadscope` or `--dist loadfile` where tests share
  module- or class-scoped fixtures, so a worker sets up once per group. Session-scoped
  fixtures execute once *per worker*, not once per run — size resources accordingly, and
  watch the database connection limit when raising worker count.
- **Scope fixtures narrowly but not naively.** Function scope for anything holding state a
  test mutates; session or module scope for the expensive, immutable setup (schema
  creation, a built image, a loaded model). Never `autouse` an expensive fixture: a pure
  test must not pay for a database it never touches.
- **`PYTHONDONTWRITEBYTECODE=1`** in CI.
- **Disable unused plugins**: `-p no:doctest -p no:pastebin`. Check with `--trace-config`.
- **Ban the network** with `pytest-socket` rather than trusting every test to mock; mock
  HTTP at the transport boundary (`respx` for `httpx`) rather than patching client methods.
- **Fake the filesystem and the clock.** `tmp_path`, and an injected clock or
  `time-machine` — never `sleep` to wait for something.

### Database isolation

Isolation between tests is the one property never traded for speed. The options, cheapest
first:

1. **Transaction per test, rolled back at teardown.** Fastest, and it never needs a
   truncate. The trap: a `DEFERRABLE INITIALLY DEFERRED` constraint only fires at commit,
   so a rollback-only suite can pass on a row production would reject. Keep a small number
   of commit-path tests that do not use the rollback fixture.
2. **Dirty-check before truncating.** `SELECT EXISTS (SELECT 1 FROM <table>)` and truncate
   only when something was written. Where most tests read, this is dramatically cheaper
   than an unconditional `TRUNCATE ... CASCADE`.
3. **`TRUNCATE ... CASCADE` per test.** Correct, and the most expensive of the three.
4. **Drop and recreate per test.** Never.

**Changing the isolation mechanism is its own change.** It is the one property the whole
suite's trustworthiness rests on. It gets its own pass and its own review — never a rider
on an unrelated piece of work.

## Structure

Adapted from [Microsoft's unit testing best
practices](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices),
which the rules below follow.

- **Fast, isolated, repeatable, self-checking, timely.** A test that fails on a Tuesday, or
  only when run after another test, is not a test yet.
- **Name is a sentence** in three parts: unit under test, scenario, expected result.
  `test_fetch_weight_with_empty_response_returns_empty_list`.
- **Arrange, act, assert**, visibly separated, in that order.
- **One act per test.** Several acts mean you cannot tell which one failed, and an early
  assertion failure hides the rest.
- **No logic in a test.** No `if`, no loop, no `switch`, no string building. If a test seems
  to need logic, it is two tests or one parametrised test.
- **Minimally passing input.** The simplest value that exercises the behaviour. Extra
  populated fields and arbitrary non-zero numbers obscure which value the test depends on.
- **No magic values.** A literal carrying meaning gets a named constant.
- **Helper functions over implicit setup.** A helper called from the test body keeps the
  arrangement visible at the point it matters, and avoids setting up more than the test
  needs. This is in tension with amortising expensive setup — resolve it by scope: cheap
  arrangement in a helper, expensive resources in a fixture.
- **Test the public surface.** A private helper is covered through the caller that uses it;
  testing it directly asserts an implementation detail and blocks refactoring.
- **Introduce a seam for anything you cannot control** — the clock, randomness, the
  environment, the network. Inject it rather than patching a global.
- **Mock versus stub.** A stub feeds the system under test. A mock is asserted against.
  Asserting on a stub tests the test.

## Docker and integration tests

- Build the image **once** per run, not per test. Reuse a running container across the
  tests that need it; reset state between them rather than recreating the container.
- Wait on a health check, never on a sleep.
- Keep the integration suite separate from the unit suite so the inner loop never touches
  Docker.
- An integration test proves wiring: the container starts, the endpoint answers, the
  migration applies. Behaviour is proven in unit tests, where it costs a millisecond.

## Running the suite during a session

This is where the time actually goes. A 25-minute suite run eight times is three and a half
hours of a session spent waiting, against perhaps thirty minutes of work.

**The loop:**

1. **Once, at the start:** run the full suite. Now you know the baseline, and any failure
   you see later is yours.
2. **Make every change.** All of them. Do not run the suite between edits.
3. **Run targeted tests** covering the code touched — by node id, by path, by marker, or
   with the last-failed selection:

   ```bash
   pytest tests/test_client.py::TestClient::test_retries_on_429
   pytest tests/integrations/ -m fast
   pytest --lf -x
   ```

4. **Once, at the end:** run the full suite again **only** when the change was broad enough
   that the targeted tests do not cover its blast radius. A one-file change with green
   targeted tests does not need it.

**Never re-run the full suite to confirm a one-line fix.** If a fix is uncertain enough to
need the whole suite, the uncertainty is about the cause, not the coverage — find the cause.

Where a full re-run is genuinely needed more than twice in a session, that is a signal about
the suite's runtime, not about the discipline. Fix the suite.
