# Release Notes — v0.97.0

> Released: 2026-08-15

DiaryKG gets a 3-D view of a diary, built in two phases so the fragile part stays isolated:
pure geometry first, then a renderer-agnostic scene that opens no window and imports no Qt.
Alongside it, the package stops shipping its own dev tooling in the wheel. Nothing in the
build or query path changed — corpora built under 0.96.0 remain valid and no rebuild is
required.

## What changed

**A diary now has a shape.** `loader.py` reads a `.diarykg` graph into the shared layout
vocabulary from `kgmodule-utils`, and two layouts interpret it differently on purpose. The
tree layout keeps gutenberg_kg's grammar with time standing in for chapters — trunk, one
limb per calendar year, entry clusters, chunk leaves — with limbs ascending in period order
so the tree reads bottom-to-top the way a life does. The temporal layout is the analytical
counterpart the tree cannot be: Z scales by *date* rather than by index, so a year Pepys
wrote little shows up as an actual gap rather than being compressed away. Neither module
imports PyVista, which is what makes the whole layer testable on a headless machine.

**One scene, two consumers.** `scene.py` builds actors into a `pv.Plotter` the caller
creates and owns — no window, no event loop, no Qt. That split is the point: the same
composition serves an interactive viewer and a headless quilt renderer, so the eventual
`diarykg quilt` costs almost nothing instead of being a second implementation. Tree mode
sweeps the organic skeleton into wood with leaf glyphs; manifold mode draws points and can
show `SIMILAR_TO` edges, because a 1667 entry echoing 1665 is a long diagonal the tree
cannot express by construction. Edges of one relation collapse into a single line-set actor,
so a diary with thousands of entries doesn't stall the renderer with thousands of them.

**Headless testing that survives a missing GPU.** Without a display, this VTK build does not
raise — it aborts the interpreter, and a fatal abort takes unrelated tests down with it.
`DISPLAY` only *correlates* with the ability to render: an xvfb server without GLX or a
container forwarding X with no GL driver both set it and abort anyway. The suite now probes
the capability directly with a minimal off-screen render in a child process, so a crash
costs one subprocess rather than the session. `xvfb-run -a pytest` behaves exactly as before.

**The wheel is verified, not assumed.** A new CI job builds the wheel, installs it into a
clean virtualenv with no source tree in sight, and loads every console-script entry point.
The existing lint, type-check and test jobs all run against `src/` via `pythonpath`, which
makes them structurally incapable of noticing when the artifact itself is broken.

**Dev tooling left the wheel.** It moved from a `dev` extra to an optional Poetry group, so
it can no longer be pip-installed and no longer appears in the published metadata. The `all`
aggregate extra retired with it — it re-listed every dev tool by name, which kept them
advertised in the wheel no matter where the dependencies actually lived.

## Upgrading

`pip install --upgrade diary-kg`. No rebuild, no migration, no API change.

Two install commands changed. `pip install -e ".[dev]"` and `pip install -e ".[all]"` no
longer exist — use `poetry install --with dev` for tooling, and ask for the feature extras
you want by name (`viz`, `viz3d`). Anything scripted against the old extras needs updating.

The 3-D layouts require `kgmodule-utils >= 0.13.2` (the floor now enforces it) and the
`viz3d` extra for rendering: `pip install "diary-kg[viz3d]"`. On a headless machine, run the
visualization tests under `xvfb-run -a`; without one they skip cleanly rather than crashing.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
