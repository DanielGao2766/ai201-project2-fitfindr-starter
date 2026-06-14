# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

--- 

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items matching a text description, optional size, and optional price ceiling. Returns results ranked by how many distinct query keywords appear across the listing's title, description, category, and style_tags fields.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Extracted from the natural-language query by the planning loop.
- `size` (str | None): Size string to filter by; matching is case-insensitive substring (e.g., "M" matches "S/M"). Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price, inclusive. Pass `None` to skip price filtering.

**What it returns:**
A `list[dict]` of matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns an empty list `[]` when nothing matches — never raises an exception.

Example result item: `{"id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style", "price": 24.0, "platform": "depop", "condition": "good", ...}`

**What happens if it fails or returns nothing:**
The planning loop checks if results `== []` immediately after the call. If empty, it sets `session["error"]` to a specific, actionable message — e.g., *"No listings found for 'designer ballgown' under $5 in size XXS. Try broader keywords, a higher budget, or remove the size filter."* — and returns the session early. It does **not** call `suggest_outfit` with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item and the user's wardrobe, asks the LLM (llama-3.3-70b-versatile, temperature 0.3) to suggest 1–2 complete outfit combinations. Handles empty wardrobes gracefully by providing general styling advice instead of failing.

**Input parameters:**
- `new_item` (dict): A listing dict — the item the user is considering. Must have at least `title`, `price`, `platform`, `condition`.
- `wardrobe` (dict): A wardrobe dict with an `'items'` key containing a list of wardrobe item dicts. May be empty — handled gracefully.

**What it returns:**
A non-empty string with outfit suggestions in natural language.

- If wardrobe is **not empty**: specific pairings referencing named pieces from the wardrobe — e.g., *"Pair this with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape."*
- If wardrobe is **empty**: general styling advice — what types of pieces pair well, what vibe it suits, 1–2 concrete outfit ideas using common wardrobe staples.

**What happens if it fails or returns nothing:**
An empty wardrobe is **not** treated as an error — the LLM gives general styling advice. The tool returns a non-empty string in both cases. If the LLM call itself fails, the exception propagates to the planning loop which surfaces it as a session error.

---

### Tool 3: create_fit_card

