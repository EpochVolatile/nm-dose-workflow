#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
stack=${NM_STACK_HOME:-$HOME/.local/share/nm-dose-workflow}
mkdir -p "$stack/src" "$stack/logs"
python3.12 -m venv "$stack/venv"
"$stack/venv/bin/python" -m pip install --upgrade pip
"$stack/venv/bin/python" -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
"$stack/venv/bin/python" -m pip install -r "$repo/requirements.txt"
if [[ ! -d $stack/src/Slicer-5.12.4-linux-amd64 ]]; then
  curl -fL --retry 2 https://download.slicer.org/bitstream/6aa1beb7ce9de556d3010204 -o "$stack/src/Slicer.tar.gz"
  tar -xzf "$stack/src/Slicer.tar.gz" -C "$stack/src"
fi
if [[ ! -d $stack/src/OpenDose3D/.git ]]; then
  git clone --depth 1 --branch develop https://gitlab.com/opendose/opendose3d.git "$stack/src/OpenDose3D"
fi
"$stack/src/Slicer-5.12.4-linux-amd64/Slicer" --launch PythonSlicer -m pip install -r "$repo/requirements-slicer.txt"
# First import downloads Geant4 data associated with the GATE wheel, then exits.
bash "$repo/scripts/python.sh" -c 'import opengate'
bash "$repo/scripts/python.sh" -c 'from importlib.metadata import version; print({p:version(p) for p in ["opengate","opengate-core","torch","pytomography","SimpleITK"]})'
printf 'Stack installed: %s\nRun: bash scripts/run.sh\n' "$stack"
