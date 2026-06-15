#!/usr/bin/env python3
"""
Filmake Agent One — REAL RENDER TEST (Wan 2.1 + SDXL)
=======================================================
Creates a project, registers shots, and renders them through ComfyUI.
  • Still shots → SDXL Lightning (~3s each)
  • Video shots → Wan 2.1 T2V 1.3B (~170s each)
"""

import sys, os, shutil, time

sys.path.insert(0, ".")

import comfyui_renderer  # auto-registers on import

from phases import handle_phase_tool

PROJ = "wan_render_test"


def call(tool, args):
    args.setdefault("project", PROJ)
    return handle_phase_tool(tool, args)


def section(title):
    print(f"\n{'─'*60}\n  {title}\n{'─'*60}")


# ── Cleanup ──
brain_dir = os.environ.get("AGENT_ONE_BRAIN_DIR", "brain_data")
for f in [f"{PROJ}.brain.json", f"{PROJ}.shots.json", f"{PROJ}.rules.json"]:
    p = os.path.join(brain_dir, f)
    if os.path.exists(p):
        os.remove(p)

print("=" * 60)
print("  FILMAKE — REAL RENDER TEST (Wan 2.1 + SDXL)")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
section("1. Create project + visual language")
# ═══════════════════════════════════════════════════════════════

call("start_project", {
    "project": PROJ,
    "title": "Neon Requiem",
    "logline": "A retired safecracker is pulled back for one last job.",
    "vision": "Neo-noir heist thriller. Rain-slicked streets, neon reflections.",
    "tone": "brooding, tense",
    "genre": "neo-noir",
    "format": "short film",
})
print("  ✓ Project created")

call("set_visual_language", {
    "look": "Desaturated teal/amber split tone, heavy 35mm grain, anamorphic",
    "palette": ["#1a3a4a", "#d4a843", "#0d0d0d"],
    "lensing": "anamorphic 2.39:1, shallow DOF",
    "lighting": "practical only — neon signs, sodium vapor streetlights",
    "film_stock": "35mm Kodak Vision3 500T, pushed 1 stop, heavy grain",
    "grade": "teal shadows, warm amber highlights, crushed blacks",
    "framing": "wide establishing shots, tight inserts, one-point perspective",
    "avoid": ["clean digital look", "oversaturated colors", "neon pink cyberpunk"],
})
print("  ✓ Visual language set")

call("add_to_bible", {
    "character": "Ray",
    "role": "protagonist",
    "description": "50s, ex-safecracker. Weathered face, grey stubble, deep-set eyes.",
    "look": "Dark wool peacoat, dark earth tones. Scar above left eyebrow.",
})
call("add_to_bible", {
    "character": "Mara",
    "role": "catalyst",
    "description": "30s, sharp and composed. Red lipstick is her only color.",
    "look": "Black trench coat, dark hair pulled back. Red lips.",
})
print("  ✓ Characters added (Ray, Mara)")

# ═══════════════════════════════════════════════════════════════
section("2. Set render tier to LOCAL")
# ═══════════════════════════════════════════════════════════════

r = call("set_render_tier", {"tier": "local"})
print(f"  ✓ {r}")

# ═══════════════════════════════════════════════════════════════
section("3. Register shots (mix of stills and video)")
# ═══════════════════════════════════════════════════════════════

