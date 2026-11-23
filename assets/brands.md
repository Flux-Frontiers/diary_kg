# Flux-Frontiers -- Brand Identity

This document covers two product families:

1. **KG Family** -- the knowledge-graph packages. Since November 2026 each
   wears an Art Techno mark drawn in code; the cybernetic-brain logos are
   retired.
2. **WaveRider Family** -- geometric ML and manifold-aware optimization.
   Visual metaphor: a curved manifold surface with an extrinsic observer
   hovering above. Unchanged; see the end of this document.

---

## KG Family -- Art Techno marks

Art Techno does for the computer age what Art Deco did for the machine age.
The style rules, palette and motif lexicon live in the Art Techno repository,
[`docs/STYLE.md`](https://github.com/Flux-Frontiers/art_techno/blob/main/docs/STYLE.md);
this section covers only how the KG marks use them.

**One mark per repo, drawn from what that repo stores.** Every mark radiates
from a chip die (rule 1: the sun is a processor), routes its traces at 0, 45
and 90 degrees, and ends every free line in a pad or via. No two marks share a
motif, so the family reads as one style without the modules looking
identical.

**Shared structure.**

- Square mark, 512 units: a double gold frame with 45-degree corners and a
  solder-green diamond at each corner; the motif; the name in Josefin Sans
  SemiBold capitals tracked +200; a tagline below in IBM Plex Mono capitals,
  mint.
- Icon, 64 units: the motif reduced to its largest parts in a single heavy
  frame, with no lettering. Every size of 64 px and below is cut from it.
- Banner, 1280 x 320: the motif left, the name set as large as the space
  beside it allows, the tagline at the same width, the pair centered on the
  banner's height. The README header of each repo shows the banner.
- Lettering is outlined to paths, so the SVGs render the same everywhere,
  including on GitHub.

**Palette.** The seven Art Techno tokens only, on an obsidian ground:

| Token | Hex | Role in the marks |
|---|---|---|
| Obsidian | `#0B100E` | Ground |
| Panel | `#121A17` | Chip packages, cards, pages |
| Copper | `#C77C48` | Secondary traces, member chips, user turns |
| Gold | `#D4AF5A` | Frames, primary traces, pads, the name |
| Solder green | `#2F8F74` | Dies and pad cores, under 10% of area |
| Mint | `#7FBFA8` | The tagline |
| Silkscreen | `#EDE6D3` | The die's lit core |

**The marks.**

| Repo | Mark | Tagline | Built by |
|---|---|---|---|
| `gutenberg_kg` | The open book: four traces notched at the gutter, a die in the gutter, a graph fan rising from it | THE KNOWLEDGE PRESS | `scripts/build_logo.py` |
| `doc_kg` | The outline: a page whose content is its own graph, document die, section nodes, chunk chains | DOCUMENTS AS A GRAPH | `scripts/build_logo.py` |
| `diary_kg` | The nib: a pen nib with a die for its breather hole, writing a line of dated nodes over a clock wave | A LIFE, ENTRY BY ENTRY | `scripts/build_logo.py` |
| `kgrag` | The federation fan: five member chips on thin traces into one large chip, three spokes fanning out | ONE QUERY, MANY GRAPHS | `scripts/build_logo.py` |
| `pycode_kg` | The call tree: a module die containing two classes of two functions each, one copper call edge across | PYTHON CODE AS A GRAPH | `scripts/build_logo.py` |
| `agent_kg` | The dialogue: user and agent turns on one bus into a memory die, topic, entity and task nodes below | CONVERSATION AS MEMORY | `scripts/build_logo.py` |
| `imagewright` | The contract: three prompt lines into a die, one gold line out to a framed picture, a lighthouse whose lamp room is the die | PROMPT IN, PICTURE OUT | `scripts/build_logo.py` |

The KGRAG app keeps its owl (`kg_rag/owl.py`) as a live status avatar; the
owl is the app's voice, not the logo. Most other fleet repos now draw their
own mark the same way; all of them, with the shared Flux-Frontiers fleet icon
and the baseline banners, are in `kgrag_priv/brands/`.

**Rebuilding.** Each repo's `scripts/build_logo.py` imports the palette,
drawing helpers and lettering from a clone of `art_techno` beside the repo
(`art_techno/docs/brand/build.py`), renders PNGs with headless Chrome, and
writes every size the repo uses. Edit the motif or tagline there and rerun:

```bash
python scripts/build_logo.py
```

**Adding a mark for a new repo.** Draw three or four candidates on one page,
each built from that repo's own graph model, and pick one; then copy a
sibling's `build_logo.py` and replace the motif, the name and the tagline.

---

## WaveRider Family

WaveRider is a separate product family from the KG stack — geometric ML rather than knowledge graphs. It shares the Flux-Frontiers brand strategy (flat vector, transparent background, no shading, wordmark below, square 1024x1024) but uses a different central metaphor: **the manifold and its observer**, drawn directly from the technical substance — TurtleND's orthonormal frame, ManifoldWalker's tangent-step trajectory, ManifoldObserver hovering at altitude in the (N+1)-dim ambient space.

**Shared rules (WaveRider):**
- Central element: a curved triangulated manifold surface (saddle-shaped, ~8×6 quads), three-quarter perspective, in cool steel-blue `#5B7FA8` wireframe + lighter translucent face fill `#A8C0D8`
- Trajectory: 6 glowing coral nodes (`#FF6B35`) connected by short straight edges, bending with the curvature
- Tangent frame: at the latest trajectory node — two short perpendicular arrows on the tangent plane, coral
- Observer: an upward-pointing triangle with circular "eye" inset, hovering above; three thin sensor lines descend to specific trajectory nodes
- Axis hint: tiny `e₁`, `e₂`, `e₃` labels in lower-left corner — implies higher-dim ambient
- Wordmark: Futura sans-serif, coral `#FF6B35`; subtitle in steel-blue `#5B7FA8`
- Background: fully transparent (PNG with alpha)
- No gradients, no drop shadows, no 3D shading on the mesh, no lens flares
- Square composition, 1024x1024

### Color Palette (WaveRider)

| Element | Color | Hex |
|---|---|---|
| Manifold wireframe | Steel-blue | `#5B7FA8` |
| Manifold face fill | Pale steel-blue | `#A8C0D8` |
| Trajectory + tangent frame + wordmark | Coral / sunset | `#FF6B35` |
| Observer body | Deep navy | `#1E3A5F` |
| Observer eye pupil | Coral | `#FF6B35` |
| Subtitle, axis labels | Steel-blue | `#5B7FA8` |

---

### WaveRider — Manifold-Aware Geometric ML

> Flat vector logo. The central element is a **curved triangulated manifold surface** rendered in three-quarter perspective — a section of a smooth 2D surface embedded in 3D space, drawn as a clean triangular wireframe mesh in cool steel-blue (#5B7FA8) with the visible faces filled in a slightly lighter translucent tone (#A8C0D8). The mesh is dense enough to read as a curved surface (roughly 8×6 quads) and gently saddle-shaped — neither flat nor extreme — so the curvature is unmistakable. **Across the surface**, a discrete trajectory of 6 glowing coral nodes (#FF6B35) connected by short straight edges traces a path that bends with the surface — this is the ManifoldWalker's tangent-step sequence. At the **latest node** in the trajectory (rightmost), a small **orthonormal frame** is drawn: two short perpendicular arrows lying flat against the tangent plane, in bright coral (#FF6B35), one slightly bolder than the other. **Hovering above the surface** at altitude, a small geometric **observer instrument** — an upward-pointing triangle with a circular "eye" inset at its center, rendered in deep navy (#1E3A5F) with a coral pupil (#FF6B35). Three thin **sensor lines** descend from the observer's base vertices to three specific nodes on the trajectory below, indicating the (N+1)-dim extrinsic vantage. In the **lower-left corner**, three small axis labels — `e₁`, `e₂`, `e₃` — in cool steel-blue (#5B7FA8), suggesting that the visible 3D scene is itself embedded in higher dimensions. Below the manifold scene, "WaveRider" in bold clean Futura sans-serif, coral #FF6B35. Beneath, in smaller lighter weight, the subtitle "Manifold-Aware Geometric ML" in cool steel-blue (#5B7FA8). Fully transparent background (PNG with alpha). No drop shadows. No gradient fills (the translucent face tone is flat). No 3D shading on the mesh — just the clean wireframe and flat-fill faces. No lens flares. No photorealism. The aesthetic is technical, instrument-like, and geometric — every line is exact. Square composition 1024x1024.
