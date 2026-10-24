#!/usr/bin/env bash
set -euo pipefail
stack=${NM_STACK_HOME:-$HOME/.local/share/nm-dose-workflow}
# Wheel libraries and the system Geant4 libraries must not share a loader path.
unset LD_LIBRARY_PATH PYTHONPATH
export OMP_NUM_THREADS=${NM_THREADS:-1}
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=${NM_THREADS:-1}
exec "$stack/venv/bin/python" "$@"
