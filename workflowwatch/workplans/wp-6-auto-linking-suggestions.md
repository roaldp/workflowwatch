# WP-6: Pattern-Based Workflow Detection & Suggestions

> **Goal:** Treat workflows as **patterns of activity** — combinations of apps and sites that appear together in a session — not as "one app = one workflow." Use existing labeled sessions to learn these patterns and suggest (or pre-select) labels when an **unlabeled block of events** matches a workflow's pattern. Reduces clicks by recognizing "this whole block looks like Startup Sourcing" (e.g. LinkedIn Sales Navigator + Google Sheets startup sourcing sheet + LinkedIn profile pages) instead of linking single events.
>
> **Testable outcome:** After labeling several Sourcing sessions that mix LinkedIn, Sheets, Evabot, profile pages, the system learns the **combination pattern**; for an unlabeled block that contains several of these in one time window, it suggests "Label as Startup Sourcing?" with one-click apply. Single-app noise (e.g. one LinkedIn tab without Sheets) does not trigger the suggestion.

---

## Prerequisites

- WP-1 through WP-5 complete. Users have labeled sessions; `session_events` contains `event_data` (app, title, url) for every event in each session.
- Design doc §1: *"The manual labels become training data for future auto-detection."*
- ActivityWatch analysis §12: workflow = sequences/steps (e.g. "LinkedIn → Evabot → Sheets"); session detection from activity patterns; temporal logic.

---

## Why Patterns, Not Single-Event Rules

**Single-event approach (scrapped):** "LinkedIn = Sourcing" leads to false positives: a single LinkedIn tab might be messaging, recruiting, or personal use. It also misses context: real sourcing often involves **several tools in one sitting** — Sales Navigator, a spreadsheet, profile pages, maybe an enrichment tool.

**Pattern-based approach:** A workflow is characterized by **which set of apps/sites co-occur** in labeled sessions. Examples:

| Workflow | Pattern (combination) |
|----------|----------------------|
| **Startup Sourcing** | LinkedIn Sales Navigator + Google Sheets (e.g. "startup sourcing" in title) + LinkedIn profile/company pages; optionally Evabot, Notion, etc. |
| **Due Diligence** | Company website + LinkedIn company + spreadsheet or doc + maybe Cursor/IDE for notes. |
| **Dev** | Cursor/VS Code + GitHub + terminal; or browser (Stack Overflow, docs) + IDE. |

So we learn: *"Sessions labeled as Startup Sourcing typically contain events from at least 2–3 of: {Sales Nav, Sheets with 'sourcing', LinkedIn profiles, Evabot}."* We then **match a block** when the block, as a whole, contains enough of that combination — not when it contains only one.

---

## Research: What We Have and What We Learn

### Labeled data (training source)

- **session_events** + **sessions**: per session we have `workflow_id` and a list of events, each with `event_data`: `app`, `title`, `url`.
- From each session we can extract the **set of (app, domain, title-signature)** that appeared in that session. Domain = host from url (e.g. `linkedin.com`, `docs.google.com`). Title-signature = normalized keyword or substring (e.g. "Sales Nav", "startup sourcing", "profile").

### What we learn per workflow (pattern)

- **Workflow pattern** = a set of **indicators** that frequently co-occur in that workflow's sessions. Each indicator is something like:
  - `(app, domain)` — e.g. (Arc, linkedin.com)
  - `(app, title_contains)` — e.g. (Google Chrome, "Sales Navigator") or (Sheets, "startup sourcing")
  - `(domain, path_or_title)` — e.g. linkedin.com/sales, linkedin.com/in (profile)
- We do **not** require a fixed order (sequence can be a later refinement). For v1 we only require **co-occurrence within the same session**: "this workflow's sessions usually contain at least N of these indicators."
- Per workflow we store: **pattern** = list of indicators with optional minimum count (e.g. "at least 2 of these 5 indicators must appear in a block to suggest this workflow").

### What we match against (candidate block)

