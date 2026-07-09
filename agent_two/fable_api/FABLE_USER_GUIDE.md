# Fable Studio — User Guide

## Overview

Fable Studio is a full-stack AI film production pipeline. It takes a script,
breaks it into individual panels (shots), enriches each panel with
cinematography, storytelling, and author-style context via a multi-agent
system, and generates LTX video prompts for the ComfyUI rendering pipeline.

**Pipeline:**
```
Script → Scene Breakdown → Characters → Assets → Storyboard
    → Panel Generation → LTX Prompt (Multi-Agent RAG-Enhanced)
    → ComfyUI / LTX Video → Final Output
```

---

## Multi-Agent Prompt Architecture

Each panel goes through **four specialized LLM agents** before a prompt is
generated:

```
Panel Data (description, camera, shot type, scene, characters, project vision)
    │
    ├──► CinemaAgent ◄── RAG: cinematography/ (shot types, lighting, lens, composition, color)
    │     Output: [CINEMATOGRAPHY] block
    │
    ├──► StorytellingAgent ◄── RAG: storytelling/ (tropes, narrative structure, pacing)
    │     Output: [STORYTELLING] block
    │
    ├──► AuthorStyleAgent ◄── RAG: authors/ (Spielberg, Fincher, Kubrick, King, etc.)
    │     Output: [AUTHOR STYLE] block
    │
    └──► MasterAgent — synthesizes all three + panel data
          Output: Final structured LTX prompt
```

### Agent Roles

| Agent | Purpose | Model | Default Cost |
|-------|---------|-------|--------------|
| CinemaAgent | Camera movement, lighting, lens, composition, color | gpt-4o-mini | ~$0.001 |
| StorytellingAgent | Narrative function, tone, tropes, pacing, character dynamics | gpt-4o-mini | ~$0.001 |
| AuthorStyleAgent | Author/director visual hallmarks and narrative signatures | gpt-4o-mini | ~$0.001 |
| MasterAgent | Synthesizes all three + panel data into final LTX prompt | gpt-4o | ~$0.025 |
| **Total per panel** | | | **~$0.028** |

### Smart Skipping

- **AuthorStyleAgent** is skipped if `project_vision` contains no known
  director/writer name (18 detected: Spielberg, Fincher, Kubrick,
  Villeneuve, Tarantino, Nolan, Scorsese, Coppola, Anderson, King,
  Clancy, del Toro, Cameron, Scott, Besson, Kurosawa, Hitchcock, Lynch)
- **StorytellingAgent** is skipped if no `scene_summary` or `project_tone`
  is provided

### Parallel Execution

All three sub-agents run concurrently via `ThreadPoolExecutor`, cutting
latency from ~12s to ~8s per panel.

---

## Knowledge Sources (RAG)

Cinematography, storytelling, and author style knowledge lives in the
OKF knowledge bundle at `~/knowledge-bundle/`:

```
knowledge-bundle/
├── index.md
├── cinematography/
│   ├── shot-types.md        — 10 shot scales with LTX prompt templates
│   ├── camera-movements.md   — dolly, pan, track, crane, steadicam, etc.
│   ├── camera-angles.md      — low, high, dutch, overhead, POV
│   ├── lighting-techniques.md — 10 lighting setups by genre
│   ├── composition.md        — rule of thirds, symmetry, leading lines
│   ├── color-theory.md       — color associations, grading styles
│   └── lens-focus.md         — focal length, DOF, rack focus
├── storytelling/
│   ├── narrative-structures.md — three-act, hero's journey, save the cat
│   ├── common-tropes.md       — Chekhov's Gun, redemption arc, MacGuffin
│   ├── genre-conventions.md   — horror, sci-fi, noir, western, rom-com
│   ├── character-archetypes.md — hero, mentor, shadow, trickster
│   └── pacing.md              — tension curves, rhythm, scene types
└── authors/
    ├── spielberg.md    — The Spielberg Face, one-shots, golden hour
    ├── stephen-king.md — small-town horror, mundane evil, Ka-Tet
    ├── tom-clancy.md   — techno-thriller, procedural detail, analyst hero
    ├── kubrick.md      — symmetry, slow zooms, Kubrick stare
    ├── villeneuve.md   — massive scale, silence, off-center framing
    ├── wes-anderson.md — perfect symmetry, color palettes, flat framing
    └── fincher.md      — clinical precision, green/teal, slow dolly
```

Each file is chunked by heading and embedded with `nomic-embed-text` via
Ollama. On query, the RAG engine returns the most semantically relevant
chunks, which are injected into the sub-agent prompts.