shots = [
    # VIDEO: Ray approaches the diner
    {
        "id": "S1E01_001",
        "order": 1,
        "spec": {"subject": "establishing", "style": "photoreal",
                 "camera_move": "static", "fidelity": "hero",
                 "duration_seconds": 2.5, "motion": "low"},
        "content": {"prompt": "Cinematic neo-noir. A lone figure in a dark peacoat walks "
                              "slowly down a rain-slicked city street at night. A neon diner "
                              "sign casts red and amber reflections in puddles on the wet "
                              "asphalt. Heavy atmospheric haze. Sodium vapor streetlights "
                              "cast pools of amber. Low angle camera, tracking slowly. "
                              "Moody, brooding, film grain."},
        "characters": ["Ray"],
        "location": "diner_exterior",
    },
    # STILL: Diner interior — Ray and Mara
    {
        "id": "S1E01_002",
        "order": 2,
        "spec": {"subject": "still", "still": True, "style": "photoreal",
                 "fidelity": "hero"},
        "content": {"prompt": "Interior diner booth, two-shot. A weathered man in his 50s "
                              "sits across from a woman in a black trench coat with striking "
                              "red lipstick. Neon light from the window backlights the woman. "
                              "A manila envelope lies on the formica table. Overhead sodium "
                              "vapor lamp. Shallow DOF, 35mm grain, crushed blacks. "
                              "Teal shadows, amber highlights."},
        "characters": ["Ray", "Mara"],
        "location": "diner_interior",
    },
    # STILL: The envelope close-up
    {
        "id": "S1E01_003",
        "order": 3,
        "spec": {"subject": "broll", "still": True, "style": "photoreal",
                 "fidelity": "hero"},
        "content": {"prompt": "Extreme close-up of weathered hands pushing a manila "
                              "envelope across a worn formica diner table. Only the hands "
                              "and envelope in focus. Teal shadows, amber highlights from "
                              "overhead light. Heavy 35mm film grain. Shallow depth of field."},
        "characters": ["Ray"],
        "location": "diner_interior",
    },
    # VIDEO: The Calder Building
    {
        "id": "S1E01_004",
        "order": 4,
        "spec": {"subject": "establishing", "style": "photoreal",
                 "camera_move": "static", "fidelity": "hero",
                 "duration_seconds": 3, "motion": "low"},
        "content": {"prompt": "Cinematic establishing shot. A brutalist concrete office "
                              "tower looms against a dark night sky. A single amber security "
                              "light above a service entrance. Rain falls through the light "
                              "beam. Low angle looking up at the building. Oppressive scale. "
                              "Desaturated teal shadows, heavy grain. Ominous mood."},
        "location": "calder_exterior",
    },
]

for s in shots:
    r = call("add_shot", s)
    media = "VIDEO" if not s["spec"].get("still") else "STILL"
    print(f"  ✓ {s['id']} [{media}]: registered")

# ═══════════════════════════════════════════════════════════════
section("4. Route preview")
# ═══════════════════════════════════════════════════════════════

for s in shots:
    r = call("route_preview", s["spec"])
    backend = r.split("→")[1].split("[")[0].strip() if "→" in r else "?"
    print(f"  {s['id']}: → {backend}")

# ═══════════════════════════════════════════════════════════════
section("5. RENDER — SDXL for stills, Wan 2.1 for video")
# ═══════════════════════════════════════════════════════════════

print("  Rendering all shots through the GPU pipeline...")
print("  (stills ~3s each, video ~170s each)\n")
t0 = time.time()

r = call("rerender", {"shot_ids": [s["id"] for s in shots]})
elapsed = time.time() - t0

print(f"\n  {r}")
print(f"\n  ⏱  Total render time: {elapsed:.1f}s")

# ═══════════════════════════════════════════════════════════════
section("6. Verify outputs")
# ═══════════════════════════════════════════════════════════════

r = call("list_shots", {})
print(r)

output_dir = os.path.expanduser("~/ComfyUI/output")
filmake_files = sorted([
    f for f in os.listdir(output_dir)
    if f.startswith("filmake_S1E01_") and not f.startswith("filmake_S1E01_00")
])
if not filmake_files:
    filmake_files = sorted([
        f for f in os.listdir(output_dir)
        if f.startswith("filmake_S1E01")
    ])

print(f"\n  Output files ({len(filmake_files)}):")
for f in filmake_files:
    full = os.path.join(output_dir, f)
    size = os.path.getsize(full)
    ext = os.path.splitext(f)[1]
    kind = "VIDEO" if ext == ".webp" else "IMAGE"
    print(f"    [{kind}] {f}  ({size/1024:.0f} KB)")

# ═══════════════════════════════════════════════════════════════
section("7. Review")
# ═══════════════════════════════════════════════════════════════

r = call("review_report", {})
print(r)

print("\n" + "=" * 60)
print("  REAL RENDER TEST COMPLETE")
print("=" * 60)
