import argparse
import json
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    read=lambda name:sitk.GetArrayFromImage(sitk.ReadImage(str(a.run/name)))
    truth=read('phantom/activity_truth_Bq_voxel.mhd')
    recon=read('activity_recon_Bq_voxel.mhd')
    dose=read('dose_integrated_Gy.mhd')
    metadata=json.loads((a.run/'opendose3d.json').read_text())
    with plt.rc_context({'font.size':10,'figure.facecolor':'white','svg.fonttype':'none'}):
        fig,axes=plt.subplots(2,2,figsize=(10,8),layout='constrained')
        maximum=max(truth[4].max(),recon[4].max())
        for ax,data,title in zip(axes[0],[truth,recon],['Known calibration phantom','GATE photons + PyTomography OSEM']):
            im=ax.imshow(data[4],origin='lower',extent=(-64,64,-64,64),vmin=0,vmax=maximum,cmap='cividis',interpolation='nearest')
            ax.set(xlabel='LPS x (mm)',ylabel='LPS y (mm)',title=title)
            fig.colorbar(im,ax=ax,label='Activity (Bq/voxel)')
        im=axes[1,0].imshow(dose[4],origin='lower',extent=(-64,64,-64,64),cmap='magma',vmin=0,interpolation='nearest')
        axes[1,0].set(xlabel='LPS x (mm)',ylabel='LPS y (mm)',title='OpenDose3D: integrated 0 to infinity')
        fig.colorbar(im,ax=axes[1,0],label='Absorbed dose (Gy)')
        model=json.loads((a.run/'phantom/model.json').read_text())
        times=np.asarray(model['times_h']); t=np.linspace(0,24,200)
        axes[1,1].plot(t,2**(-t/6),color='#0072B2',label='Prescribed 6 h exponential')
        axes[1,1].plot(times,2**(-times/6),'o',color='#D55E00',label='Synthetic time points')
        axes[1,1].set(xlabel='Time after reference (h)',ylabel='Dose rate / reference dose rate',ylim=(0,1.05),title='Synthetic kinetics, common spatial map')
        axes[1,1].legend()
        fig.suptitle('Local workflow demonstration; ideal camera; not a scanner calibration',fontsize=12)
        fig.savefig(a.run/'overview.png',dpi=180)
        fig.savefig(a.run/'overview.svg')
        plt.close(fig)
    # Truth is available only in this synthetic exercise: measure axes and reconstruction fidelity.
    labels=read('phantom/labels.mhd')
    grid=np.indices(truth.shape)
    centroids={name:[float((index*data).sum()/data.sum()) for index in grid]
               for name,data in [('truth',truth),('reconstruction',recon)]}
    error=float(np.linalg.norm(recon-truth)/np.linalg.norm(truth))
    metrics={'relative_L2_error':error,'centroid_zyx_voxels':centroids,
             'truth_lesion_mean_Bq_voxel':float(truth[labels==2].mean()),
             'reconstructed_lesion_mean_Bq_voxel':float(recon[labels==2].mean()),
             'note':'No agreement threshold; finite angular sampling, noise, interpolation and approximate attenuation remain'}
    (a.run/'image_metrics.json').write_text(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
