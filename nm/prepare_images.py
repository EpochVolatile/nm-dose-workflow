"""Resample CT and discrete labels onto the reconstruction reference in physical LPS space."""
import argparse
import json
from pathlib import Path
import SimpleITK as sitk


def read_ct(path, series_id):
    if not path.is_dir():return sitk.ReadImage(str(path))
    ids=sitk.ImageSeriesReader.GetGDCMSeriesIDs(str(path))
    if not ids:raise ValueError('No DICOM series found')
    if series_id is None:
        if len(ids)!=1:raise ValueError(f'Select --series-id explicitly from: {ids}')
        series_id=ids[0]
    reader=sitk.ImageSeriesReader()
    reader.SetFileNames(sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(path),series_id))
    return reader.Execute()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ct',type=Path,required=True);p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--labels',type=Path);p.add_argument('--series-id')
    p.add_argument('--reference-to-moving-transform',type=Path)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    ct=read_ct(a.ct,a.series_id);ref=sitk.ReadImage(str(a.reference))
    transform=sitk.ReadTransform(str(a.reference_to_moving_transform)) if a.reference_to_moving_transform else sitk.Transform(3,sitk.sitkIdentity)
    output=sitk.Resample(ct,ref,transform,sitk.sitkLinear,-1000,sitk.sitkFloat32)
    sitk.WriteImage(output,str(a.out/'ct_on_reference.mhd'),True)
    if a.labels:
        labels=sitk.ReadImage(str(a.labels))
        result=sitk.Resample(labels,ref,transform,sitk.sitkNearestNeighbor,0,sitk.sitkUInt16)
        sitk.WriteImage(result,str(a.out/'labels_on_reference.mhd'),True)
    (a.out/'image_geometry.json').write_text(json.dumps({
        'coordinate_system':'LPS mm','size_xyz':ref.GetSize(),'spacing_mm':ref.GetSpacing(),
        'origin_mm':ref.GetOrigin(),'direction':ref.GetDirection(),
        'ct_interpolation':'linear','labels_interpolation':'nearest neighbour',
        'transform':'reference/output points to moving/input points',
        'registration':'supplied transform, or identity; this script does not estimate registration',
        'activity':'Bq/voxel reference grid is not interpolated here'},indent=2))


if __name__=='__main__':main()
