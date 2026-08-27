#!/usr/bin/env bash
# =============================================================================
# install-skill.sh — Bootstrap the DiaryKG AI integration layer
#
# Installs SKILL.md reference files and Claude Code slash commands for AI
# agents, then configures MCP server integration for the specified providers.
#
# Supported providers:
#   claude   — Claude Code  (.mcp.json)
#   kilo     — Kilo Code    (.mcp.json, shared with Claude Code)
#   copilot  — GitHub Copilot (.vscode/mcp.json)
#   cline    — Cline        (cline_mcp_settings.json)
#
# Usage (from a target repo, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/diary_kg/main/scripts/install-skill.sh | bash
#
# With provider selection:
#   curl -fsSL .../install-skill.sh | bash -s -- --providers all
#   curl -fsSL .../install-skill.sh | bash -s -- --providers claude,copilot
#   bash scripts/install-skill.sh --providers kilo,cline
#
# Flags:
#   --providers <list>   Comma-separated provider names, or "all" (default: all)
#   --dry-run            Print what would be done without making any changes
#
# What it does:
#   1. Creates skill directories for Claude Code, Kilo Code, and other agents
#      and installs SKILL.md + references/installation.md into each
#   2. Installs Claude Code slash commands (setup-diarykg-mcp, continue,
#      protocol) to ~/.claude/commands/
#   3. Installs diary-kg if diarykg is not found:
#        a. pip install from latest GitHub release wheel (preferred, no git needed)
#        b. pip install from git+https (fallback, needs git)
#        c. poetry add (fallback for Poetry-managed repos)
#   4. Reports whether the DiaryKG for this repo has been built yet. Building
#      requires a diary text source (`diarykg build ROOT --source <file>`),
#      which this installer has no way to discover automatically — it is
#      never run for you.
#   5. Writes provider MCP configs as requested
#   6. Prints a final summary
#
# Author: Eric G. Suchanek, PhD
# =============================================================================

set -eo pipefail

# ── Parse arguments ───────────────────────────────────────────────────────────
PROVIDERS_ARG="all"
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --providers)
            PROVIDERS_ARG="${2:-all}"
            shift 2
            ;;
        --providers=*)
            PROVIDERS_ARG="${1#*=}"
            shift
            ;;
        --dry-run)
            DRY_RUN="1"
            shift
            ;;
        *)
            echo "Unknown flag: $1"
            echo "Usage: $0 [--providers all|claude,kilo,copilot,cline] [--dry-run]"
            exit 1
            ;;
    esac
done

# Run a command, or in dry-run mode just print what would be executed.
_exec() {
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# Normalise to a set of boolean flags
DO_CLAUDE=0; DO_KILO=0; DO_COPILOT=0; DO_CLINE=0

_enable_provider() {
    case "$1" in
        all)    DO_CLAUDE=1; DO_KILO=1; DO_COPILOT=1; DO_CLINE=1 ;;
        claude) DO_CLAUDE=1 ;;
        kilo)   DO_KILO=1 ;;
        copilot)DO_COPILOT=1 ;;
        cline)  DO_CLINE=1 ;;
        *)
            echo "Unknown provider: $1  (valid: all, claude, kilo, copilot, cline)"
            exit 1
            ;;
    esac
}

IFS=',' read -ra _PLIST <<< "$PROVIDERS_ARG"
for _p in "${_PLIST[@]}"; do
    _enable_provider "$(echo "$_p" | tr -d ' ')"
done

REPO="Flux-Frontiers/diary_kg"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

# Install to Claude Code, Kilo Code, and other agent skill directories
SKILL_DIRS=(
    "${HOME}/.claude/skills/diarykg"
    "${HOME}/.kilocode/skills/diarykg"
    "${HOME}/.agents/skills/diarykg"
)

# Global Claude Code command files to install to ~/.claude/commands/.
# changelog-commit.md and release.md are fleet-wide and live in
# ~/.claude/commands already — shipping repo copies would overwrite the
# global ones with a stale, diary_kg-specific fork.
CLAUDE_COMMAND_FILES=(
    "setup-diarykg-mcp.md"
    "continue.md"
    "protocol.md"
)

