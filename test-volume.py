from typing import Any
from pydicom import Dataset
import pydicom
from pathlib import Path
import numpy as np
from collections import defaultdict

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

def get_orient_mat_orig(im_orientation_pt):
    arr = np.asarray(im_orientation_pt).reshape((2,3))
    return np.vstack((arr,[cross(*arr)]))


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
        new_series_uid = pydicom.uid.generate_uid()
        files = sorted(list(Path("/opt/gravis/data/cases/e37501cf-dcf6-4d5b-9c76-5ce99d606267/input").glob(f"reco.{series}.*.dcm")))
        example_dcm = pydicom.dcmread(files[0])

        z_axis = get_orient_mat_orig(example_dcm.ImageOrientationPatient)[2]
        datasets = [pydicom.dcmread(f) for f in files]
        datasets = sorted(datasets, key=lambda ds: np.dot(z_axis,ds.ImagePositionPatient))

        volume = np.asarray([ds.pixel_array for ds in datasets])
        

        # volume = volume.transpose(2,0,1)
        volume = np.rot90(volume,axes=(2,0))
        
        mat = get_orient_mat(example_dcm.ImageOrientationPatient)
        rot_by = np.linalg.matrix_power(rots[2], 1)
        # rot_by = np.linalg.inv(rot_by)
        rotated_mat = (mat @ rot_by)
        # exit()
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "FAKE^CORONAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[2]
            ds.Rows = volume.shape[1]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 
            ds.ImageOrientationPatient = rotated_mat[0:2].ravel().tolist()
            ds.ImagePositionPatient = [0, i, 0]
            ds.PixelData = volume[i,:,:].tobytes()
            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as( out_dir / subdir / f"reco.{series}.{i:03}.dcm")



def sagittal_flip():
    subdir = "sagittal_flip"
    (out_dir / subdir).mkdir(exist_ok=True)

    new_study_uid = pydicom.uid.generate_uid()

    for series in [f"{k:03}" for k in range(1)]:
        new_series_uid = pydicom.uid.generate_uid()
        files = sorted(list(Path("/opt/gravis/data/cases/e37501cf-dcf6-4d5b-9c76-5ce99d606267/input").glob(f"reco.{series}.*.dcm")))
        example_dcm = pydicom.dcmread(files[0])

        z_axis = get_orient_mat_orig(example_dcm.ImageOrientationPatient)[2]
        datasets = [pydicom.dcmread(f) for f in files]
        datasets = sorted(datasets, key=lambda ds: np.dot(z_axis,ds.ImagePositionPatient))

        volume = np.asarray([ds.pixel_array for ds in datasets])
        volume = np.flip(volume,2)
        # volume = volume.transpose(2,0,1)
        # volume = np.rot90(volume,axes=(2,0))
        # volume = np.rot90(volume,axes=(2,0))

        mat = get_orient_mat(example_dcm.ImageOrientationPatient)
        print(mat)
        mat[0] = -mat[0]
        print(mat)
        # rot_by = np.linalg.matrix_power(rots[2], 2)
        # rot_by = np.linalg.inv(rot_by)
        # rotated_mat = (mat @ rot_by)
        # exit()
        for i in range(volume.shape[0]):
            ds = example_dcm.copy()
            ds.PatientName = "FAKE^FLIP^SAGITTAL"
            ds.PatientID = "000000"
            ds.PatientBirthDate = "19000101"
            ds.Columns = volume.shape[2]
            ds.Rows = volume.shape[1]
            ds.SliceLocation = f"{i}.0"
            ds.InstanceNumber = i 
            ds.ImageOrientationPatient = mat[0:2].ravel().tolist()
            ds.ImagePositionPatient = [-i, 0, 0]
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
            rotations += [(n,(0,2))] 

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

def test_all_orientations():
    axial_data = synthetic_data(np.array([[1,0,0],[0,1,0],[0,0,1]]))

    orientations = all_orientations()
    for i,o in enumerate(orientations):
        print(i)
        mat = get_orient_mat(o)
        print(mat)
        # print(np.linalg.inv(mat))
        volume = synthetic_data(mat)
        # print(volume[0])
        rotations = mat_to_rotations(mat)
        # print(rotations)
        # print(volume[0,:,:])
        
        for k,axes in rotations:
            volume = np.rot90(volume,k=k, axes=axes)
        assert np.array_equal(axial_data,volume)

    # print(o, rotations)


# m = get_orient_mat(orientations[0])

# print(arr[:,:,0])

# for dc_set in Path("/opt/gravis/data/test_volume_2").iterdir():
#     # if dc_set.name != 'orig_sagittal': continue
#     # if dc_set.name not in ('coronal', 'axial_1','axial_2', 'axial_3', 'orig_sagittal'): continue
#     print(dc_set.name)
#     subdir = dc_set.name + "_transformed"
#     (out_dir / subdir).mkdir(exist_ok=True)




