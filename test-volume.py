from pydicom import Dataset
import pydicom
from pathlib import Path
import numpy as np

out_dir = Path("/opt/gravis/data/test_volume")
out_dir.mkdir(exist_ok=True)

def tip_axial():
    for n,dcm in enumerate(Path("/opt/gravis/data/cases/2e500281-b99d-479d-af67-3575c7e86104/input").glob("reco.00*.*.dcm")):
        ds = pydicom.dcmread(dcm)
        ds.PatientName = "FAKE^SIDEWAYS^AXIAL"
        ds.PatientID = "000000"
        ds.PatientBirthDate = "19000101"
        print(ds.ImageOrientationPatient)
        ds.ImageOrientationPatient = [ *ds.ImageOrientationPatient[3:], *ds.ImageOrientationPatient[:3] ]
        print(ds.ImageOrientationPatient)
        ds.PixelData = ds.pixel_array.T.tobytes()
        ds.save_as( out_dir / dcm.name)

def coronal():
    new_study_uid = pydicom.uid.generate_uid()

    for series in [f"{k:03}" for k in range(6)]:
        example_dcm = None
        volume = []
        files = sorted(list(Path("/opt/gravis/data/cases/e37501cf-dcf6-4d5b-9c76-5ce99d606267/input").glob(f"reco.{series}.*.dcm")))
        new_series_uid = pydicom.uid.generate_uid()
        for n,dcm in enumerate(files):
            ds = pydicom.dcmread(dcm)
            if not example_dcm:
                example_dcm = ds
            volume.append(ds.pixel_array[:])

        volume = np.asarray(volume)
        volume = volume.transpose(2,0,1)
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "FAKE^CORONAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[1]
            ds.Rows = volume.shape[2]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 
            ds.ImageOrientationPatient = [1,0,0,0,0,-1]
            ds.ImagePositionPatient = [0, i, 0]
            ds.PixelData = volume[i,:,:].T.tobytes()
            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as( out_dir / f"reco.{series}.{i:03}.dcm")
coronal()