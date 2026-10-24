"""Full Lu-177 ion decay in GATE 10 using reconstructed activity as voxel source."""
import argparse
import json
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import opengate as gate
from phantom import write_image


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--events', type=int, default=100000)
    a = p.parse_args()
    out = a.run/'gate-dose'
    out.mkdir(exist_ok=True)
    sim = gate.Simulation()
    sim.output_dir = out
    sim.random_seed = 97531
    sim.number_of_threads = 1
    sim.progress_bar = False
    sim.world.size = [400, 400, 400]
    sim.world.material = 'G4_AIR'
    water = sim.add_volume('Tubs', 'water')
    water.rmin, water.rmax, water.dz = 0, 48, 16
    water.sphi, water.dphi = 0, 360*gate.g4_units.deg
    water.material = 'G4_WATER'
    sim.physics_manager.physics_list_name = 'G4EmLivermorePhysics'
    sim.physics_manager.enable_decay = True
    sim.physics_manager.set_production_cut('world', 'all', 0.1)
    source = sim.add_source('VoxelSource', 'reconstructed_activity')
    source.image = str(a.run/'activity_recon_Bq_voxel.mhd')
    source.particle = 'ion 71 177'
    source.energy.type, source.energy.mono = 'mono', 0
    source.n = a.events
    source.direction.type = 'iso'
    source.user_particle_life_time = 0
    dose = sim.add_actor('DoseActor', 'dose')
    dose.attached_to = water.name
    dose.size, dose.spacing = [32, 32, 8], [4, 4, 4]
    dose.dose.active = True
    dose.dose_uncertainty.active = True
    dose.dose.output_filename = 'dose_sum_Gy.mhd'
    dose.dose_uncertainty.output_filename = 'dose_relative_uncertainty.mhd'
    dose.edep.output_filename = 'edep_sum_MeV.mhd'
    stats = sim.add_actor('SimulationStatisticsActor', 'statistics')
    stats.output_filename = 'statistics.txt'
    sim.run()
    image = sitk.ReadImage(str(out/'dose_sum_Gy.mhd'))
    total_dose = sitk.GetArrayFromImage(image)
    ref = sitk.ReadImage(str(a.run/'activity_recon_Bq_voxel.mhd'))
    if not np.allclose(ref.GetOrigin(), image.GetOrigin(), atol=1e-5):
        raise ValueError(f'Unexpected dose image origin: {image.GetOrigin()} vs {ref.GetOrigin()}')
    total_bq = float(sitk.GetArrayFromImage(ref).sum())
    # Gy per emitted parent Lu-177 ion x decays/s = Gy/s.
    dose_rate = total_dose/a.events*total_bq
    model = json.loads((a.run/'phantom/model.json').read_text())
    for t in model['times_h']:
        write_image((dose_rate*2**(-t/model['effective_half_life_h'])).astype(np.float32),
                    a.run/f'dose_rate_t{t:03}_Gy_s.mhd', ref)
    (out/'normalization.json').write_text(json.dumps({
        'parent_decays': a.events, 'activity_Bq': total_bq,
        'formula': 'dose_sum_Gy / parent_decays * activity_Bq = dose_rate_Gy_per_s',
        'source': 'Lu-177 ion, forced zero parent lifetime; Geant4 radioactive decay',
        'production_cut_mm': 0.1,
        'uncertainty': 'GATE relative MC uncertainty, no calibration or kinetic uncertainty included',
    }, indent=2))


if __name__ == '__main__':
    main()
