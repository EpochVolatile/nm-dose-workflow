"""Run with Slicer, not the external venv. Use OpenDose3D's actual fit backend."""
import csv
import json
import os
from pathlib import Path

import numpy as np
import SimpleITK as sitk
import slicer
from Logic.fitutils import MonoExponential
from Logic.OpenDose3DLogic import OpenDose3DLogic


def main():
    run=Path(os.environ['NM_RUN_DIR'])
    model=json.loads((run/'phantom/model.json').read_text())
    times=np.array(model['times_h'],dtype=float)*3600
    reference=sitk.ReadImage(str(run/'dose_rate_t000_Gy_s.mhd'))
    rates=np.array([sitk.GetArrayFromImage(sitk.ReadImage(str(run/f'dose_rate_t{int(t):03}_Gy_s.mhd')))
                    for t in model['times_h']])
    labels=sitk.GetArrayFromImage(sitk.ReadImage(str(run/'prepared/labels_on_reference.mhd')))
    physical_lambda=np.log(2)/(model['physical_half_life_h']*3600)
    # All time points in this tutorial share the spatial map; fit its common kinetics once.
    kinetics=2**(-times/(model['effective_half_life_h']*3600))
    fitting=MonoExponential(times,kinetics,physical_lambda)
    fitting.minimize()
    integration_seconds=float(fitting.AUC())
    dose=rates[0]*integration_seconds
    image=sitk.GetImageFromArray(dose.astype(np.float32)); image.CopyInformation(reference)
    sitk.WriteImage(image,str(run/'dose_integrated_Gy.mhd'),True)
    results=[]
    for label,name in [(1,'Water_background'),(2,'Hot_lesion')]:
        values=np.array([x[labels==label].mean() for x in rates])
        fit=MonoExponential(times,values,physical_lambda);fit.minimize()
        results.append({'region':name,'voxels':int((labels==label).sum()),
                        'dose_Gy':float(fit.AUC()),
                        'effective_half_life_h':float(fit.getParameters()[1]/3600)})
    with (run/'opendose3d_regions.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    # Instantiate the installed Slicer logic as an additional extension import check.
    logic=OpenDose3DLogic(isotopeText='Lu-177')
    ct=slicer.util.loadVolume(str(run/'prepared/ct_on_reference.mhd'),{'name':'CT_HU'})
    activity=slicer.util.loadVolume(str(run/'activity_recon_Bq_voxel.mhd'),{'name':'Activity_Bq_per_voxel'})
    activity.SetAttribute('Workflow.Units','Bq/voxel')
    dose_node=slicer.util.loadVolume(str(run/'dose_integrated_Gy.mhd'),{'name':'OpenDose3D_IntegratedDose_Gy'})
    dose_node.SetAttribute('DicomRtImport.DoseVolume','1')
    dose_node.SetAttribute('Workflow.Units','Gy')
    label_node=slicer.util.loadLabelVolume(str(run/'prepared/labels_on_reference.mhd'))
    segmentation=slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode','Phantom_regions')
    segmentation.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node,segmentation)
    slicer.mrmlScene.RemoveNode(label_node)
    slicer.util.setSliceViewerLayers(background=ct,foreground=dose_node,foregroundOpacity=0.5)
    if slicer.app.layoutManager() is not None:
        slicer.util.resetSliceViews()
    slicer.util.saveScene(str(run/'dosimetry.mrb'))
    summary={'engine':'OpenDose3D Logic.fitutils.MonoExponential, executed inside 3D Slicer',
             'slicer_version':slicer.app.applicationVersion,
             'extension_logic_class':logic.__class__.__name__,
             'time_unit':'s','dose_rate_unit':'Gy/s','dose_unit':'Gy',
             'integration_range':'0 to infinity, fitted mono-exponential',
             'integration_seconds':integration_seconds,
             'analytic_seconds':model['effective_half_life_h']*3600/np.log(2),
             'regions':results,
             'limitations':'common spatial distribution and prescribed synthetic kinetics; no independent time point measurements; MC/calibration/registration uncertainty not propagated'}
    (run/'opendose3d.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