# ── Detect if we're running from inside the repo ─────────────────────────────
# BASH_SOURCE[0] is unbound when piped via curl | bash.
# Use ${BASH_SOURCE:-} (no array index) which is safe even when unset.
_BASH_SOURCE="${BASH_SOURCE:-}"
if [ -n "$_BASH_SOURCE" ] && [ "$_BASH_SOURCE" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$_BASH_SOURCE")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Running via curl | bash — no local clone available
    SCRIPT_DIR=""
    REPO_ROOT=""
fi
LOCAL_SKILL="${REPO_ROOT:+${REPO_ROOT}/.claude/skills/diarykg/SKILL.md}"

# The target repo is where the user ran the script from (CWD).
TARGET_REPO="${PWD}"
SQLITE_DB="${TARGET_REPO}/.diarykg/graph.sqlite"
VECTORS_PATH="${TARGET_REPO}/.diarykg/vectors.sqlite"

echo "╔══════════════════════════════════════════════════╗"
echo "║       DiaryKG Integration Installer               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
[ -n "$DRY_RUN" ] && echo "  *** DRY RUN — no changes will be made ***"
echo "  Target repo: ${TARGET_REPO}"
_PNAMES=""
[ "$DO_CLAUDE"  = "1" ] && _PNAMES="${_PNAMES} claude"
[ "$DO_KILO"    = "1" ] && _PNAMES="${_PNAMES} kilo"
[ "$DO_COPILOT" = "1" ] && _PNAMES="${_PNAMES} copilot"
[ "$DO_CLINE"   = "1" ] && _PNAMES="${_PNAMES} cline"
echo "  Providers:   ${_PNAMES# }"
echo ""

# ── Step 1: Install skill files to agent directories ─────────────────────────
echo "── Step 1: Installing skill files ──────────────────"
echo ""

# diary_kg does not ship a .claude/skills/diarykg/SKILL.md of its own (neither
# locally nor on GitHub) — only vendored copies of other repos' skills. There
# is nothing to install here yet; skip rather than crash on a download that
# will always 404. See the fleet sweep notes for tracking this gap.
if [ -f "$LOCAL_SKILL" ] || curl -fsSL -o /dev/null "${RAW_BASE}/.claude/skills/diarykg/SKILL.md" 2>/dev/null; then
    for SKILL_DIR in "${SKILL_DIRS[@]}"; do
        _exec mkdir -p "$SKILL_DIR"
        if [ -f "$LOCAL_SKILL" ]; then
            _exec cp "$LOCAL_SKILL" "${SKILL_DIR}/SKILL.md"
        elif [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/diarykg/SKILL.md → ${SKILL_DIR}/SKILL.md"
        else
            curl -fsSL "${RAW_BASE}/.claude/skills/diarykg/SKILL.md" -o "${SKILL_DIR}/SKILL.md"
        fi
        echo "  ✓ ${SKILL_DIR}/SKILL.md"
    done
else
    echo "  ⚠ No diarykg SKILL.md found (local or GitHub) — skipping."
    echo "    diary_kg has not published one yet; agents will not have"
    echo "    dedicated diarykg usage guidance until it does."
fi

# ── Step 2: Install Claude Code commands to ~/.claude/commands/ ───────────────
echo ""
echo "── Step 2: Installing Claude Code commands ──────────"
echo ""

CLAUDE_CMD_DIR="${HOME}/.claude/commands"
_exec mkdir -p "$CLAUDE_CMD_DIR"

for _CMD_FILE in "${CLAUDE_COMMAND_FILES[@]}"; do
    _DST="${CLAUDE_CMD_DIR}/${_CMD_FILE}"
    _LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/${_CMD_FILE}}"

    if [ -n "$_LOCAL_CMD" ] && [ -f "$_LOCAL_CMD" ]; then
        _exec cp "$_LOCAL_CMD" "$_DST"
        echo "  ✓ Copied from local repo → ${_DST}"
    else
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/${_CMD_FILE} → ${_DST}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -o "$_DST"
            echo "  ✓ Downloaded → ${_DST}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -O "$_DST"
            echo "  ✓ Downloaded → ${_DST}"
        else
            echo "  ⚠ Neither curl nor wget found — skipping ${_CMD_FILE}"
        fi
    fi
done

echo ""
echo "── Cline ─────────────────────────────────────────────"
echo ""
if [ "$DO_CLINE" = "1" ]; then
    echo "  – No per-repo slash command to install (diarykg.md was never shipped);"
    echo "    Cline MCP registration is configured below."
else
    echo "  – Skipped (cline not selected)"
fi

# ── Step 3: Install diary-kg if not already present ───────────────────────────
echo ""
echo "── Step 3: Checking diary-kg installation ────────────"
echo ""

# Resolve the latest GitHub release wheel URL (requires curl or wget + python3).
# Returns empty string if no release exists yet.
_latest_wheel_url() {
    local _api="https://api.github.com/repos/${REPO}/releases/latest"
    local _json=""
    if command -v curl &>/dev/null; then
        _json="$(curl -fsSL "$_api" 2>/dev/null || true)"
    elif command -v wget &>/dev/null; then
        _json="$(wget -qO- "$_api" 2>/dev/null || true)"
    fi
    [ -z "$_json" ] && return
    python3 - <<PYEOF
import json, sys
try:
    data = json.loads('''$_json''')
    assets = data.get("assets", [])
    whl = next((a["browser_download_url"] for a in assets if a["name"].endswith(".whl")), None)
    if whl:
        print(whl)
except Exception:
    pass
PYEOF
}

DIARYKG_BIN=""
DIARYKG_MCP_BIN=""

# Probe for an existing installation in order of priority:
#   1. Local .venv in the target repo (Poetry project that added diary-kg)
#   2. Local .venv in the diary_kg source repo (running the script from the repo itself)
#   3. Importable in the active Python environment
#   4. On $PATH
if [ -x "${TARGET_REPO}/.venv/bin/diarykg" ]; then
    DIARYKG_BIN="${TARGET_REPO}/.venv/bin/diarykg"
    DIARYKG_MCP_BIN="${TARGET_REPO}/.venv/bin/diarykg-mcp"
    echo "  ✓ Found diarykg in local venv: ${DIARYKG_BIN}"
elif [ -n "${REPO_ROOT}" ] && [ -x "${REPO_ROOT}/.venv/bin/diarykg" ]; then
    DIARYKG_BIN="${REPO_ROOT}/.venv/bin/diarykg"
    DIARYKG_MCP_BIN="${REPO_ROOT}/.venv/bin/diarykg-mcp"
    echo "  ✓ Found diarykg in source venv: ${DIARYKG_BIN}"
elif python3 -c "import diary_kg" &>/dev/null 2>&1; then
    # Importable — resolve the binaries from the same interpreter's Scripts/bin
    _SCRIPTS_DIR="$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts'))")"
    DIARYKG_BIN="${_SCRIPTS_DIR}/diarykg"
    DIARYKG_MCP_BIN="${_SCRIPTS_DIR}/diarykg-mcp"
    [ -x "$DIARYKG_BIN" ] || DIARYKG_BIN="diarykg"   # fallback to PATH entry
    [ -x "$DIARYKG_MCP_BIN" ] || DIARYKG_MCP_BIN="diarykg-mcp"
    echo "  ✓ Found diary_kg in Python environment — diarykg: ${DIARYKG_BIN}"
