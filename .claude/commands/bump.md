# Version Bump Workflow

You will update the project version in `pyproject.toml` and `__init__.py` files, then stage the changes.

## Step 1: Determine Current Version

1. Check if `pyproject.toml` exists in the project root
2. Find the `version = "X.Y.Z"` line
3. Extract the current version

## Step 2: Ask for Bump Type

Ask the user which version component to bump:
- **major**: X.0.0 (breaking changes)
- **minor**: x.Y.0 (new features, backward compatible)
- **patch**: x.y.Z (bug fixes)

Calculate the new version based on their response.

## Step 3: Update pyproject.toml

1. Read `pyproject.toml`
2. Find the line: `version = "X.Y.Z"`
3. Replace with new version: `version = "A.B.C"`
4. Save the file

## Step 4: Update __init__.py

1. Find the main package's `__init__.py` file (usually `src/<package>/__init__.py`)
2. Look for `__version__ = "X.Y.Z"`
3. Replace with new version: `__version__ = "A.B.C"`
4. Save the file

## Step 5: Update poetry.lock

Run:
```bash
poetry lock --no-update
```

This updates `poetry.lock` with the new version constraint.

## Step 6: Stage Changes

Run:
```bash
git add pyproject.toml poetry.lock src/*//__init__.py
git status
```

Verify all files are staged: `pyproject.toml`, `poetry.lock`, and `src/[package]/__init__.py`.

## Step 7: Confirm

Display:
```
✓ Updated version to A.B.C
✓ Modified: pyproject.toml
✓ Modified: poetry.lock
✓ Modified: src/[package]/__init__.py
✓ Staged changes

Ready to commit with: git commit -m "chore(release): bump version to A.B.C"
```
