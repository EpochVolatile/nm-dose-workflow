"""One real GATE 10 acquisition view. Ideal parallel camera; no detector PSF."""
import argparse
from pathlib import Path

import opengate as gate
from scipy.spatial.transform import Rotation


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phantom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--angle', type=float, required=True)
    p.add_argument('--events', type=int, default=20000)
    p.add_argument('--seed', type=int, default=24680)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sim = gate.Simulation()
    sim.output_dir = a.out
    sim.random_seed = a.seed
    sim.number_of_threads = 1
    sim.progress_bar = False
    sim.world.size = [400, 400, 400]
    sim.world.material = 'G4_AIR'
    water = sim.add_volume('Tubs', 'water')
    water.rmin, water.rmax, water.dz = 0, 48, 16
    water.sphi, water.dphi = 0, 360*gate.g4_units.deg
    water.material = 'G4_WATER'
    # VoxelSource uses its attached volume's global rotation; position.rotation is ignored.
    water.rotation = Rotation.from_euler('z', a.angle, degrees=True).as_matrix()
    plane = sim.add_volume('Box', 'camera')
    plane.size = [160, 0.1, 64]
    plane.translation = [0, -100, 0]
    plane.material = 'G4_AIR'
    sim.physics_manager.physics_list_name = 'G4EmLivermorePhysics'
    sim.physics_manager.set_production_cut('world', 'all', 0.1)
    source = sim.add_source('VoxelSource', 'activity')
    source.image = str(a.phantom/'activity_truth_Bq_voxel.mhd')
    source.n = a.events
    source.particle = 'gamma'
    source.energy.type, source.energy.mono = 'mono', 208*gate.g4_units.keV
    source.attached_to = water.name
    source.direction_relative_to_attached_volume = False
    source.direction.type = 'momentum'
    source.direction.momentum = [0, -1, 0]
    phsp = sim.add_actor('PhaseSpaceActor', 'camera_hits')
    phsp.attached_to = plane.name
    phsp.attributes = ['PrePosition', 'PreDirection', 'KineticEnergy', 'EventID', 'ParentID']
    phsp.steps_to_store = 'entering'
    phsp.output_filename = 'hits.root'
    sim.run()


if __name__ == '__main__':
    main()
