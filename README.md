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

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (highest first).  Returns `Try broader keywords, a higher budget, or remove the size filter`, if nothing matches.

**Scoring:** The query is tokenized into whole words (lowercase). Each listing is scored by how many distinct query keywords appear across its `title`, `description`, `category`, and `style_tags` fields. Listings that match zero keywords are excluded.

---

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

**Purpose:** Given a thrifted item and the user's wardrobe, uses an LLM to suggest 1–2 complete outfit combinations. 

**Inputs:**
- `new_item` (dict) — a listing dict from `search_listings`. Fields used in the prompt: `title`, `price`, `platform`, `condition`.
- `wardrobe` (dict) — wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. May be empty.

**Output:** A non-empty string with outfit suggestions.
- Non-empty wardrobe: specific pairings referencing named pieces from the wardrobe — *"Pair this with your baggy dark-wash jeans and chunky white sneakers for a streetwear look. Tuck the front corner slightly for shape."*
- Empty wardrobe: general styling advice — what pairs well with the item, what vibe it suits, 1–2 outfit ideas using common staples.

**Model:** `llama-3.3-70b-versatile`, temperature `0.3`.

---

### `create_fit_card(outfit: str, new_item: dict) → str`

**Purpose:** Generates a 2–4 sentence Instagram/TikTok-style caption for the thrifted find and its outfit.

**Inputs:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict) — the listing dict. Fields used in the prompt: `title`, `price`, `platform`, `condition`.

**Output:** A casual, authentic-sounding caption that mentions the item name, price, and platform  — e.g., *"found this tour bootleg tee on depop for $24 and it was made for my baggy jeans — graphic tees that actually fit are so rare."*

If `outfit` is empty or whitespace-only, returns `"Unable to generate a fit card — no outfit suggestion was available."`

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

**One way implementation diverged from the spec:** In the inital `planning.md` I described a a `tool_call_id` through Gradio's message history similar to how the lab2-plantadvisor works, but after looking at the requirements in the `agent.py` specifications I realized tha thte python session calls each tool directly and the LLM never slects which tool to call next. 

---

## AI Usage

### Instance 1 — Implementing `search_listings`

I gave Claude the Tool 1 spec block from `planning.md` — including the input parameters with types, the field list from the listing dict, the scoring approach, and the failure mode and asked it to implement `search_listings()` in `tools.py` using `load_listings()` from the data loader.

**What I reviewed and revised:** The generated implementation used `str.find()` for keyword matching, which would match `"tee"` inside `"coffee"` or `"committee"`. I revised it to get whole-word tokenization on both the query and the listing fields, eliminating false positives.

### Instance 2 — Implementing `run_agent` and `handle_query`

I gave Claude the Planning Loop, State Management, and Architecture sections from `planning.md` — including the full ASCII diagram showing the decision branch on empty results — and asked it to implement `run_agent()` in `agent.py` and `handle_query()` in `app.py`.

**What I reviewed and revised:** I created tests in the tests folder under `test_tools.py` to independently verify the results of the output based on the `planning.md` to double check the code. 