**What it does:**
Generates a 2–4 sentence Instagram/TikTok-style caption for the thrifted find and its outfit. Uses llama-3.3-70b-versatile at temperature 0.8 for variety — running it twice on the same input should produce different captions.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit()`.
- `new_item` (dict): The listing dict for the thrifted item. Fields used in the prompt: `title`, `price`, `platform`, `condition`.

**What it returns:**
A 2–4 sentence string usable as a social media caption. Casual and authentic (not a product description). Mentions item name, price, and platform naturally (once each).

Example: *"thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"*

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns the error string `"Unable to generate a fit card — no outfit suggestion was available."` without raising an exception.

---

### Additional Tools (if any)

None for this submission. Stretch features were not attempted.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop is implemented as a plain Python function `run_agent()` in `agent.py`. The LLM is **not** used to route tool calls — Python conditional logic controls the sequence. The LLM only executes inside `suggest_outfit` and `create_fit_card` as a generation step.

Logic:

1. Parse the user's natural-language query with regex to extract `description`, `size`, and `max_price`. Store in `session["parsed"]`.
2. Call `search_listings(description, size, max_price)`. Store results in `session["search_results"]`.
3. **Check:** if `results == []`, set `session["error"]` to a specific actionable message and **return early**. `suggest_outfit` is never called with empty input.
4. If results are non-empty, set `session["selected_item"] = results[0]` (top-ranked result).
5. Call `suggest_outfit(selected_item, wardrobe)`. Store result in `session["outfit_suggestion"]`.
6. Call `create_fit_card(outfit_suggestion, selected_item)`. Store result in `session["fit_card"]`.
7. Return the session dict.

The agent's behavior is different for non-standard inputs: a query that yields no listings terminates at step 3 and never reaches steps 5–6. This is the primary branch the planning loop handles.

---

## State Management

**How does information from one tool get passed to the next?**

State is stored in a Python session dict initialized by `_new_session()` in `agent.py`. Keys:

| Key | Type | Set when |
|-----|------|----------|
| `query` | str | Initialization |
| `parsed` | dict | After query parsing (`description`, `size`, `max_price`) |
| `search_results` | list[dict] | After `search_listings` returns |
| `selected_item` | dict \| None | After selecting `results[0]` |
| `wardrobe` | dict | Initialization (passed in from `app.py`) |
| `outfit_suggestion` | str \| None | After `suggest_outfit` returns |
| `fit_card` | str \| None | After `create_fit_card` returns |
| `error` | str \| None | Set on early exit; `None` on success |

`run_agent()` returns the completed session dict. `handle_query()` in `app.py` reads `session["selected_item"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` to populate the three Gradio output panels. No data is re-entered by the user between steps.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the description, size, and/or price filter | Sets `session["error"]`: *"No listings found for '[query]'. Try broader keywords, a higher budget, or remove the size filter."* Returns session immediately. `suggest_outfit` is never called. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Not treated as a failure — LLM provides general styling advice (what pairs well with the item, what vibe it suits, 1–2 outfit ideas using common staples). Returns a non-empty string. |
| `create_fit_card` | `outfit` argument is empty or whitespace-only | Returns the error string: `"Unable to generate a fit card — no outfit suggestion was available."` Does not raise an exception. |

---

## Architecture

```
User query
│
▼
Planning Loop (run_agent in agent.py) ───────────────────────────────────────┐
│                                                                            │
│  Step 1: _parse_query(query)                                               │
│          → session["parsed"] = {description, size, max_price}              │
│                                                                            │
├─► search_listings(description, size, max_price)                            │
│       │ results == []                                                      │
│       ├──► [ERROR] session["error"] = "No listings found..." → return ─────┤
│       │                                                                    │
│       │ results = [item, ...]                                              │
│       ▼                                                                    │
│   session["search_results"] = results                                      │
│   session["selected_item"]  = results[0]  ← shown to user in panel 1      │
│       │                                                                    │
├─► suggest_outfit(selected_item, wardrobe)                                  │
│       │                                                                    │
│       ├── wardrobe empty → LLM: general styling advice (not an error)      │
│       ├── wardrobe not empty → LLM: specific pairings from wardrobe        │
│       ▼                                                                    │
│   session["outfit_suggestion"] = "..."  ← shown to user in panel 2        │
│       │                                                                    │
└─► create_fit_card(outfit_suggestion, selected_item)                        │
        │                                                                    │
        ├──► outfit empty → return error string (no exception)               │
        ▼                                                                    │
    session["fit_card"] = "..."  ← shown to user in panel 3                 │
        │                                                                ────┘
        ▼                         error path returns to caller here
    return session
        │
        ▼
handle_query (app.py) maps session keys → three Gradio output panels
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I gave Claude the Tool 1 spec block from planning.md (inputs with types, return value description including field list, failure mode) and the `load_listings()` reference from `utils/data_loader.py`, and asked it to implement `search_listings()` in `tools.py`. Before running it, I checked that the generated code: (1) filters by all three parameters, (2) handles `None` for size and max_price, (3) returns `[]` on no match without raising, and (4) uses whole-word tokenization across all four fields. Then I ran `pytest tests/` to verify: happy path returns a non-empty list, no-match query returns `[]`, price filter holds (`all(item["price"] <= max_price)`), and size filter uses case-insensitive substring matching.

I gave Claude the Tool 2 and Tool 3 spec blocks separately and asked it to implement each function. For `suggest_outfit` I verified the generated code: (1) checks `wardrobe["items"]` before branching, (2) uses different prompts for empty vs non-empty wardrobe, (3) calls the LLM with `llama-3.3-70b-versatile` and `temperature=0.3`. For `create_fit_card` I verified: (1) the empty-string guard runs before the LLM call, (2) `temperature=0.8`, (3) the prompt includes title, price, platform, and condition. I ran `create_fit_card` three times on the same input and confirmed outputs differed.

**Milestone 4 — Planning loop and state management:**

I gave Claude the Planning Loop, State Management, and Architecture sections of this planning.md and asked it to implement `run_agent()` in `agent.py` and `handle_query()` in `app.py`. Before running, I reviewed the generated `run_agent()` to confirm: (1) it checks `results == []` before calling `suggest_outfit`, (2) it stores values in the session dict (not hardcoded), (3) it never calls all three tools unconditionally. I ran `python agent.py` and verified both test cases — the happy path printed a fit card, and the no-results path printed an error message with `session["fit_card"] == None`.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
`run_agent()` calls `_parse_query()` which extracts: `description="I'm looking for a vintage graphic tee"`, `max_price=30.0`, `size=None`. It then calls `search_listings("I'm looking for a vintage graphic tee", size=None, max_price=30.0)`. The function loads all listings, filters to those priced ≤ $30, tokenizes each against the query keywords ["vintage", "graphic", "tee"], and scores by distinct keyword matches across title, description, category, and style_tags. Three listings score > 0. The top result is: `{"title": "Graphic Tee — 2003 Tour Bootleg Style", "price": 24.0, "platform": "depop", "condition": "good", "size": "L", ...}`. This is stored in `session["selected_item"]`.

**Step 2:**
`run_agent()` calls `suggest_outfit(selected_item, wardrobe)`. The wardrobe is non-empty (example wardrobe with 10 items). The LLM receives a prompt listing the item description and a bullet list of wardrobe items. It returns: *"Pair this graphic tee with your baggy straight-leg dark-wash jeans and chunky white sneakers for an effortless streetwear look. Tuck the front corner slightly for shape and add the black crossbody bag to keep it clean."* This is stored in `session["outfit_suggestion"]` and displayed in the "Style It" panel.

**Step 3:**
`run_agent()` calls `create_fit_card(outfit_suggestion, selected_item)`. The LLM receives the item details (title, $24.00, depop, good condition) and the outfit suggestion at temperature 0.8. It returns: *"found this tour bootleg tee on depop for $24 and it was made for my baggy jeans 🖤 graphic tees that actually fit are so rare — full look in my stories"*. This is stored in `session["fit_card"]` and displayed in the "Share It" panel.

**Final output to user:**
All three Gradio output panels populate:
- **Top listing found:** "Graphic Tee — 2003 Tour Bootleg Style / $24.00 · Depop · Good condition / Size: L / Colors: black"
- **Style It:** The outfit suggestion string from Step 2.
- **Share It:** The fit card caption from Step 3.

If Step 1 had returned no results (e.g., query "designer ballgown size XXS under $5"), only the first panel would populate with the error message, and the agent would not have called suggest_outfit or create_fit_card.