- An **unlabeled block** = contiguous (or near-contiguous, with small gaps) sequence of events on the timeline for a given day.
- We summarize the block: set of (app, domain, title-substrings) that appear in the block.
- **Block matches workflow W** if the block's set **overlaps sufficiently** with workflow W's pattern (e.g. at least 2 distinct indicators from W's pattern appear in the block). Thresholds: minimum number of indicators, minimum block duration or event count, to avoid single-tab false positives.

---

## Deliverables

| # | Deliverable | Purpose |
|---|-------------|---------|
| 1 | **Workflow pattern model** | Per workflow, a **pattern** = set of indicators (app+domain, app+title key, domain+path) derived from that workflow's labeled sessions. Stored or cached; recomputed when sessions change. |
| 2 | **Block summarization** | Given a block of events (list of event_data), produce a canonical set of indicators present in the block (deduplicated by app/domain/title). |
| 3 | **Pattern match scoring** | Given a block summary and a workflow pattern, score how well the block matches (e.g. count of pattern indicators present; optionally weight by frequency in training). Return ranked workflows. |
| 4 | **Suggestions API** | For a date: find contiguous unlabeled blocks; for each block, score against all workflow patterns; return suggestions where score ≥ threshold (e.g. "block has ≥2 indicators of Sourcing"). Optional: add-to-session, fill-gap as in previous WP. |
| 5 | **UI: suggestions from patterns** | Show "Label as [Workflow]?" only when the **block** matches the workflow's **pattern** (combination), with one-click apply. Pre-select workflow in "Label as…" when the **selection** matches a pattern. |
| 6 | **Documentation** | How indicators are derived (aggregation of event_data across session_events per workflow); how block–pattern matching works; tuning (min indicators, min block size). |

---

## Tasks

### 1. Backend: Derive workflow patterns from labeled sessions

- **Input:** All `session_events` with `event_data` (app, title, url), joined to `sessions` for `workflow_id`.
- **Per session:** Extract from all events in that session a set of **indicators**. Example indicator types:
  - **App + domain:** (app, url_host) e.g. ("Arc", "linkedin.com"). If no url, use (app, null) or (app, title_slug).
  - **Domain + path/key:** (url_host, path_prefix_or_keyword) e.g. ("linkedin.com", "/sales"), ("docs.google.com", "spreadsheet" or title contains "sourcing").
  - **App + title keyword:** (app, title_substring) e.g. ("Google Chrome", "Sales Navigator"), ("Cursor", "activitywatch").
- **Per workflow:** Aggregate across all its sessions: collect all indicators that appear in ≥1 session; optionally keep only those that appear in ≥ N sessions or with frequency above threshold. The **workflow pattern** = this set of indicators (and optionally a **minimum match count** per block, e.g. 2).
- **Storage:** New table `workflow_patterns` (workflow_id, indicator_type, indicator_value_1, indicator_value_2, session_count) or a JSON blob per workflow; or recompute on demand and cache. Recompute when sessions/events are created or deleted.

### 2. Backend: Block summarization and pattern scoring

- **Block summarization:** Given a list of events (each with app, title, url), build the same indicator set as above (app+domain, domain+path, app+title key). Normalize: same domain, same title keyword; deduplicate.
- **Pattern scoring:** For a block summary (set of indicators) and a workflow pattern (set of indicators), score = size of intersection (or weighted sum). Optionally require **minimum number of distinct pattern indicators** in the block (e.g. ≥2) so that single-app blocks don’t match. Return workflows sorted by score; only return those with score ≥ threshold and ≥ min_indicators_matched.
- **Function:** `score_block_against_workflow_patterns(events: list[EventData]) -> list[(workflow_id, score, matched_indicators)]`.

### 3. Backend: Suggestions for a date (pattern-based)

- **Endpoint:** e.g. `GET /api/v1/suggestions?date=YYYY-MM-DD`.
- **Logic:**
  - Fetch timeline for date. Split timeline into **contiguous unlabeled blocks** (events with session_id null, split when gap &gt; max_gap_minutes or at labeled events).
  - For each block with ≥ min_events or ≥ min_duration_seconds, compute block summary and score against all workflow patterns. If best workflow has score ≥ threshold and ≥ min_indicators_matched, add suggestion: (event_refs, suggested workflow_id, score, matched_indicators).
  - Optional: "Add to session" when block immediately follows a session of W and block matches W's pattern; "Fill gap" when gap between two W-sessions has unlabeled events that match W's pattern.
- **Response:** `[{ type: "label" | "add_to_session" | "fill_gap", workflow_id, session_id?, event_refs[], score, matched_indicators? }]`.

### 4. Frontend: Suggestions and pre-select (pattern-aware)

- **Suggestions:** Show "Label as [Workflow]?" only for blocks that matched that workflow’s **pattern** (combination). Display optional hint: "Matched: Sales Nav, Sheets, LinkedIn profiles" so the user sees why.
- **One-click apply:** Same as before: create session or add to session.
- **Pre-select in "Label as…":** When user selects a set of events, run pattern scoring on that set; pre-select or sort first the workflow that best matches the **combination** (not just the first event).

### 5. Tuning and thresholds

- **Min indicators per workflow pattern:** Only suggest workflow W if the block contains at least **2** (or N) distinct indicators from W’s pattern. This is the main lever to avoid "one LinkedIn tab = Sourcing."
- **Min block size:** Suggest only for blocks with ≥ 2 events or ≥ 1–2 minutes duration.
- **Max gap within block:** When building contiguous unlabeled blocks, merge events that are within e.g. 10–15 minutes so that "Sales Nav then 5 min break then Sheets" can still be one block.
- **Pattern freshness:** Recompute patterns when sessions change so new labeling improves suggestions.

---

## Example: Startup Sourcing Pattern

**From labeled data:** Sessions labeled "Startup Sourcing" contain events like:

- Arc, title "LinkedIn Sales Navigator - Search", url linkedin.com/sales/...
- Chrome, title "Startup Sourcing Sheet", url docs.google.com/spreadsheets/...
- Arc, title "John Doe - LinkedIn", url linkedin.com/in/johndoe
- Arc, title "Company Name - LinkedIn", url linkedin.com/company/...

**Derived pattern (set of indicators):**

- (linkedin.com, /sales) or title contains "Sales Nav"
- (docs.google.com, spreadsheet) or title contains "sourcing" or "startup sourcing"
- (linkedin.com, /in) or title contains "LinkedIn" + "profile"
- (linkedin.com, /company)
- Optionally: (evabot.com) or similar

**Matching:** An unlabeled block that contains, for example, Sales Nav + Sheets with "sourcing" + at least one profile/company page → 3 indicators → suggest "Startup Sourcing." A block with only Sales Nav → 1 indicator → do not suggest (or score below threshold).

---

## Technical notes

- **Indicator normalization:** Use lowercased domain; strip www; title keywords lowercased; path prefix (e.g. /sales, /in) from url path.
- **Order:** v1 ignores order of events within the block; only co-occurrence matters. Optional later: "typically Sales Nav before Sheets" as a soft boost.
- **Performance:** Pattern derivation is O(sessions × events). Block scoring is O(blocks × workflows × indicators). Cache patterns; keep indicator sets small (e.g. top 10–20 per workflow).
- **Privacy:** All data local; no external calls.

---

## Out of scope for this WP

- **ML / embeddings:** No neural models; patterns are derived from counts and set overlap.
- **User-editable patterns:** Patterns are derived only from labels; no UI yet for editing rules (can be a later WP).
- **Strict sequence:** "Step 1 then Step 2 then Step 3" is not required; only "these indicators appear together in the block."
- **Cross-day sessions:** Same-day blocks only for v1.

---

## Testing plan

| # | Test | How to verify |
|---|------|---------------|
| 1 | Pattern derivation | After 3+ Sourcing sessions with LinkedIn + Sheets + profiles, recompute → Sourcing pattern contains linkedin.com/sales, docs.google.com, linkedin.com/in (or equivalent indicators). |
| 2 | Block with combination | Unlabeled block with Sales Nav + Sheets "sourcing" + 1 profile → suggestion "Startup Sourcing?"; apply → session created. |
| 3 | Single app no suggestion | Unlabeled block with only LinkedIn (no Sheets, no profile in same block) → no Sourcing suggestion (or score below threshold). |
| 4 | Pre-select by pattern | User selects events that include Sales Nav + Sheets + profile; opens "Label as…" → Startup Sourcing pre-selected or first. |
| 5 | Two workflows | Block matches both Sourcing and DD patterns weakly; only the stronger match (or first above threshold) suggested. |
| 6 | Min indicators | Block with only 1 indicator from Sourcing pattern → no suggestion. |

---

## Definition of done

- [ ] Workflow **patterns** (sets of co-occurring indicators) are derived from `session_events` and stored or cached.
- [ ] Block summarization and pattern scoring use **combination** logic (min N indicators matched), not single-event match.
- [ ] Suggestions API returns suggestions only when a block matches a workflow pattern (combination) above threshold.
- [ ] Frontend shows pattern-based suggestions with one-click apply; optional hint of matched indicators.
- [ ] "Label as…" pre-selects workflow based on pattern match of the **selected set** of events.
- [ ] Documentation describes pattern model, indicators, and tuning (min indicators, min block size).

---

## Success metric

**Patterns, not single apps:** The system suggests "Startup Sourcing" when it sees the **combination** (e.g. Sales Navigator + startup sourcing sheet + LinkedIn profile/company) in a block, and does not suggest it for a single LinkedIn tab or a random mix of unrelated apps. User labels with fewer clicks because whole blocks are suggested in one go when the activity pattern matches past sessions.
