#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out=${1:-$HOME/sim-data/nm-dose-workflow/$(date +%Y%m%d-%H%M%S-%N)}
views=${NM_VIEWS:-24}
events=${NM_VIEW_EVENTS:-20000}
dose_events=${NM_DOSE_EVENTS:-100000}
if (( views < 4 || views % 4 != 0 )); then
  printf 'NM_VIEWS must be at least 4 and divisible by the 4 OSEM subsets.\n' >&2
  exit 2
fi
mkdir -p "$out/logs"
out=$(cd "$out" && pwd)
bash "$repo/scripts/python.sh" "$repo/nm/phantom.py" --out "$out/phantom"
for ((view=0; view<views; view++)); do
  angle=$(awk -v i="$view" -v n="$views" 'BEGIN{print i*360/n}')
  name=$(printf 'view-%03d' "$view")
  printf 'GATE acquisition %s/%s, angle %s deg\n' "$((view+1))" "$views" "$angle"
  bash "$repo/scripts/python.sh" "$repo/nm/gate_acquire.py" --phantom "$out/phantom" \
    --out "$out/acquisition/$name" --angle "$angle" --events "$events" --seed "$((24680+view))" \
    > "$out/logs/$name.log" 2>&1
done
bash "$repo/scripts/python.sh" "$repo/nm/prepare_images.py" --ct "$out/phantom/ct_HU.mhd" \
  --reference "$out/phantom/activity_truth_Bq_voxel.mhd" --labels "$out/phantom/labels.mhd" --out "$out/prepared"
bash "$repo/scripts/python.sh" "$repo/nm/reconstruct.py" --run "$out" --views "$views" > "$out/logs/reconstruction.log" 2>&1
bash "$repo/scripts/python.sh" "$repo/nm/gate_dose.py" --run "$out" --events "$dose_events" > "$out/logs/gate-dose.log" 2>&1
export NM_RUN_DIR="$out"
xvfb-run -a env QT_QPA_PLATFORM=xcb bash "$repo/scripts/slicer.sh" --no-splash --no-main-window \
  --python-script "$repo/slicer/integrate_and_view.py" > "$out/logs/opendose3d.log" 2>&1
bash "$repo/scripts/python.sh" "$repo/nm/plot_results.py" --run "$out"
printf 'Results: %s\n' "$out"
