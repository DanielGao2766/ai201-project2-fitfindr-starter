"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural-language query
    using regex. Returns a dict with keys: description, size, max_price.

    Examples:
        "vintage graphic tee under $30, size M"
            → {description: "vintage graphic tee", size: "M", max_price: 30.0}
        "90s track jacket in size M"
            → {description: "90s track jacket", size: "M", max_price: None}
        "flowy midi skirt under $40"
            → {description: "flowy midi skirt", size: None, max_price: 40.0}
    """
    description = query

    # --- Extract max_price ---
    # Matches: "under $30", "under 30", "less than $40", "below $25", "max $50"
    price_pattern = re.compile(
        r"\b(?:under|less\s+than|below|max)\s*\$?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    price_match = price_pattern.search(query)
    # Fallback: bare "$30"
    if not price_match:
        price_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", query)

    max_price = float(price_match.group(1)) if price_match else None

    # --- Extract size ---
    # Matches: "size M", "in size M", "size 8" — order matters: longer tokens first
    size_pattern = re.compile(
        r"\b(?:in\s+)?size\s+(xxs|xxl|xs|xl|s/m|m/l|s|m|l|\d{1,2}(?:\.\d)?)\b",
        re.IGNORECASE,
    )
    size_match = size_pattern.search(query)
    # Fallback: "in M" without the word "size"
    if not size_match:
        size_match = re.search(
            r"\bin\s+(xxs|xxl|xs|xl|s/m|m/l|s|m|l)\b",
            query,
            re.IGNORECASE,
        )

    size = size_match.group(1).upper() if size_match else None

    # --- Build clean description ---
    # Remove the matched price phrase
    if price_match:
        description = price_pattern.sub("", description)
        description = re.sub(r"\$\s*\d+(?:\.\d+)?", "", description)
    # Remove the matched size phrase
    if size_match:
        description = size_pattern.sub("", description)
        description = re.sub(
            r"\bin\s+(?:xxs|xxl|xs|xl|s/m|m/l|s|m|l)\b", "", description, flags=re.IGNORECASE
        )

    # Normalize whitespace and trailing punctuation
    description = re.sub(r"\s+", " ", description).strip(" ,.-")

    return {
        "description": description if description else query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and outfit_suggestion
        and fit_card will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query
    session["parsed"] = _parse_query(query)
    parsed = session["parsed"]

    # Step 3: Search listings — guard against empty results before proceeding
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        # Build a specific, actionable error message
        parts = []
        if parsed["description"]:
            parts.append(f"'{parsed['description']}'")
        if parsed["max_price"] is not None:
            parts.append(f"under ${parsed['max_price']:.0f}")
        if parsed["size"]:
            parts.append(f"in size {parsed['size']}")
        query_desc = " ".join(parts) if parts else f"'{query}'"
        session["error"] = (
            f"No listings found for {query_desc}. "
            f"Try broader keywords, a higher budget, or remove the size filter."
        )
        return session

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit — always returns a string (empty wardrobe → general advice)
    session["outfit_suggestion"] = suggest_outfit(results[0], wardrobe)

    # Step 6: Generate fit card — guards against empty outfit internally
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
