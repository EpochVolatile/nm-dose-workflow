"""GATE phase space -> projections -> CPU PyTomography OSEM -> Bq/voxel images."""
import argparse
import json
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import torch
import uproot
import pytomography
from pytomography.metadata.SPECT import SPECTObjectMeta, SPECTProjMeta
from pytomography.projectors.SPECT import SPECTSystemMatrix
from pytomography.likelihoods import PoissonLogLikelihood
from pytomography.algorithms import OSEM
from pytomography.transforms.SPECT import SPECTAttenuationTransform
from phantom import write_image


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--views', type=int, default=24)
    p.add_argument('--iters', type=int, default=8)
    a = p.parse_args()
    torch.set_num_threads(1)
    pytomography.set_device('cpu')
    angles = np.arange(a.views)*360/a.views
    projections = []
    counts = []
    for view in range(a.views):
        with uproot.open(a.run/f'acquisition/view-{view:03}/hits.root') as root:
            tree = root['camera_hits']
            hits = tree.arrays(library='np')
            # Reject scattered and off-axis photons. Same emitted photon count at every view.
            keep = ((hits['KineticEnergy'] > 0.20799) &
                    (hits['ParentID'] == 0) & (hits['PreDirection_Y'] < -0.999999))
            h, _, _ = np.histogram2d(hits['PrePosition_X'][keep], hits['PrePosition_Z'][keep],
                                     bins=[np.arange(33)*4-64, np.arange(9)*4-16])
            projections.append(h)
            counts.append(int(keep.sum()))
    projections = torch.tensor(np.asarray(projections), dtype=torch.float32)
    np.save(a.run/'projections_counts.npy', projections.numpy())
    reference = sitk.ReadImage(str(a.run/'prepared/ct_on_reference.mhd'))
    ct = sitk.GetArrayFromImage(reference)
    # PyTomography uses cm. This teaching attenuation coefficient is user configuration.
    mu = torch.tensor(np.transpose(np.where(ct == 0, 0.135, 0.), (2, 1, 0)).copy(), dtype=torch.float32)
    object_meta = SPECTObjectMeta(dr=(0.4, 0.4, 0.4), shape=(32, 32, 8))
    proj_meta = SPECTProjMeta(projection_shape=(32, 8), dr=(0.4, 0.4),
                             angles=angles, radii=np.ones(a.views)*10)
    attenuation = SPECTAttenuationTransform(attenuation_map=mu)
    matrix = SPECTSystemMatrix(obj2obj_transforms=[attenuation], proj2proj_transforms=[],
                              object_meta=object_meta, proj_meta=proj_meta)
    recon = OSEM(PoissonLogLikelihood(matrix, projections))(n_iters=a.iters, n_subsets=4)
    array = np.transpose(recon.cpu().numpy(), (2, 1, 0))
    # Explicit phantom-based calibration, never a patient calibration inferred from counts.
    array = np.where(ct == 0, array, 0.)
    scale = 1e6/array.sum()
    array = array*scale
    image = write_image(array.astype(np.float32), a.run/'activity_recon_Bq_voxel.mhd', reference)
    model = json.loads((a.run/'phantom/model.json').read_text())
    for t in model['times_h']:
        write_image((array*2**(-t/model['effective_half_life_h'])).astype(np.float32),
                    a.run/f'activity_t{t:03}_Bq_voxel.mhd', image)
    (a.run/'reconstruction.json').write_text(json.dumps({
        'angles_degrees': angles.tolist(), 'accepted_counts_per_view': counts,
        'iterations': a.iters, 'subsets': 4, 'device': 'cpu',
        'counts_to_Bq_voxel_factor': float(scale),
        'calibration_source': 'known 1 MBq synthetic calibration phantom',
        'attenuation_cm_inverse': 0.135,
        'psf_and_scatter_correction': 'ideal camera, energy/direction rejection, no hardware PSF',
        'timeseries': 'synthetic common spatial distribution, effective half-life 6 h',
    }, indent=2))


if __name__ == '__main__':
    main()