def transform_dir(in_folder, out_folder):
    dcm = next(in_folder.iterdir())

    example_ds = pydicom.dcmread(dcm)
    mat = get_orient_mat(example_ds.ImageOrientationPatient)
    rotations = mat_to_rotations(mat)
    files = sorted(in_folder.glob(f"reco.000.*.dcm"))
    new_series_uid = pydicom.uid.generate_uid()
    volume = []

    z_axis = get_orient_mat_orig(example_ds.ImageOrientationPatient)[2]

    datasets = [pydicom.dcmread(f) for f in files]
    datasets = sorted(datasets, key=lambda ds: np.dot(z_axis,ds.ImagePositionPatient))
    for ds in datasets:
        volume.append(ds.pixel_array)
    volume = np.asarray(volume)
    # exit()
    for k,axes in rotations:
        volume = np.rot90(volume,k=k, axes=axes)

    for i in range(volume.shape[0]):
        ds = example_ds.copy()
        ds.PatientName = f"TRANSFORMED^{in_folder.name}"
        ds.PatientID = "000000"
        ds.PatientBirthDate = "19000101"
        ds.Columns = volume.shape[2]
        ds.Rows = volume.shape[1]
        ds.SliceLocation = f"{i}.0"
        ds.InstanceNumber = i 
        ds.ImageOrientationPatient = [1,0,0,0,1,0]
        ds.ImagePositionPatient = [0, 0, i]
        ds.PixelData = volume[i,:,:].tobytes()
        ds.SeriesInstanceUID = new_series_uid
        ds.SOPInstanceUID    = pydicom.uid.generate_uid()

        ds.save_as( out_folder / f"reco.000.{i:03}.dcm")
    print(in_folder.name)

def show_array(a):
    print(f"""P2
{a.shape[1]} {a.shape[0]}
{a.max()}
"""+"\n".join(" ".join([str(k) for k in r]) for r in a))


def load_case(folder):
    files = list(Path(folder).glob(f"*.dcm"))

    series = defaultdict(lambda: [])
    for f in files:
        _,series_n,slice_n, _ = f.name.split(".")
        series[int(series_n)].append(f)
    
    volumes = []
    for k in range(10): # range(len(series)):
        volumes.append([pydicom.dcmread(x,defer_size ='1 KB') for x in series[k]])
    
    for v in range(len(volumes)):
        z_axis = get_orient_mat_orig(volumes[v][0].ImageOrientationPatient)[2]
        volumes[v] = sorted(volumes[v], key=lambda ds: np.dot(z_axis,ds.ImagePositionPatient))

    return get_orient_mat(volumes[0][0].ImageOrientationPatient), np.asarray([ [ ds.pixel_array for ds in v ] for v in volumes ]), volumes[0][0]

# def previews_from_axial(volume):


def render_previews(case, out_folder):
    out_folders = [Path(out_folder) / x for x in ("AX", "COR", "SAG")]
    for f in out_folders:
        f.mkdir(exist_ok=True)

    orient, volume, example_ds = load_case(case)
    rotations = mat_to_rotations(orient)
    for k,axes in rotations:
        volume = np.rot90(volume,k=k, axes=[a+1 for a in axes])

    def get_index(axis,volume_slice, time=slice(None)):
        return [(time,volume_slice,slice(None),slice(None)),
            (time,slice(None,None,-1),volume_slice,slice(None)),
            (time,slice(None,None,-1),slice(None),volume_slice)
        ][axis]
    
    new_study_uid = pydicom.uid.generate_uid()
    for axis in (0,1,2):
        new_series_uid = pydicom.uid.generate_uid()

        for i in range(volume.shape[axis+1]):
            t_array = volume[get_index(axis,i)]
            ds = example_ds.copy()
            ds.NumberOfFrames   = t_array.shape[0]
            ds.Rows             = t_array.shape[1]
            ds.Columns          = t_array.shape[2]
            ds.PixelData        = t_array.tobytes()
            ds.SliceLocation    = str(i)+".0"
            ds.SeriesNumber     = str(i)

            ds.StudyInstanceUID  = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID    = pydicom.uid.generate_uid()

            ds.save_as(out_folders[axis] / f"multiframe.{i}.dcm")
            # new_instance = DICOMInstance.from_dataset(ds)
            # new_instance.dicom_set = v.dicom_set
            # new_instance.instance_location = f"multiframe.{i}.dcm"
            # new_instance.save()


    # axial, coronal, sagittal = [volume[get_index(axis,volume.shape[axis+1]//2)] for axis in (0,1,2)]
    # axial = volume[0,volume.shape[1]//2,:,:]
    # coronal = volume[0,::-1,volume.shape[2]//2,:]
    # sagittal = volume[0,::-1,:,volume.shape[3]//2]
    # show_array(np.vstack([axial, coronal, sagittal]))

# test_all_orientations()
# render_previews("/opt/gravis/data/cases/e37501cf-dcf6-4d5b-9c76-5ce99d606267/input")
render_previews("/opt/gravis/data/cases/2e500281-b99d-479d-af67-3575c7e86104/input", "/vagrant/test_previews")
# fake_coronal()
# sagittal_flip()
# transform_dir(Path("/opt/gravis/data/test_volume/sagittal_flip"), Path("/opt/gravis/data/test_volume/sagittal_flip_transformed"))
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