elif command -v diarykg &>/dev/null; then
    DIARYKG_BIN="$(command -v diarykg)"
    DIARYKG_MCP_BIN="$(command -v diarykg-mcp 2>/dev/null || echo diarykg-mcp)"
    echo "  ✓ Found diarykg on PATH: ${DIARYKG_BIN}"
fi

if [ -z "$DIARYKG_BIN" ]; then
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would install diary-kg from GitHub (wheel or git source)"
        DIARYKG_BIN="diarykg"
        DIARYKG_MCP_BIN="diarykg-mcp"
    else
        # ── Preferred: latest GitHub release wheel (no git needed) ────────────
        WHEEL_URL="$(_latest_wheel_url || true)"
        if [ -n "$WHEEL_URL" ]; then
            echo "  → Installing diary-kg from GitHub release wheel..."
            pip install --quiet "diary-kg @ ${WHEEL_URL}"
        else
            # ── Fallback: pip from git source ─────────────────────────────────
            echo "  → Installing diary-kg from GitHub source..."
            pip install --quiet "diary-kg @ git+https://github.com/${REPO}.git"
        fi
        # Re-probe after install
        DIARYKG_BIN="$(command -v diarykg 2>/dev/null || true)"
        DIARYKG_MCP_BIN="$(command -v diarykg-mcp 2>/dev/null || true)"
        if [ -n "$DIARYKG_BIN" ]; then
            echo "  ✓ Installed diary-kg — diarykg at: ${DIARYKG_BIN}"
        else
            echo "  ✗ Installation failed. Install manually:"
            echo "      pip install 'diary-kg @ git+https://github.com/${REPO}.git'"
            exit 1
        fi
    fi
