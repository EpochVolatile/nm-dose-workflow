#!/usr/bin/env bash
set -euo pipefail
stack=${NM_STACK_HOME:-$HOME/.local/share/nm-dose-workflow}
unset LD_LIBRARY_PATH PYTHONPATH
export QTWEBENGINE_DISABLE_SANDBOX=1
exec "$stack/src/Slicer-5.12.4-linux-amd64/Slicer" \
  --additional-module-paths "$stack/src/OpenDose3D/OpenDose3D" "$@"
