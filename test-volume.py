from typing import Any
from pydicom import Dataset
import pydicom
from pathlib import Path
import numpy as np

out_dir = Path("/opt/gravis/data/test_volume")
out_dir.mkdir(exist_ok=True)

rots = [
    np.array([[1,0,0],
              [0,0,-1],
              [0,1,0]]),
    np.array([[0,0,1],
              [0,1,0],
              [-1,0,0]]),
    np.array([[0,-1,0],
              [1,0,0],
              [0,0,1]])
]
def cross(*n) -> Any:
    return np.cross(*n)

def get_orient_mat(im_orientation_pt):
    arr = np.asarray(im_orientation_pt).reshape((2,3))
    return np.rint(np.vstack((arr,[cross(*arr)])))

def argabs(m):
    k = np.abs(m).argmax()
    return k, m[k]

def tip_axial(n):
    subdir = f"axial_{n}"
    print(subdir)
    (out_dir / subdir).mkdir(exist_ok=True)

    for dcm in Path("/opt/gravis/data/cases/2e500281-b99d-479d-af67-3575c7e86104/input").glob("reco.000.*.dcm"):
        ds = pydicom.dcmread(dcm)
        ds.PatientName = f"FAKE^SIDEWAYS^AXIAL^{n}"
        ds.PatientID = "000000"
        ds.PatientBirthDate = "19000101"
        mat = get_orient_mat(ds.ImageOrientationPatient)
        rot_by = np.linalg.matrix_power(rots[2], n)
        rot_by = np.linalg.inv(rot_by)
        rotated = (mat @ rot_by)
        ds.ImageOrientationPatient = rotated[0:2].ravel().tolist()
        print(ds.ImageOrientationPatient)
        print("---")

        ds.PixelData = np.rot90(ds.pixel_array, k=n).tobytes()
        ds.save_as( out_dir / subdir / dcm.name)

def fake_coronal():
    subdir = "fake_coronal_from_sag"
    (out_dir / subdir).mkdir(exist_ok=True)

    new_study_uid = pydicom.uid.generate_uid()

    for series in [f"{k:03}" for k in range(1)]:
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
        # volume = volume.transpose(2,0,1)
        volume = np.rot90(volume,axes=(2,0))
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "FAKE^CORONAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[2]
            ds.Rows = volume.shape[1]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 

            mat = get_orient_mat(ds.ImageOrientationPatient)
            rot_by = np.linalg.matrix_power(rots[2], 1)
            rot_by = np.linalg.inv(rot_by)
            rotated = (mat @ rot_by)
            ds.ImageOrientationPatient = rotated[0:2].ravel().tolist()


            ds.ImagePositionPatient = [0, i, 0]
            ds.PixelData = volume[i,:,:].tobytes()
            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as( out_dir / subdir / f"reco.{series}.{i:03}.dcm")

def orig_sagittal():
    subdir = "orig_sagittal"
    (out_dir / subdir).mkdir(exist_ok=True)

    new_study_uid = pydicom.uid.generate_uid()

    for series in [f"{k:03}" for k in range(1)]:
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
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "REAL^SAGITTAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[2]
            ds.Rows = volume.shape[1]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 

            ds.ImageOrientationPatient = get_orient_mat(ds.ImageOrientationPatient)[0:2].ravel().tolist()
            ds.ImagePositionPatient = [i, 0, 0]
            ds.PixelData = volume[i,:,:].tobytes()
            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as( out_dir / subdir / f"reco.{series}.{i:03}.dcm")

def mat_to_rotations(mat):
    rotations = []

    n = 0
    while (mat @ [1, 0, 0]).tolist() != [1, 0, 0] and n < 4:
        mat = mat @ rots[2]
        n += 1

    if n and n < 4:
        rotations += [(n,(2,1))]

    if n == 4:
        n = 0
        while (mat @ [1, 0, 0]).tolist() != [1, 0, 0] and n < 4:
            mat = mat @ rots[1]
            n += 1
        if n > 3:
            raise Exception()
        if n:
            rotations += [(n,(0,2))] # not sure if this is the right direction

    n = 0
    while (mat @ [0, 1, 0]).tolist() != [0, 1, 0]:
        mat = mat @ rots[0]
        n += 1
        if n > 3:
            raise Exception("")
    if n:
        rotations += [(n,(1,0))]
    
    assert np.array_equal(mat,np.identity(3))
    rotations.reverse()
    return rotations
    # print(mat)

def all_orientations():
    o = []
    for i in range(0,3):
        for j in range(0,3):
            if i == j: continue
            for q in (-1,1):
                for r in (-1,1):
                    m = [0]*6
                    m[i] = q
                    m[3+j] = r
                    o.append(m)
    return o

