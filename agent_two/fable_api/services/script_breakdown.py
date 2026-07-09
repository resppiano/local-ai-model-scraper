"""
Script Breakdown Service
========================
Parses screenplay text into individual scenes by splitting on
standard screenplay heading patterns (INT., EXT., INT./EXT.).
"""

import re
from typing import List, Dict, Optional


# Regex for screenplay scene headings: INT./EXT./INT./EXT. at start of line
# Group 1: full heading (e.g. "INT. OFFICE - NIGHT")
# Group 2: location (e.g. "OFFICE")
# Group 3: time of day (e.g. "NIGHT")
HEADING_PATTERN = re.compile(
    r"^(INT\./EXT\.|INT\.|EXT\.)\s+(.+?)(?:\s*[-–—]\s*(.+?))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_script(
    text: str, base_scene_number: int = 1
) -> List[Dict[str, Optional[str]]]:
    """
    Parse screenplay text into a list of scene dicts.

    Each dict contains:
      - heading (str): the full scene heading line
      - location (str or None): location part of the heading
      - time_of_day (str or None): time of day if present
      - summary (str or None): first 200 chars of scene body

    Returns empty list if no headings found.
    """
    scenes: List[Dict[str, Optional[str]]] = []

    # Find all heading matches with their positions
    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        return scenes

    for i, match in enumerate(matches):
        heading = match.group(0).strip()
        location = (match.group(2) or "").strip()
        time_of_day = (match.group(3) or "").strip() if match.group(3) else None

        # Determine scene body (text between this heading and the next)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # Basic summary: first 200 chars of body
        summary = body[:200].strip() if body else None
        if summary and len(body) > 200:
            summary += "..."

        scenes.append(
            {
                "heading": heading,
                "location": location if location else None,
                "time_of_day": time_of_day,
                "summary": summary,
            }
        )

    return scenes


def format_scene_heading(heading: str) -> str:
    """Clean up a scene heading (remove extra whitespace, normalize dashes)."""
    heading = re.sub(r"\s+", " ", heading).strip()
    heading = re.sub(r"\s*[-–—]+\s*", " - ", heading)
    return heading