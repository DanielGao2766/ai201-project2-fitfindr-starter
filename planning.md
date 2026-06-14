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
<!-- Describe what this tool does in 1–2 sentences -->
It searches the database for suitable matches based on the descriptions given by the user prompt. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The keywords for the type of clothing. 
- `size` (str): The size required for the clothing. 
- `max_price` (float): The number that the `price` cannot be higher than

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
It contains a list of all the possible items ranked with all the results being avilable in the format: "Faded Band Tee — $22, Depop, Good condition."

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The agent states that the search_listings tool was unable to find any matches and recemmeneds the user tries other options for that specific piece of clothing. If there is empty input, the agent stops. It does not call suggest_outfit with empty input. 
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
It creates pairings for new items with already items that you already own. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The item that is being paired with.
- `wardrobe` (dict): The database containing all the items that you already own. This one is different from the database of all the listings for new items. 

**What it returns:**
<!-- Describe the return value -->
It returns a string with a sentence recommendation from the LLM based on what is avilable in the wardrobe in this format: "Pair this with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape."

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
The agent should explicitly state that the suggest_outfit tool found no suitable pairings for the new item.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Creates captions for new items that you buy. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...):  The outfit from the suggest_outfit tool

**What it returns:**
<!-- Describe the return value -->
Creates a caption for new items in this format: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If outfit data is incomplete, the agent should explicitly tell the user that the create_fit_card tool was unable to create a fit card. 

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
After search_listings runs, check if results is empty. If yes, set an error message in the session and return early. If no, set selected_item = results[0] and proceed to suggest_outfit. Then after suggest_outfit runs, check if result is empty. If yes, set the error message as provided above and return early with the prior results, otherwise take the outfit string from suggest_outfit and proceed to create_fit_card. At create_fit_card, check for errors as decscribed above, otherwise once the tool is finished pass the final result back to the agent to output a result. 
---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
I use gradio to track tool_call_id, which gives the assistant message and then the tool results for each time the agent loops. 

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

     User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │       ├──► [ERROR] "Empty wardrobe" → return item  │
    │       ├──► [ERROR] "Unable to match" → return item │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
            ├──► [ERROR] "Missing outfit" → return item  │
        Session: fit_card = "..."                        ▼
            │                                 error path returns here following error message based on the specific tool as outlineed above
            ▼
        Return session

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it.

**Milestone 4 — Planning loop and state management:**
     "I'll give Claude my planning loop, state management, error handling, and architecture portions of the planning.md to give a high level overview of my vision and ask it to implement agent.py and app.py with that information. Then I'll ask it to test the system against 3 queries before trusting it. 


---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
It finds that it doesn't have enough information to generate a relevant response so it calls the search_listings tool to get the listings, 
The parameters would be search_listings("vintage graphic tee", size = M, max_price = 30.0)

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:**
<!-- Continue until the full interaction is complete -->

**Final output to user:**
<!-- What does the user actually see at the end? -->
