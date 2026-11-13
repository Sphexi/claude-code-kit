# Code Standards (part 1 of 1) — applied for this session

## Comments

**The default is no comment.** Code that reads clearly is finished; it does not also need a sentence saying what it just said. A comment is a small, expensive exception granted to a line that cannot speak for itself, and each one earns that exception individually. A file with no comments in it is not an oversight.

**The code says what and how. A comment says why.** Where the *what* is genuinely not legible — a regex, a bit-twiddle, a protocol offset, a non-obvious algorithm — the comment may say what, in one line. It never restates a line that already reads clearly.

**Never duplicate.** Not the code beneath it, not the type signature beside it, not a document elsewhere in the repo. A comment that repeats `docs/`, a spec, a README, or a plan is a second copy that will drift from the first.

### Never appears in a comment

These are prohibited outright, in every language, in docstrings as well as inline comments:

- **Process and provenance** — session numbers, task or backlog IDs, sprint references, plan or spec filenames, decision-log entries, dates of changes, "as of the refactor", "previously this did X".
- **Rationale for a decision that was made about the project** rather than a constraint the code is under. "We chose Postgres over SQLite because…" is a document. "This query is not parameterised because the identifier cannot be bound" is a comment.
- **The case for a choice, argued against its alternatives.** "Argon2id rather than bcrypt because…", "a plain hash is right here rather than a KDF because…", "p=1, because each extra thread multiplies the memory pool". The chosen value is in the code; why it beat the runner-up is not a property of the code at all, and nobody editing that line needs the debate replayed.
- **Citations propping up a choice.** A link to a standard, benchmark, or cheat sheet included to show the value was well-chosen is the previous item with a URL attached. A link to an upstream *defect* being worked around, or to the *spec being implemented*, is a different thing and stays — see below.
- **People.** No names, no initials, no "requested by", no "per our discussion", no attribution of a choice to anyone.
- **The assistant and its machinery.** No mention of Claude, agents, subagents, skills, plugins, prompts, CLAUDE.md, technical plans, or sessions. Code has no idea any of that exists and must not learn.
- **Changelog prose.** "Added in v2", "changed to fix the timeout bug", "used to call `_legacy_parse`". Version control holds history; a comment holding history is a duplicate that silently goes stale.
- **Tours of other files.** "The login route catches this and converges on a 401", "imported by the CLI and by the admin route". Behaviour belongs beside the code that performs it, and a description of a caller written into the callee goes stale the first time that caller moves. Name another module only where this code breaks without it.
- **Commented-out code.** Delete it.

A bug-fix comment is allowed when it explains a workaround a future reader would otherwise undo — but it states the *constraint*, not the incident: "the API returns 200 with an empty body on a rate limit, so status alone is not sufficient", never "fixes the bug found when the sync ran twice".

### Where a comment does earn its place

- Code that looks wrong or redundant and is not, so the next reader does not "fix" it.
- A constraint on the caller that the signature cannot express — ordering, lifetime, thread or task affinity, a unit, a range.
- A workaround for an external defect, with a link to the upstream issue or standard.
- A source link for code adapted from elsewhere.
- A deliberate omission, and what would have to be true to fill it in.
- A security or correctness invariant that the surrounding code depends on and does not enforce.

### Size

- **Module or file header:** one to three lines. What this file is. Longer belongs in the repo's documentation, not here.
- **Public function, class, or method:** a one-line docstring where the name and signature do not already say it, in the imperative. A wrapper called `hash_password(plaintext: str) -> str` does not need a line reporting that it hashes a password.
- **Public constant, type alias, interface, or field:** none, unless the value or shape is genuinely not self-evident from the name.
- **Argument, return, and error sections** (`Args:`/`Returns:`/`Raises:`, `@param`, `.PARAMETER`, `///`): only where they add information the signature and type annotations do not already carry. A section restating an annotated parameter is deleted.
- **Private helper:** no docstring when the name and body are self-evident. A one-liner only where the logic is not.
- **Inline:** one line. If it needs a paragraph, the code needs a better name or a smaller function.

