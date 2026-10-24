"""Generate a local, asymmetric water phantom; all image coordinates are LPS mm."""
import argparse
import json
from pathlib import Path

import numpy as np
import SimpleITK as sitk


def write_image(array, path, reference=None, spacing=(4., 4., 4.)):
    image = sitk.GetImageFromArray(np.asarray(array))  # NumPy z,y,x
    if reference is None:
        image.SetSpacing(spacing)
        image.SetOrigin(tuple(-(n - 1) * s / 2 for n, s in zip(image.GetSize(), spacing)))
    else:
        image.CopyInformation(reference)
    sitk.WriteImage(image, str(path), True)
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    z, y, x = np.meshgrid((np.arange(8)-3.5)*4, (np.arange(32)-15.5)*4,
                          (np.arange(32)-15.5)*4, indexing='ij')
    body = x*x+y*y < 48**2
    lesion = (x-16)**2+(y+12)**2+(z-2)**2 < 12**2
    activity = np.where(body, 1., 0.) + lesion*7.
    activity *= 1e6/activity.sum()  # Bq/voxel at t=0; known only for this calibration phantom
    labels = body.astype(np.uint8)
    labels[lesion] = 2
    write_image(activity.astype(np.float32), args.out/'activity_truth_Bq_voxel.mhd')
    write_image(np.where(body, 0, -1000).astype(np.int16), args.out/'ct_HU.mhd')
    write_image(labels, args.out/'labels.mhd')
    (args.out/'model.json').write_text(json.dumps({
        'shape_xyz': [32, 32, 8], 'spacing_mm': [4, 4, 4],
        'coordinate_system': 'LPS', 'water_radius_mm': 48.,
        'times_h': [0, 4, 12, 24], 'effective_half_life_h': 6.,
        'physical_half_life_h': 159.528, 'isotope': 'Lu-177',
        'activity_t0_Bq': 1e6, 'imaging_energy_keV': 208.,
        'imaging_model': 'forced parallel primary photons, ideal camera; not scanner validation',
        'calibration': 'known total activity in the synthetic calibration phantom',
    }, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
