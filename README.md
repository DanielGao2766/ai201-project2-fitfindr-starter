# FitFindr - Project 2

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. The agent searches mock thrift listings, suggests outfits based on the user's existing wardrobe, and generates a shareable caption based on a single user query about what clothing they are looking for. 

---

## Tool Inventory

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

**Purpose:** Searches the mock listings dataset for items matching a text description, optional size, and optional price ceiling.

**Inputs:**
- `description` (str) — keywords describing what the user wants (e.g., `"vintage graphic tee"`). Extracted from the user's natural-language query by the planning loop via regex.
- `size` (str | None) — size to filter by. Matching is case-insensitive substring: `"M"` matches `"S/M"` and `"M/L"`. Pass `None` to skip size filtering.
- `max_price` (float | None) — price ceiling, inclusive. Pass `None` to skip price filtering.

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises.

**Scoring:** The query is tokenized into whole words (lowercase). Each listing is scored by how many distinct query keywords appear across its `title`, `description`, `category`, and `style_tags` fields. Listings that match zero keywords are excluded.

---

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

**Purpose:** Given a thrifted item and the user's wardrobe, uses an LLM to suggest 1–2 complete outfit combinations. Handles an empty wardrobe gracefully.

**Inputs:**
- `new_item` (dict) — a listing dict from `search_listings`. Fields used in the prompt: `title`, `price`, `platform`, `condition`.
- `wardrobe` (dict) — wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. May be empty.

**Output:** A non-empty string with outfit suggestions.
- Non-empty wardrobe: specific pairings referencing named pieces from the wardrobe — *"Pair this with your baggy dark-wash jeans and chunky white sneakers for a streetwear look. Tuck the front corner slightly for shape."*
- Empty wardrobe: general styling advice — what pairs well with the item, what vibe it suits, 1–2 outfit ideas using common staples.

**Model:** `llama-3.3-70b-versatile`, temperature `0.3`.

---

### `create_fit_card(outfit: str, new_item: dict) → str`

**Purpose:** Generates a 2–4 sentence Instagram/TikTok-style caption for the thrifted find and its outfit. Uses a higher temperature for variety — the same input produces different captions each run.

**Inputs:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict) — the listing dict. Fields used in the prompt: `title`, `price`, `platform`, `condition`.

**Output:** A casual, authentic-sounding caption that mentions the item name, price, and platform naturally once each — e.g., *"found this tour bootleg tee on depop for $24 and it was made for my baggy jeans — graphic tees that actually fit are so rare."*

If `outfit` is empty or whitespace-only, returns `"Unable to generate a fit card — no outfit suggestion was available."` without raising.

**Model:** `llama-3.3-70b-versatile`, temperature `0.8`.

---

## Planning Loop

`run_agent()` in `agent.py` is a plain Python function — the LLM is **not** used to route tool calls. The LLM only executes inside `suggest_outfit` and `create_fit_card` as a generation step. The sequence is:

1. **Parse the query** — regex extracts `description`, `size`, and `max_price` from the user's natural-language input (e.g., `"vintage graphic tee under $30, size M"` → `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`). Stored in `session["parsed"]`.

2. **Call `search_listings()`** with the parsed parameters. Store results in `session["search_results"]`.

3. **Check results:** if `results == []`, set `session["error"]` to a specific actionable message and **return immediately** — `suggest_outfit` is never called with empty input. This is the primary decision point in the loop.

4. **Select top result** — `session["selected_item"] = results[0]`.

5. **Call `suggest_outfit()`** with the selected item and wardrobe. Store result in `session["outfit_suggestion"]`.

6. **Call `create_fit_card()`** with the outfit suggestion and selected item. Store result in `session["fit_card"]`.

7. **Return** the completed session dict.

The agent behaves differently for non-standard inputs: a query like `"designer ballgown size XXS under $5"` exits after step 3 with an error message and never reaches steps 5–6, leaving `outfit_suggestion` and `fit_card` as `None`.

---

## State Management

All state lives in a Python session dict initialized by `_new_session()` and mutated by `run_agent()` as each step completes. No data is re-entered by the user between tools.

| Key | Type | Set when |
|-----|------|----------|
| `query` | str | Initialization |
| `parsed` | dict | After regex query parsing |
| `search_results` | list[dict] | After `search_listings` returns |
| `selected_item` | dict \| None | After selecting `results[0]` |
| `wardrobe` | dict | Initialization (passed in from `app.py`) |
| `outfit_suggestion` | str \| None | After `suggest_outfit` returns |
| `fit_card` | str \| None | After `create_fit_card` returns |
| `error` | str \| None | Set on early exit; `None` on success |