### Handling

**String literals are code, not comments.** User-facing copy, schema descriptions, SQL, log messages, and validation text are data the program depends on. Never edit inside a string while reducing comments.

**A comment you invalidate is a comment you fix or delete.** Changing code and leaving its comment behind produces a confident lie. This is the one case where deleting without replacing is always correct.

**`TODO` is allowed** when it names the condition that would resolve it. No person, no session, no date.

## Tests

### What a test is worth

A test earns its place only if deleting it would make a realistic failure materially harder to catch. Nothing else justifies one — not symmetry with a neighbouring test, not a coverage number, not a line-count ratio.

**Coverage is sized by project tier**, measured as test LOC against the code under test:

| Tier | Band | What it buys |
|---|---|---|
| Light | ~0.85 : 1 | Happy path, the error paths a caller can actually hit, config and boundary parsing |
| Standard | ~1.0–1.2 : 1 | The above, plus edge cases, partial failure, and retry/backoff behaviour |
| Heavy | ~1.5 : 1 | The above, plus adversarial input, concurrency, and recovery paths |

**The ratio is a sanity check, never a target.** A suite that drifts far outside its band is worth looking at; a test is never added to raise the ratio and never deleted to lower it. Judge a suite by test count and runtime, which are what a reader and a CI run actually pay.

### Cost, and where runtime actually goes

Tests do not cost the same. A test that touches a database, a container, a real filesystem, or a subprocess costs two to three orders of magnitude more than a pure in-process test — hundreds of milliseconds against roughly one.

Four consequences, and they are the whole of test efficiency:

1. **Reduce the count of expensive tests, not lines anywhere.** Trimming a pure test changes nothing measurable.
2. **Parametrising an expensive test does not make it cheaper.** Every case is still a separate test paying full setup. Prefer the opposite: merge expensive tests that share setup into one test with several assertions, and de-parametrise where the cases only vary data.
3. **Parametrise pure tests freely.** They are where a table of cases costs nothing and reads best.
4. **Move the assertion to where it is cheap.** If logic can be tested behind a seam without infrastructure, test it there and leave the expensive test to prove the wiring once.

### Structure

- **Arrange, act, assert**, in that order, visibly separated. One act per test.
- **Names are sentences** — unit under test, scenario, expected result.
- **No control flow in a test.** No `if`, no loops, no string building. If a test needs logic, it is two tests or a parametrised one.
- **Minimally passing input.** The simplest value that exercises the behaviour. Extra fields and non-zero values that do not matter obscure what does.
- **No magic values.** A literal that carries meaning gets a named constant.
- **Assert behaviour, not implementation.** Test through the public surface; a private helper is covered by the public caller that uses it.
- **Fixtures at the narrowest scope that is still correct**, with expensive setup shared at the widest scope that preserves isolation. An expensive fixture is never `autouse` — a test that does not need the database must not pay for it.
- **Nothing real that can be faked**: no network, no wall clock, no filesystem outside a temporary directory, no sleeping to wait for something.

### Running the suite

Test time is spent on re-running, not on running. A session that runs the full suite after every small edit spends more time waiting than working.

**The loop is:** run the full suite once at the start. Make every change. Run only the tests covering the code touched — by node id, by path, by marker, or with the last-failed selection. Run the full suite once more at the end only when the change was broad enough that targeted tests do not cover its blast radius.

**Never re-run the full suite to confirm a one-line fix.**

Where a suite is large enough that this matters, it is set up to support it: a fast/slow split by marker so the inner loop is seconds, parallel execution across workers, and a profile of the slowest tests before any optimisation is attempted. Measure before changing; the slow part is usually setup, not test bodies.

**Never weaken an isolation guarantee to buy speed as a side effect of other work.** Changing how tests are isolated from one another is its own change, made deliberately and reviewed on its own terms.
