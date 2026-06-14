"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive substring (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Filter by price ceiling
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Filter by size — case-insensitive substring match
    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Tokenize the query into a set of lowercase whole words
    query_tokens = set(re.findall(r"\b\w+\b", description.lower()))

    def _listing_tokens(listing: dict) -> set[str]:
        """Return all whole-word tokens from a listing's searchable text fields."""
        text = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
        ])
        return set(re.findall(r"\b\w+\b", text.lower()))

    def _score(listing: dict) -> int:
        """Count how many distinct query keywords appear in the listing's tokens."""
        listing_tokens = _listing_tokens(listing)
        return sum(1 for kw in query_tokens if kw in listing_tokens)

    # Score, drop zero-score listings, sort descending
    scored = [(s, l) for l in listings if (s := _score(l)) > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handled gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice rather than
        raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_desc = (
        f"{new_item['title']} "
        f"(${new_item['price']:.2f}, {new_item['platform']}, "
        f"{new_item['condition']} condition)"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"You are a personal stylist. A user just found this thrifted item: {item_desc}.\n\n"
            "They haven't described their wardrobe yet, so give them general styling advice: "
            "what types of pieces pair well with this item, what vibe or aesthetic it suits, "
            "and 1–2 concrete outfit ideas using common wardrobe staples.\n\n"
            "Keep it casual and specific — like advice from a friend who knows fashion, "
            "not a product description. Under 120 words."
        )
    else:
        wardrobe_list = "\n".join(f"- {item['name']}" for item in wardrobe_items)
        prompt = (
            f"You are a personal stylist. A user just found this thrifted item: {item_desc}.\n\n"
            f"Their wardrobe includes:\n{wardrobe_list}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific pieces "
            "from their wardrobe. Name the exact wardrobe pieces. Add a brief styling note "
            "(e.g., tuck here, cuff there, layer with). "
            "Keep it casual and under 120 words."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.

    The caption:
    - Feels casual and authentic (like a real OOTD post)
    - Mentions item name, price, and platform naturally (once each)
    - Captures the outfit vibe in specific terms
    - Sounds different each time (temperature 0.8)
    """
    if not outfit or not outfit.strip():
        return "Unable to generate a fit card — no outfit suggestion was available."

    client = _get_groq_client()

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this outfit.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']:.2f}\n"
        f"Found on: {new_item['platform']}\n"
        f"Condition: {new_item['condition']}\n"
        f"Outfit description: {outfit}\n\n"
        "Rules:\n"
        "- Sound casual and authentic, like a real OOTD post — not a product description\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the outfit vibe in specific, evocative terms\n"
        "- Write flowing sentences, not a list\n"
        "- Keep it under 80 words\n"
        "- Do not add hashtags"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()
