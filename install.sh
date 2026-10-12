#!/usr/bin/env bash
# Install the Maya-side bridge into the user's Maya scripts directory.
set -euo pipefail

MAYA_VERSION="${1:-2027}"
SCRIPT_DIR="$HOME/Library/Preferences/Autodesk/maya/$MAYA_VERSION/scripts"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$SCRIPT_DIR" ]; then
  echo "Maya scripts dir not found: $SCRIPT_DIR" >&2
  echo "Pass the Maya version as the first argument, e.g. ./install.sh 2026" >&2
  exit 1
fi

cp "$HERE/maya_bridge.py" "$SCRIPT_DIR/maya_bridge.py"

if [ -f "$SCRIPT_DIR/userSetup.py" ]; then
  echo "userSetup.py already exists in $SCRIPT_DIR; not overwriting."
  echo "Add the following lines to auto-start the bridge on launch:"
  echo
  echo "    import maya_bridge"
  echo "    maya_bridge.start()"
else
  cp "$HERE/userSetup.py" "$SCRIPT_DIR/userSetup.py"
fi

echo "Installed maya_bridge.py into $SCRIPT_DIR"
echo "Restart Maya, or run in the Script Editor: import maya_bridge; maya_bridge.start()"
