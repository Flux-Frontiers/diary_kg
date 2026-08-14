"""Prove off-screen rendering works, without betting the session on it.

An installed pyvista is not enough, and neither is a set ``DISPLAY``. This VTK
build has no OSMesa or EGL fallback, so constructing a ``Plotter`` without a
working GL context does not raise -- it aborts the interpreter. A fatal abort
takes the whole pytest session down, unrelated tests included, and no
``try``/``except`` or ``importorskip`` can intercept it.

``DISPLAY`` is a proxy for the thing we actually care about: whether a render
succeeds. The two come apart whenever a display exists but cannot render --
an ``xvfb`` server without GLX, a stale ``DISPLAY`` pointing at a dead socket,
a container forwarding X without a GL driver. In those cases the proxy says
"go" and the abort happens anyway.

Running the render in a child process removes the guesswork: the parent reads
an exit code, and a crash costs one subprocess instead of the suite.
"""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache

#: Executed in a child process, where a fatal abort is contained.
_PROBE_SOURCE = """
import pyvista as pv

plotter = pv.Plotter(off_screen=True, window_size=(32, 32))
plotter.add_mesh(pv.Sphere())
plotter.screenshot(None, return_img=True)
plotter.close()
"""

_PROBE_TIMEOUT = 120


@lru_cache(maxsize=1)
def can_render() -> bool:
    """Whether a minimal off-screen render completes in this environment.

    The result is cached, so the subprocess is spawned once per session no
    matter how many modules gate on it.

    :return: True if a child process completed the render cleanly.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE_SOURCE],
            capture_output=True,
            timeout=_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        # No interpreter to spawn, or the probe hung past the timeout.
        return False
    # A fatal abort surfaces as a negative return code (-signal.SIGSEGV).
    return proc.returncode == 0