fi

# ── Step 3b: Write Cline MCP settings (cline_mcp_settings.json) ─────────────
# Must run after DIARYKG_MCP_BIN is resolved above.
echo ""
echo "── Step 3b: Configuring Cline MCP settings ──────────"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    # Cline global MCP settings — macOS/Linux paths
    CLINE_SETTINGS=""
    if [ -f "${HOME}/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" ]; then
        CLINE_SETTINGS="${HOME}/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    elif [ -f "${HOME}/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" ]; then
        CLINE_SETTINGS="${HOME}/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    fi

    if [ -z "$CLINE_SETTINGS" ]; then
        echo "  ⚠ cline_mcp_settings.json not found — is Cline installed?"
        echo "    Expected: ~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    elif [ -n "$DRY_RUN" ]; then
        REPO_NAME="$(basename "${TARGET_REPO}")"
        echo "  [dry-run] would upsert diarykg-${REPO_NAME} in ${CLINE_SETTINGS}"
    else
        REPO_NAME="$(basename "${TARGET_REPO}")"
        python3 - "$CLINE_SETTINGS" "$TARGET_REPO" "$REPO_NAME" "$DIARYKG_MCP_BIN" <<'PYEOF'
import json, sys
cline_settings = sys.argv[1]
target_repo    = sys.argv[2]
repo_name      = sys.argv[3]
diarykg_mcp    = sys.argv[4]
server_key     = f"diarykg-{repo_name}"

with open(cline_settings, "r") as f:
    data = json.load(f)
if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"][server_key] = {
    "command": diarykg_mcp,
    "args": ["--repo", target_repo]
}

with open(cline_settings, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  ✓ Upserted {server_key} in {cline_settings}")
PYEOF
    fi
else
    echo "  – Skipped (cline not selected)"
fi

# ── Step 4: Report DiaryKG build status ────────────────────────────────────────
echo ""
echo "── Step 4: DiaryKG build status ─────────────────────"
echo ""

if [ -f "$SQLITE_DB" ] && [ -f "$VECTORS_PATH" ]; then
    echo "  ✓ DiaryKG already built:"
    echo "    ${SQLITE_DB}"
    echo "    ${VECTORS_PATH}"
else
    echo "  – DiaryKG has not been built for this repo yet."
    echo "    Building requires a diary text source and is never run"
    echo "    automatically. Build it yourself:"
    echo "      ${DIARYKG_BIN} build ${TARGET_REPO} --source <path-to-diary.txt>"
fi

# ── Step 5: Write .mcp.json (Claude Code + Kilo Code) ────────────────────────
echo ""
echo "── Step 5: Configuring .mcp.json (Claude Code + Kilo Code) ──"
echo ""

MCP_JSON="${TARGET_REPO}/.mcp.json"

if [ "$DO_KILO" = "0" ] && [ "$DO_CLAUDE" = "0" ]; then
    echo "  – Skipped (neither claude nor kilo selected)"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would upsert diarykg entry in ${MCP_JSON}"
elif [ ! -f "$MCP_JSON" ]; then
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "diarykg": {
      "command": "${DIARYKG_MCP_BIN}",
      "args": [
        "--repo", "${TARGET_REPO}"
      ]
    }
  }
}
EOF
    echo "  ✓ Created ${MCP_JSON}"
    echo "    (add --source <diary.txt> to args if this repo's DiaryKG isn't built yet)"
else
    python3 - "$MCP_JSON" "$TARGET_REPO" "$DIARYKG_MCP_BIN" <<'PYEOF'