def synthetic_data(orientation):
    arr_size = 3
    arr = np.empty((arr_size,)*3, dtype='<U10')

    for x in range(1,arr_size+1):
        for y in range(1,arr_size+1):
            for z in range(1,arr_size+1):
                r = np.linalg.inv(orientation) @ [x, y, z]
                result = ""
                for k in r:
                    if k < 0:
                        k =  arr_size + k+ 1
                    result += str(int(k))+","
                arr[z-1, y-1, x-1] = result
            # print(result)
    return arr


axial_data = synthetic_data(np.array([[1,0,0],[0,1,0],[0,0,1]]))
print(axial_data)
orientations = all_orientations()
for i,o in enumerate(orientations):
    print(i)
    mat = get_orient_mat(o)
    print(mat)
    # print(np.linalg.inv(mat))
    volume = synthetic_data(mat)
    # print(volume[0])
    # exit()
    rotations = mat_to_rotations(mat)
    print(rotations)
    # volume = np.rot90(volume,k=3, axes=(1,0))
    # volume = np.rot90(volume,k=2, axes=(2,1))

    # print(volume)
    print(volume[0,:,:])
    
    for k,axes in rotations:
        volume = np.rot90(volume,k=k, axes=axes)
    try:
        assert np.array_equal(axial_data,volume)
    finally:
        print(volume[0,:,:])

    # print(o, rotations)


# m = get_orient_mat(orientations[0])

# print(arr[:,:,0])
exit()
rotations = mat_to_rotations(get_orient_mat([0,1,0,0,0,1]))
print(rotations)
exit()

for dc_set in out_dir.iterdir():
    if dc_set.name != 'axial_1': continue
    # if dc_set.name not in ('coronal', 'axial_1','axial_2', 'axial_3'): continue
    print(dc_set.name)
    subdir = dc_set.name + "_transformed"
    (out_dir / subdir).mkdir(exist_ok=True)

    dcm = next(dc_set.iterdir())
    
    example_ds = pydicom.dcmread(dcm)
    mat = get_orient_mat(example_ds.ImageOrientationPatient)
    rotations = mat_to_rotations(mat)
    print(rotations)
    files = sorted(dc_set.glob(f"reco.000.*.dcm"))
    new_series_uid = pydicom.uid.generate_uid()
    volume = []
    for n,dcm in enumerate(files):
        ds = pydicom.dcmread(dcm)
        volume.append(ds.pixel_array[:])
    volume = np.asarray(volume)
    for k,axes in rotations:
        volume = np.rot90(volume,k=k, axes=axes)

    for i in range(volume.shape[0]):
        ds = example_ds.copy()
        ds.PatientName = f"TRANSFORMED^{dc_set.name}"
        ds.PatientID = "000000"
        ds.PatientBirthDate = "19000101"
        ds.Columns = volume.shape[2]
        ds.Rows = volume.shape[1]
        ds.SliceLocation = f"{i}.0"
        ds.InstanceNumber = i 
        ds.ImageOrientationPatient = [1,0,0,0,1,0]
        ds.ImagePositionPatient = [0, 0, -i]
        ds.PixelData = volume[i,:,:].tobytes()
        ds.save_as( out_dir / subdir / f"reco.000.{i:03}.dcm")

# mat_to_rotations(np.array([[ 0.,  1.,  0.],
#  [-0. ,-0., -1.],
#  [-1.,  0.,  0.]]))
exit()
def fake_axial():
    subdir = "fake_axial_from_sag"
    (out_dir / subdir).mkdir(exist_ok=True)

    new_study_uid = pydicom.uid.generate_uid()

    for series in [f"{k:03}" for k in range(1)]:
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
        # volume = volume.transpose(2,0,1)
        volume = np.rot90(volume,axes=(1,0))
        volume = np.rot90(volume,axes=(2,1))
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "FAKE^AXIAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[2]
            ds.Rows = volume.shape[1]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 

            mat = get_orient_mat(ds.ImageOrientationPatient)
            print(mat)
            exit()
            rot_by = np.linalg.inv(rots[1]) @ rots[2] 
            # rot_by = np.linalg.inv(rot_by)
            rotated = (mat @ rot_by)
            ds.ImageOrientationPatient = rotated[0:2].ravel().tolist()


            ds.ImagePositionPatient = [0, 0, -i]
            ds.PixelData = volume[i,:,:].tobytes()
            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as( out_dir / subdir / f"reco.{series}.{i:03}.dcm")



# for x in (0,1,2,3):
#     tip_axial(x)
# coronal()
# orig_sagittal()
fake_axial()