To refresh the RAG after adding new knowledge files:

```bash
rm ~/agent_two/fable_api/services/rag/rag_cache.json
# Re-embed on next panel generation, or run:
cd ~/agent_two/fable_api && python3 -c "
from services.rag.knowledge_rag import get_rag
rag = get_rag()
rag.refresh(force=True)
"
```

---

## Workflow Example

### Step 1: Define a Project

Create a project in the Fable frontend (or via API):

```json
POST /api/projects
{
  "title": "The Last Witness",
  "vision": "David Fincher-style psychological thriller",
  "tone": "tense, paranoid, noir"
}
```

The `vision` field triggers the AuthorStyleAgent to retrieve Fincher's
visual hallmarks from the knowledge base.

### Step 2: Upload a Script

Upload or paste a script. The script breakdown service parses scene
headings, character entrances, locations, and times of day.

### Step 3: Panels Are Created

Each scene is broken into panels. A panel has:

```json
{
  "panel_number": 3,
  "panel_type": "closeup",
  "camera_direction": "dolly_in",
  "description": "Detective Mills stares at a wall of evidence photos, strings connecting suspects. He realizes the killer is watching from the window behind him.",
  "scene_heading": "INT. POLICE STATION - NIGHT",
  "location": "Evidence room, precinct",
  "time_of_day": "Night",
  "scene_summary": "Detective realizes the killer is still inside the building",
  "assigned_character_ids": [1, 2]
}
```

### Step 4: Generate the LTX Prompt

Call the generate endpoint:

```http
POST /api/panels/3/generate
```

This triggers the full multi-agent pipeline. Here's what happens internally:

#### What CinemaAgent receives:
```
Panel description: A detective stares at a wall of evidence photos...
Shot type: closeup
Camera direction: dolly_in
Scene summary: Detective realizes the killer is still inside...
Project tone: tense, paranoid
Project vision: David Fincher-style psychological thriller
Scene position: Panel 3/12 — rising action, building tension

Reference Knowledge: [low-key lighting] High contrast between light and shadow.
Deep blacks, single strong key light, minimal fill... [Film Noir] Chiaroscuro,
venetian blind shadows... [David Fincher] Clinical precision, green/teal shadows,
dark underexposed frames, slow smooth dollies.
```

#### What StorytellingAgent receives:
```
Panel description: A detective stares at a wall...
Scene summary: Detective realizes the killer is still inside...
Project tone: tense, paranoid
Scene position: Panel 3/12 — rising action, building tension
Characters:
  Detective Mills: tired determined homicide detective...
```

#### What AuthorStyleAgent receives:
```
Panel description: A detective stares at a wall...
Project vision: David Fincher-style psychological thriller
Project tone: tense, paranoid
```

#### What MasterAgent receives (synthesis):

All three outputs (Cinema, Storytelling, Author blocks) plus the original
panel data. The MasterAgent weaves them together.

#### Final Output:

```
[VISUAL]
Detective Mills stands in the dimly lit evidence room, his weary face
illuminated by harsh overhead light. The wall of evidence photos fills
the frame behind him. He is positioned in the lower third, his intense
eyes scanning the connections. The window behind him is partially
obscured by shadows.

[CINEMATOGRAPHY]
Slow dolly-in toward Mills' face, enhancing tension and paranoia.
As realization dawns, the pace quickens slightly. Low-key lighting casts
oppressive shadows with cool tones. A 50mm lens with shallow depth of
field isolates Mills from the blurred background, heightening emotional
stakes.

[CHARACTER MOTION]
Mills stands rigid, his eyes darting between photos, his expression
shifting from focused determination to dawning horror. His breathing
becomes shallow, his hand trembles slightly.

[SPEECH]
Mills whispers, barely audible. Silence follows, amplifying tension.

[SOUNDS]
Faint hum of fluorescent lights, distant precinct murmur. A subtle,
suspenseful underscore builds as the camera closes in.
```

This prompt is then sent to the ComfyUI/LTX pipeline for video generation.

---

## Scene Position & Continuity

The pipeline accepts optional `panel_number` and `total_panels` to
inform the agents about where on the narrative tension curve the
panel falls:

| Position | Ratio | Label |
|----------|-------|-------|
| Early | 0–25% | Setup / Establishing |
| Rising | 25–45% | Building tension |
| Midpoint | 45–55% | Turning point |
| Late | 55–75% | Approaching climax |
| Final | 75–100% | Climax / Resolution |

Continuity between panels is supported via the optional
`previous_panel_prompt` parameter. Pass the output of panel N as
`previous_panel_prompt` when generating panel N+1 to maintain
consistent lighting, lens, and color palette across a scene.