`handle_query()` in `app.py` calls `run_agent()` and reads the returned session dict to populate the three Gradio output panels: `session["selected_item"]` → listing panel, `session["outfit_suggestion"]` → outfit panel, `session["fit_card"]` → caption panel.

---

## Error Handling

### `search_listings` — no matching results

**Failure mode:** All listings are filtered out by price/size, or no listings match any query keywords.

**Agent response:** Sets `session["error"]` to a specific, actionable message and returns early without calling `suggest_outfit`:
> *"No listings found for 'designer ballgown' under $5 in size XXS. Try broader keywords, a higher budget, or remove the size filter."*

**Concrete test example:**
```python
results = search_listings("designer ballgown", size="XXS", max_price=5)
assert results == []  # passes — returns empty list, no exception
```
Running the full agent with `query="designer ballgown size XXS under $5"` populates only the first Gradio panel with the error message; the outfit and caption panels remain empty.

---

### `suggest_outfit` — empty wardrobe

**Failure mode:** `wardrobe["items"]` is an empty list — the user hasn't described any items they own.

**Agent response:** Not treated as a failure. The LLM is prompted for general styling advice instead of wardrobe-specific pairings. Returns a non-empty string describing what types of pieces pair well with the item and what vibe it suits.

**Concrete test example:**
```python
results = search_listings("vintage graphic tee", size=None, max_price=50)
result = suggest_outfit(results[0], get_empty_wardrobe())
assert isinstance(result, str) and len(result.strip()) > 0  # passes
```

---

### `create_fit_card` — missing or empty outfit string

**Failure mode:** `outfit` argument is an empty string or whitespace-only — e.g., if `suggest_outfit` were to return nothing unexpectedly.

**Agent response:** Returns the error string `"Unable to generate a fit card — no outfit suggestion was available."` without raising an exception or calling the LLM.

**Concrete test example:**
```python
results = search_listings("vintage graphic tee", size=None, max_price=50)
result = create_fit_card("", results[0])
assert "unable" in result.lower()  # passes
```

---

## Spec Reflection

**One way the spec helped:** The planning loop description in the project guide was precise enough to use directly as implementation logic: *"After search_listings runs, check if results is empty. If yes, set an error message in the session and return early. If no, set selected_item = results[0] and proceed to suggest_outfit."* That level of specificity meant the Python code in `run_agent()` mapped one-to-one to the spec without ambiguity.

**One way implementation diverged from the spec:** The initial `planning.md` described state management as tracking `tool_call_id` through Gradio's message history — as if the LLM were routing tool calls in a ReAct loop. In practice, the `agent.py` starter code uses a plain Python session dict and calls each tool function directly. The LLM never selects which tool to call next. The spec was updated to reflect the Python-driven architecture, which is simpler to reason about and test.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

I gave Claude the Tool 1 spec block from `planning.md` — including the input parameters with types, the field list from the listing dict, the scoring approach (distinct keyword count across all four fields), and the failure mode (return `[]`, never raise) — and asked it to implement `search_listings()` in `tools.py` using `load_listings()` from the data loader.

**What I reviewed and revised:** The generated implementation used `str.find()` for keyword matching, which would match `"tee"` inside `"coffee"` or `"committee"`. I revised it to use `re.findall(r"\b\w+\b", ...)` for whole-word tokenization on both the query and the listing fields, eliminating false positives. I also verified that `style_tags` (a list) was joined into a string before tokenization, since multi-word tags like `"graphic tee"` needed to be split into individual tokens. I confirmed the fix by running `pytest tests/` against 7 targeted test cases.

### Instance 2 — Implementing `run_agent` and `handle_query`

I gave Claude the Planning Loop, State Management, and Architecture sections from `planning.md` — including the full ASCII diagram showing the decision branch on empty results — and asked it to implement `run_agent()` in `agent.py` and `handle_query()` in `app.py`.

**What I reviewed and revised:** I checked that the generated `run_agent()` inspected `results == []` before calling `suggest_outfit` (the spec's main guard condition), that values were stored in the session dict by key name rather than as local variables, and that the no-results path left `outfit_suggestion` and `fit_card` as `None`. I also reviewed `handle_query()` to confirm it read from the session dict keys rather than re-running any tools, and that the empty-query guard returned a user-facing message rather than passing an empty string to `run_agent()`. I verified the end-to-end flow by running `python agent.py` and checking both test cases printed in the CLI output.
