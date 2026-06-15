"""
filtersafe.py — content-filter-safe prompt language (harvested + adapted).
================================================================================
Image/video model filters flag the COMBINATION of trigger signals, not single
words. This module does two things:

  1. safe_text(text)  → swap known trigger phrases for neutral cinematic language
  2. check_stacking(text) → warn when one sentence stacks >2 trigger categories

Source methodology: Tim Simmons / Theoretically Media "Filter Safety Guide."
The default SWAPS use an action/crime-thriller as the running example (that genre
stacks the most triggers). They're a starting set — override per project via
load_swaps() so the language fits YOUR story.

Used two ways in Agent One:
  • Director: run prompts through safe_text() before dispatch (pre-render pass)
  • Reviewer (Phase 4): check_stacking() as a warn-level QA check

Stdlib only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

# ── default swaps (avoid → use). "" means OMIT the term entirely. ───────────
# First alternative chosen where the guide lists several. Phrases before words.
DEFAULT_SWAPS: dict[str, str] = {
    # genre & setting
    "yakuza compound": "traditional Japanese noble clan compound",
    "criminal empire": "dynasty",
    "organized crime": "",
    "yakuza": "noble clan",
    "hideout": "estate",
    "cartel": "house",
    "gang": "clan",
    "mob": "family",
    "lair": "compound",
    # characters & tone
    "coiled danger": "quiet intensity",
    "predatory": "poised",
    "predator": "poised",
    "dangerous": "focused",
    "betrayal": "history between them",
    "assassin": "",
    "lethal": "precise",
    "revenge": "",
    "killer": "",
    # action & movement
    "cutting down": "confronting",
    "mid-strike": "in motion",
    "slicing": "engaging",
    "bloodied": "drawn",
    "violence": "intensity",
    "violent": "intense",
    "brutal": "grounded",
    "savage": "raw",
    "killing": "",
    "killed": "",
    "bodies": "fallen figures",
    "wound": "",
    "injury": "",
    "assault": "advance",
    "assaults": "advances",
    "attack": "approach",
    "attacks": "approaches",
    "attacking": "approaching",
    "battle": "encounter",
    "fight": "sequence",
    "kill": "",
    # weapons
    "flamethrower": "industrial torch",
    "weapon": "prop",
    "katana": "heirloom blade",
    "armed": "carrying",
    # outfit & appearance
    "bralette": "fitted top",
    "seductive": "striking",
    "revealing": "fitted",
    "exposed": "sleeveless",
    "harness": "tactical rig",
    "sexy": "confident",
    "bra": "fitted top",
}

# trigger categories for the stacking check
_CATEGORIES = {
    "weapon": ["blade", "sword", "katana", "gun", "rifle", "pistol", "knife",
               "weapon", "flamethrower", "firearm"],
    "action": ["strike", "slicing", "cutting", "fight", "attack", "assault",
               "kill", "charge", "lunge", "stab", "slash"],
    "appearance": ["harness", "bralette", "revealing", "exposed", "sexy",
                   "seductive", "torn", "bare"],
    "threat": ["lethal", "dangerous", "deadly", "brutal", "savage", "predator",
               "predatory", "menacing", "vicious"],
}


def load_swaps(path: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    """Default swaps merged with a project JSON file and/or an extra dict.
    Per-project file lets each story use its own neutral vocabulary."""
    swaps = dict(DEFAULT_SWAPS)
    if path and Path(path).exists():
        try:
            swaps.update(json.loads(Path(path).read_text(encoding="utf-8")))
        except Exception:
            pass
    if extra:
        swaps.update(extra)
    return swaps


def _collapse_ws(s: str) -> str:
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)   # no space before punctuation
    return re.sub(r"\s{2,}", " ", s).strip()


def safe_text(text: str, swaps: Optional[dict] = None) -> dict:
    """Apply filter-safe swaps. Returns {text, changed, replacements}.
    Whole-word, case-insensitive; longer phrases applied first."""
    if not text:
        return {"text": text, "changed": False, "replacements": []}
    table = swaps if swaps is not None else DEFAULT_SWAPS
    out = text
    replacements = []
    for avoid in sorted(table, key=len, reverse=True):
        use = table[avoid]
        pattern = re.compile(r"\b" + re.escape(avoid) + r"\b", re.IGNORECASE)
        if pattern.search(out):
            out = pattern.sub(use, out)
            replacements.append({"from": avoid, "to": use or "(removed)"})
    out = _collapse_ws(out)
    return {"text": out, "changed": out != text, "replacements": replacements}


def check_stacking(text: str, limit: int = 2) -> list[dict]:
    """Flag sentences that stack more than `limit` trigger categories.
    Returns a list of findings (severity warn)."""
    findings = []
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    for i, sent in enumerate(sentences):
        low = sent.lower()
        hit = [cat for cat, kws in _CATEGORIES.items() if any(k in low for k in kws)]
        if len(hit) > limit:
            findings.append({
                "check": "filter_safety", "severity": "warn",
                "message": (f"sentence {i+1} stacks {len(hit)} trigger categories "
                            f"({', '.join(hit)}) — spread them across prompt sections"),
            })
    return findings


def make_safe(text: str, swaps: Optional[dict] = None) -> str:
    """Convenience: return just the cleaned text."""
    return safe_text(text, swaps)["text"]