---

## Environment

### Backend
```
~/agent_two/fable_api/
├── main.py                       — FastAPI app, routes, static mounts
├── database.py                   — SQLAlchemy models
├── schemas.py                    — Pydantic schemas
├── routes/
│   ├── panels.py                 — Panel CRUD + generate endpoint
│   ├── upload.py                 — File upload with panel_id support
│   └── ...
├── services/
│   ├── ltx_prompt_agent.py       — Main agent orchestrator
│   ├── prompt_builder.py         — Entry point for prompt generation
│   ├── agents/
│   │   ├── cinema_agent.py       — CinemaAgent
│   │   ├── storytelling_agent.py — StorytellingAgent
│   │   ├── author_style_agent.py — AuthorStyleAgent
│   │   ├── master_agent.py       — MasterAgent (synthesis)
│   │   └── base_agent.py         — Shared LLM calling
│   └── rag/
│       └── knowledge_rag.py      — Zero-dependency RAG engine
└── static/
    └── theoreticallypose_v4.html — Control video preprocessing
```

### Frontend
```
~/Desktop/app/
├── src/
│   ├── pages/
│   │   ├── ScriptPage.tsx        — Script editor
│   │   ├── CharactersPage.tsx    — Character management
│   │   ├── AssetsPage.tsx        — Asset uploads
│   │   ├── StoryboardPage.tsx    — Storyboard canvas
│   │   ├── PanelDetail.tsx       — Panel editor with Driving Video
│   │   └── ControlVideosPage.tsx — Control video management
│   ├── api/
│   │   └── fable.ts              — API client
│   └── components/
│       └── ...
└── ...
```

### Key Files
```
~/knowledge-bundle/                     — OKF bundle (cinematography, storytelling, authors)
~/Documents/AntMatter/                  — ComfyUI workflows
~/ComfyUI/output/                       — Generated videos
~/FableAssets/uploads/                  — Uploaded assets
```

---

## API Reference

### Generate a Panel Prompt

```
POST /api/panels/{panel_id}/generate
```

Triggers the full multi-agent pipeline. Returns a 202 Accepted with
the panel queued for rendering.

### Key Parameters on `generate_panel_ltx_prompt()`

```python
generate_panel_ltx_prompt(
    description="...",          # Panel description text
    camera_direction="dolly_in", # 16 supported directions
    panel_type="closeup",        # wide / medium / closeup / insert
    scene_heading="INT. OFFICE - NIGHT",
    location="Precinct evidence room",
    time_of_day="Night",
    scene_summary="Detective realizes...",
    character_descriptions=[...],
    project_vision="Fincher-style thriller",
    project_tone="tense, noir",
    mode="image-to-video",
    panel_number=3,              # Scene position (optional)
    total_panels=12,             # Total in scene (optional)
    previous_panel_prompt="...",  # Continuity (optional)
)
```

### Supported Camera Directions

| Direction | Description |
|-----------|-------------|
| `pan_left` / `pan_right` | Horizontal reveal |
| `dolly_in` | Push toward subject |
| `dolly_out` | Pull back / reveal |
| `track_left` / `track_right` | Parallel movement |
| `crane_up` / `crane_down` | Vertical rise / lower |
| `tilt_up` / `tilt_down` | Vertical angle shift |
| `static` | Locked-off tripod |
| `handheld` | Documentary feel |
| `steadicam` | Smooth gimbal follow |
| `dolly_zoom` | Vertigo effect |
| `whip_pan` | Fast disorienting move |
| `aerial` | Drone / bird's-eye |

---

## Adding Knowledge

To extend the RAG with new domains:

1. Create a directory in `~/knowledge-bundle/` (e.g. `sound-design/`)
2. Add markdown files with `##` heading-based sections
3. Add the domain name to `DOMAINS` in `knowledge_rag.py`
4. Delete `rag_cache.json` to force re-embedding

Each file should have YAML frontmatter:
```yaml
---
type: Reference
title: My Topic
description: Brief description
tags: [category, subtopic]
timestamp: 2026-07-08
---
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| RAG returns no results | Cache missing or stale | `rm rag_cache.json` and re-generate |
| All agents fall back to template | OPENROUTER_API_KEY missing | Check `~/.hermes/.env` |
| CinemaAgent output is generic | RAG not finding relevant chunks | Add more specific knowledge files |
| Pipeline too slow | Sequential fallback (parallel failed) | Check agent error logs |
| Author style not applied | Name not in KNOWN_AUTHORS list | Add to list in `ltx_prompt_agent.py` |