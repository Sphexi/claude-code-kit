---
name: systematic-debugging
description: Root-cause-before-fix debugging methodology. Use when a bug's cause is not yet known, when a fix did not hold, when a test fails intermittently, or when the temptation is to change something and re-run. Covers the four-phase loop, root-cause tracing, and flaky-test isolation.
---

# Systematic Debugging

> **Attribution.** The four-phase root-cause-before-fix structure is derived from the
> `systematic-debugging` skill in [superpowers](https://github.com/obra/superpowers)
> (Jesse Vincent / Prime Radiant, MIT licence). This skill is a rewrite carrying the
> methodology forward, not a copy of its text.

The failure mode this exists to prevent: changing something plausible, re-running, seeing green,
and calling it fixed. That is not debugging — it is sampling. It produces fixes that mask symptoms,
fixes that work by coincidence, and fixes that get reverted three weeks later by someone who cannot
tell why the line was there.

**The rule: you may not write a fix until you can state the cause as a claim that could be wrong.**

## The four phases

Run them in order. Do not skip ahead because the answer "seems obvious" — an obvious answer is a
hypothesis, and it belongs in phase 2 where it can be tested.

### Phase 1 — Reproduce

Establish a deterministic reproduction before investigating anything.

- Find the smallest input, state, or sequence that triggers the failure.
- Write it down as concrete steps or, better, a failing test.
- Record the exact error: full message, full traceback, exit code, log lines around it.
- Note what *does* work. The boundary between working and failing is where the cause lives.

If you cannot reproduce it, say so explicitly and stop. Everything after this point assumes a
reproduction, and an investigation built on an unreproducible report produces confident nonsense.
If it only reproduces sometimes, go to **Flaky failures** below before continuing.

### Phase 2 — Isolate

Narrow the failure to the smallest region of code or data that still exhibits it.

- Bisect: by input, by code path, by commit, by configuration — whichever axis is cheapest.
- Remove variables one at a time. Changing two things between runs discards the result of both.
- Instrument rather than guess: log or print actual values at the boundary, and check that the
  values are what the code assumes they are.
- Verify each assumption you are relying on. Most bugs live in an assumption nobody checked,
  not in the logic everyone read.

End this phase able to say: "the failure occurs between *here* and *here*, when *this* is true."

### Phase 3 — Explain

State the root cause as a falsifiable claim, then test the claim.

- Write one sentence: *this happens because X*.
- Then answer: if X were true, what else would be true? Go and check that. If it is not, X is wrong.
- Check that X explains **all** of the observed behaviour, including the parts that work. A cause
  that explains the failure but not the successes is incomplete.
- Trace it back: X is usually itself caused by something. Keep asking why until you reach a cause
  you can actually change — a missing check, a wrong default, an unstated contract between two
  modules. Stop when going further would leave the codebase.

A cause you cannot state as a sentence is not understood, and a fix built on it is a guess.

### Phase 4 — Fix and verify

- Fix the cause, not the symptom. If the fix is a `try`/`except` around the error, a retry, a
  `None` check at the call site, or a default that papers over a bad value — ask whether you are
  fixing the cause or hiding it. Sometimes those *are* the right fix; say which it is.
- Add a regression test that fails before the fix and passes after. Confirm both directions —
  a test that was never seen to fail proves nothing.
- Re-run the original reproduction from phase 1, not just the new test.
- Run the surrounding suite. A fix that breaks something else is not finished.
- State what you changed, why it works, and what you did **not** address.

## Root-cause tracing

When the visible error is far from its origin:

1. **Start at the observable failure** and walk backwards through the data, not the call stack.
   Ask where the bad value came from, then where *that* came from.
2. **Find the first point where the value is wrong.** Everything downstream of that is a
   consequence, not a bug. Fixing a consequence is how a bug gets fixed four times.
3. **Distinguish the three usual origins:** bad input that was never validated, correct input
   transformed wrongly, or correct data arriving in the wrong order or at the wrong time.
4. **Check contracts at each boundary.** Between two modules that are each individually correct,
   the bug is in what they assumed about each other — nullability, units, ordering, ownership,
   encoding, timezone.
5. **Stop at the deepest cause you can change.** Note anything below that line as a constraint
   rather than continuing to dig.

When the trail goes cold, the answer is usually that an assumption checked in phase 2 was checked
by reading rather than by observing. Go back and print the value.

## Flaky failures

An intermittent failure is a real bug with a hidden input. Do not re-run until it passes.

1. **Quantify it.** Run it in a loop — 20, 50, 100 times — and record the failure rate. "Sometimes"
   is not a measurement, and you cannot tell whether a fix worked without a baseline.
2. **Look for the hidden input,** in rough order of likelihood:
   - **Order dependence** — passes alone, fails in the suite, or vice versa. Run the test by
     itself, then run the suite in a different order.
   - **Shared state** — module-level globals, class attributes, caches, a database or temp
     directory not reset between tests, an environment variable set by an earlier test.
   - **Time** — timeouts tuned to a fast machine, sleeps standing in for synchronisation,
     timezone or DST boundaries, dates near midnight, month or year rollovers.
   - **Concurrency** — a race between threads, tasks, or processes; an `await` that yields where
     the code assumed atomicity; a fixture torn down while something still uses it.
   - **Unseeded randomness** — random data, dictionary or set iteration order, hash seeding,
     UUIDs colliding with an assumption of ordering.
   - **The environment** — filesystem case sensitivity, path separators, locale, available cores,
     network reachability.
3. **Make it deterministic before fixing it.** Force the failing condition: pin the seed, freeze
   the clock, force the order, run the two operations concurrently on purpose. A flake you can
   trigger on demand is an ordinary bug and goes back to phase 1.
4. **Fix the cause, not the flake.** Adding a retry, a longer timeout, or a `sleep` converts a
   visible intermittent failure into an invisible one. If a wait is genuinely correct, wait on the
   condition, not on a duration.
5. **Verify with the same loop** you used to quantify it, at the same iteration count.

Never mark a flaky test skipped without recording what is known about it and what would prove it
fixed. A skipped flaky test is a bug report that stopped reporting.

## When to stop and ask

Escalate rather than continuing to dig when:

- Reproducing requires access, data, or an environment you do not have.
- The root cause is in a third-party dependency and the choice is between a workaround, a version
  change, and a fork — that is a decision, not a fix.
- The fix would change behaviour that something else may depend on.
- You have been through the loop twice without narrowing the cause. Report what you ruled out;
  a well-documented dead end is worth more than a third guess.

Report the state of the investigation — reproduction, what is isolated, what is ruled out — rather
than only the fact that you are stuck.