import json, sys
mcp_json     = sys.argv[1]
target_repo  = sys.argv[2]
diarykg_mcp  = sys.argv[3]
with open(mcp_json, "r") as f:
    data = json.load(f)
if "mcpServers" not in data:
    data["mcpServers"] = {}
data["mcpServers"]["diarykg"] = {
    "command": diarykg_mcp,
    "args": ["--repo", target_repo]
}
with open(mcp_json, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  ✓ Updated diarykg entry in ${MCP_JSON}"
fi

# ── Step 6: Write .vscode/mcp.json (GitHub Copilot) ──────────────────────────
echo ""
echo "── Step 6: Configuring .vscode/mcp.json (GitHub Copilot) ──"
echo ""

VSCODE_DIR="${TARGET_REPO}/.vscode"
VSCODE_MCP="${VSCODE_DIR}/mcp.json"

if [ "$DO_COPILOT" = "0" ]; then
    echo "  – Skipped (copilot not selected)"
elif [ -n "$DRY_RUN" ]; then
    if [ ! -f "$VSCODE_MCP" ]; then
        echo "  [dry-run] would create ${VSCODE_MCP}"
    else
        echo "  [dry-run] would upsert diarykg entry in existing ${VSCODE_MCP}"
    fi
else
    _exec mkdir -p "$VSCODE_DIR"

    if [ ! -f "$VSCODE_MCP" ]; then
        cat > "$VSCODE_MCP" <<EOF
{
  "servers": {
    "diarykg": {
      "type": "stdio",
      "command": "${DIARYKG_MCP_BIN}",
      "args": [
        "--repo", "${TARGET_REPO}"
      ]
    }
  }
}
EOF
        echo "  ✓ Created ${VSCODE_MCP}"
    else
        python3 - "$VSCODE_MCP" "$TARGET_REPO" "$DIARYKG_MCP_BIN" <<'PYEOF'
import json, sys
vscode_mcp   = sys.argv[1]
target_repo  = sys.argv[2]
diarykg_mcp  = sys.argv[3]
with open(vscode_mcp, "r") as f:
    data = json.load(f)
if "servers" not in data:
    data["servers"] = {}
data["servers"]["diarykg"] = {
    "type": "stdio",
    "command": diarykg_mcp,
    "args": ["--repo", target_repo]
}
with open(vscode_mcp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
        echo "  ✓ Updated diarykg entry in ${VSCODE_MCP}"
    fi
fi  # DO_COPILOT

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
if [ -n "$DRY_RUN" ]; then
echo "╔══════════════════════════════════════════════════╗"
echo "║   DiaryKG dry-run complete — no changes made.    ║"
echo "╚══════════════════════════════════════════════════╝"
else
echo "╔══════════════════════════════════════════════════╗"
echo "║   DiaryKG installed and configured successfully! ║"
echo "╚══════════════════════════════════════════════════╝"
fi
echo ""
echo "  Repo:    ${TARGET_REPO}"
echo "  SQLite:  ${SQLITE_DB}"
echo "  Vectors: ${VECTORS_PATH}"
echo ""
echo "  Claude commands installed:"
for _CMD_FILE in "${CLAUDE_COMMAND_FILES[@]}"; do
    echo "    ✓ ~/.claude/commands/${_CMD_FILE}"
done
echo ""
echo "  Providers configured:"
( [ "$DO_CLAUDE" = "1" ] || [ "$DO_KILO" = "1" ] ) && echo "    ✓ Claude Code + Kilo Code  (.mcp.json)"
[ "$DO_COPILOT" = "1" ] && echo "    ✓ GitHub Copilot (.vscode/mcp.json)"
[ "$DO_CLINE"   = "1" ] && echo "    ✓ Cline          (cline_mcp_settings.json)"
echo ""
echo "  ⚠ One manual step required:"
echo "    Reload VS Code to activate the MCP servers:"
echo "    Cmd+Shift+P → 'Developer: Reload Window'"
echo ""
[ "$DO_COPILOT" = "1" ] && echo "  GitHub Copilot: VS Code will prompt you to Trust the diarykg server on first use."
echo ""
echo "  Full docs: https://github.com/Flux-Frontiers/diary_kg/blob/main/docs/MCP.md"
