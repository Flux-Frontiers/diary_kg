"""
Assert the installed SDK actually provides what this repo imports.

Written after ``kgmodule-utils`` 0.12.0 was published without the ``viz3d``
organic engine it was documented as introducing. Two things made that expensive
rather than merely annoying, and this module is aimed at both:

**A version string is not a capability.** ``gutenberg_kg``'s pin checker went
green on 0.12.0 because every declared version agreed with every locked version.
They did. The engine still was not there. Comparing numbers cannot detect a
missing module, so this asserts the symbols instead.

**An editable install hides a broken release.** The promotion was verified
against a source checkout of the SDK, which is why it passed while the published
wheel could not satisfy a single one of the imports. :func:`test_sdk_is_not_an_editable_checkout`
makes that condition visible rather than silently reassuring.

The failure messages name the installed version and the minimum that works, so
the fix is obvious from the test output alone.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

#: Minimum SDK that contains the organic engine. 0.12.0 was published without
#: it and cannot be corrected in place, since PyPI permanently reserves an
#: uploaded filename.
MINIMUM_SDK = "0.12.1"

#: Names imported by :mod:`diary_kg.layout_tree` and
#: :mod:`diary_kg.layout_temporal`. Keep in step with those modules.
REQUIRED_VIZ3D_NAMES: tuple[str, ...] = (
    "Layout3D",
    "LayoutEdge",
    "LayoutNode",
    "crown_spacing",
    "fibonacci_sphere",
    "golden_spiral_2d",
    "grow_tree",
    "seed_from_key",
)


def _installed_version() -> str:
    """
    Version of the installed SDK.

    :return: Version string, or ``"unknown"``.
    """
    return getattr(importlib.import_module("kg_utils"), "__version__", "unknown")


def test_sdk_exposes_every_name_the_layouts_import() -> None:
    """
    The whole contract, in one assertion with an actionable message.

    A missing name here means the resolved SDK predates the engine promotion —
    not that this repo's code is wrong.
    """
    viz3d = importlib.import_module("kg_utils.viz3d")
    missing = [name for name in REQUIRED_VIZ3D_NAMES if not hasattr(viz3d, name)]

    assert not missing, (
        f"kgmodule-utils {_installed_version()} does not export "
        f"{', '.join(missing)} from kg_utils.viz3d. The organic engine landed in "
        f"{MINIMUM_SDK}; 0.12.0 was published without it. Raise the floor to "
        f">={MINIMUM_SDK} and relock."
    )


def test_organic_module_exists() -> None:
    """The engine must be a real module, not merely names on the package."""
    try:
        importlib.import_module("kg_utils.viz3d.organic")
    except ModuleNotFoundError:  # pragma: no cover - only on a stale SDK
        pytest.fail(
            f"kgmodule-utils {_installed_version()} has no kg_utils.viz3d.organic. "
            f"Requires >={MINIMUM_SDK}."
        )


def test_sdk_is_not_an_editable_checkout() -> None:
    """
    Warn when the SDK resolves to a source tree rather than an installed wheel.

    This is the condition that let a broken release pass review: an editable
    checkout satisfies imports the published artifact cannot, so the suite goes
    green and the wheel is still unusable. Testing against a checkout is
    legitimate while developing the SDK itself, so this reports rather than
    fails — but it reports, which is the part that was missing.
    """
    kg_utils = importlib.import_module("kg_utils")
    location = Path(kg_utils.__file__ or "").resolve()

    if "site-packages" not in location.parts:
        pytest.skip(
            f"kg_utils resolves to {location}, not an installed wheel. Results here "
            "do not prove the published artifact works — verify against the wheel "
            "before trusting them."
        )

    assert location.is_file()
