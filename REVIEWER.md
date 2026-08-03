# concept-bot — code reviewer

Two layers. Run both.

1. **`review.py`** — mechanical. Countable, project-specific invariants. No API calls, no network.
2. **This file** — judgment. Paste into Claude Code when you want a real review.

The split exists for a reason this project learned the hard way. The critic prompt told Haiku *"a first line over fifteen words caps fluency at 5"*, then handed it a 30-word opening line, and got back a 9. **Never ask a language model to do what a regex can do.** Countable things get counted in code. The LLM gets only genuine judgment.

---

## Running it

```bash
python3 review.py                    # every run
python3 review.py --fail-on high     # in CI
```

Then paste the block below into Claude Code.

---

## The review prompt

```
Review this repo as a senior engineer who will personally be on call for it.

Read first, in this order:
- docs/GROWTH_STRATEGY.md — what this system is FOR. A technically clean change that
  weakens the product is a bad change.
- app.py — the whole pipeline in one file
- topics.py, generate_prompt.py, validate_prompt.py, validate.py — the content engine
- state.py, images.py, poster.py, config.py — the plumbing
- Then run `python3 review.py` and treat its findings as already-known. Don't repeat
  them. Find what it can't see.

## What this system actually is

A fully autonomous publisher. No human approves anything before it goes out. That
single fact should govern every judgment you make:

- A crash is cheap. The slot is skipped, an alert fires, nobody sees it.
- A BAD POST IS EXPENSIVE. It goes out under a real name, permanently, and per-post
  engagement rate is what the platform's ranking system scores the whole account on.
  One weak post lowers distribution for every future post.
- Therefore: when in doubt, fail closed. Skipping is nearly free. Publishing something
  mediocre is not.

Cost matters but is not the constraint. The whole thing runs for a few dollars a month.
Do not propose optimisations that trade correctness or content quality for pennies.

## Review in this priority order

### 1. Silent wrongness
The worst failure here is not an exception — it's the pipeline running to completion and
publishing something wrong. Hunt specifically for:
- Anything that can produce a plausible-looking but incorrect post
- State that can be read stale, or written after it's needed
- Two invocations racing (this has already happened in production — see the incident log
  in the v1 design doc; MIN_MINUTES_BETWEEN_POSTS is the current mitigation)
- Defaults or fallbacks that quietly substitute something worse instead of failing
- Any `except` broad enough to swallow a real bug

### 2. The gate
This is where the product lives. Ask:
- Is every numeric rule stated in CRITIC_SYSTEM_PROMPT also enforced deterministically?
  If a rule is only in the prompt, assume it is not enforced. Calibration proved this.
- Can the critic's output be trusted without verification? It currently cannot — the
  extracted "gift" is accepted on faith.
- Does the retry path actually change anything, or does it regenerate the same mistake?
- If the critic returns malformed JSON, or times out, what ships?

### 3. Blast radius of external failures
Every external call is a thing that will fail at 9am on a Sunday. For each one, trace
what actually happens: Anthropic 429/529/timeout, Unsplash and Pexels down or rate
limited, X API auth expiry or rate limit, Firestore unavailable.
For each: does it degrade to a skipped slot with a clear log line, or does it 500?

### 4. Content-system judgment
You are also reviewing the prompts as code, because they are.
- Does the topic bank's Door hold up? Pick the three weakest `universal_door` values and
  argue why they'd fail for someone outside the US.
- Where do generate_prompt and validate_prompt disagree? A generator told one thing and a
  critic scoring another produces expensive, invisible thrash.
- Is anything in the critic rubric anchoring rather than measuring? (Universality returned
  9 on all 20 calibration drafts — the rubric's examples match the bank too closely.)

### 5. Ordinary engineering
Naming, dead code, duplication, docstrings that no longer match behaviour, missing type
hints, functions doing two jobs. Lowest priority, still worth saying.

## How to report

Group by severity. For each finding give exactly four things:
- **Where** — file and function
- **What** — one sentence
- **Why it matters here** — tied to THIS system's failure modes, not general principle.
  "Broad except is bad practice" is not a reason. "This except swallows the auth error
  that means every post for the next week will silently fail" is.
- **Fix** — concrete, minimal, and specific.

Rules:
- If something is fine, say so briefly. A review that finds problems everywhere is not a
  careful review, it's a nervous one.
- Rank by expected damage, not by how easy it is to describe.
- If you'd defend the current code against a proposed change, say that too — the strategy
  doc and the incident log contain deliberate decisions that look wrong out of context.
  The random tie-break in pick_next_topic and the disabled extended thinking in
  generate.py are both intentional fixes for real production incidents. Don't "clean
  them up."
- Do not change any code in this pass. Report only. I'll pick what to act on.
```

---

## Standing constraints for any fix

Give these to Claude Code alongside the review when you act on findings.

**Do not touch without discussion:**
- The random tie-break in `pick_next_topic()` — fixed a real duplicate-post incident (commit `96eeefc`)
- `thinking={"type": "disabled"}` in `generate.py` and `images.py` — thinking silently ate the entire token budget and returned truncated output
- `MIN_MINUTES_BETWEEN_POSTS` — defence against a scheduler retry racing a slow original request
- The v1.1 + v2 tweepy split in `poster.py` — X retired v1.1 `statuses/update`, but `media_upload` has no v2 equivalent. Both are required.
- `cache_control: ephemeral` on the system block — the prompt is large and identical every call

**Always:**
- Fail closed. Skipping a slot is nearly free; a bad post is not.
- One concern per change. Never bundle a schedule change with a code change — you lose the ability to attribute a regression.
- Show the diff before applying. Never deploy in the same session as a review.
- After any change to the gate or the prompts, re-run `python3 calibrate.py --seed 42` and compare against the previous run. All six controls must fail.

---

## When to run what

| Situation | Run |
|---|---|
| Before any deploy | `review.py --fail-on high` |
| After changing prompts or thresholds | `calibrate.py --seed 42` |
| After changing `topics.py` | `python3 topics.py` then `calibrate.py --drafts 10` |
| Weekly | the full judgment review |
| After any production incident | both, plus add a check to `review.py` encoding what went wrong |

That last row is the one that compounds. Every incident should leave behind a check that
would have caught it. `review.py` is designed to be appended to — add a function, register
it in `main()`, done.
