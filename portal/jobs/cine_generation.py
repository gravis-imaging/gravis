import json
import stat
import uuid
from pathlib import Path

from django.urls import path
import numpy as np
import numpy.typing as npt
import pydicom

from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from .work_job import WorkJobView
from loguru import logger

def cross(*c) -> npt.ArrayLike:
    return np.cross(*c)

def show_array(a):
    print(f"""P2
{a.shape[1]} {a.shape[0]}
{a.max()}
"""+"\n".join(" ".join([str(k) for k in r]) for r in a))

class GeneratePreviewsJob(WorkJobView):
    type = "CINE"

    @classmethod
    def mat_to_rotations(cls,mat):
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

    @classmethod
    def do_job(cls, job: ProcessingJob):
        instances = job.dicom_set.instances.all()
        first_instance_metadata = json.loads(instances[0].json_metadata)
        if "00200037" not in first_instance_metadata:
            raise Exception("ImageOrientationPatient tag missing from dataset. This may not be a volume at all.")
        
        im_orientation_patient = np.asarray(first_instance_metadata["00200037"]["Value"]).reshape((2,3))
        im_orientation_mat = np.vstack((im_orientation_patient,[cross(*im_orientation_patient)]))
        z_axis = im_orientation_mat[2]
        # views = cls.calc_views_for_set(im_orientation_patient)

        def get_position(instance):
            return np.asarray(json.loads(instance.json_metadata)["00200032"]["Value"])


        locations = sorted([np.dot(z_axis,get_position(k)) for k in instances if k.series_uid == instances[0].series_uid])
        logger.info(f"z-axis {z_axis}")

        average_z_spacing = (max(locations) - min(locations)) / (len(locations)-1) #TODO: really subtract 1 here? why does this work? 

        voxel_spacing = [average_z_spacing, *first_instance_metadata["00280030"]["Value"]]
        logger.info(f"====== Voxel spacing is {voxel_spacing} =====")
        series_uids = { k.series_uid for k in instances }
        split_by_series = [ sorted([k for k in instances if k.series_uid == uid], key = lambda x:np.dot(z_axis,get_position(x))) for uid in series_uids ]
        files_by_series = [ [ Path(i.dicom_set.set_location) / i.instance_location for i in k] for k in sorted(split_by_series,key=lambda x:x[0].acquisition_seconds) ]

        random_name = str(uuid.uuid4())
        dicom_sets = []
        for v in ("AX", "COR", "SAG"):
            location = Path(job.case.case_location) / "processed" / (v+"-"+random_name)
            location.mkdir()
            dicom_set = DICOMSet(
                set_location = location,
                type = f"CINE/{v}",
                case = job.case,
                processing_job = job)
            dicom_set.save()
            dicom_sets.append(dicom_set)
            # output_folder = Path(new_set.set_location)

        volume = None
        prototype_ds = None
        undersample = 1
        num_series = len(files_by_series) 

        if job.parameters.get("undersample",None) == True:
            if num_series > 20:
                if num_series % 20 == 0:
                    undersample = 20
                elif num_series % 10 == 0:
                    undersample = 10
                elif num_series % 5 == 0:
                    undersample = 5
        elif job.parameters.get("undersample", None):
            undersample = job.parameters["undersample"]
        for i, files in enumerate(files_by_series[::undersample]):
            for j, file in enumerate(files):
                dcm = pydicom.dcmread(file)
                array = dcm.pixel_array # [ row, column ] order
                if volume is None:
                    volume = np.empty_like(array,shape=(len(files_by_series) // undersample, len(files), *array.shape))
                    prototype_ds = dcm
                    print(volume.shape)
                volume[i,j,:,:] = array
        assert volume is not None
        orient = np.rint(np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))
        rotations = cls.mat_to_rotations(orient)
        for k,axes in rotations:
            volume = np.rot90(volume,k=k, axes=[a+1 for a in axes])
        logger.info(f"Volume shape: {volume.shape}")

        voxel_spacing_rot = np.abs(orient @ voxel_spacing)
        logger.info(f"Voxel spacing rotated {voxel_spacing_rot}")
        def get_index(axis,volume_slice, time=slice(None)):
            return [(time,volume_slice,        slice(None),  slice(None)), # axial 
                    (time,slice(None,None,-1), volume_slice, slice(None)), # coronal
                    (time,slice(None,None,-1), slice(None),  volume_slice) # sagittal
            ][axis]

        # axial, coronal, sagittal = [volume[get_index(axis,volume.shape[axis+1]//2)] for axis in (0,1,2)]
        # print(axial.shape, coronal.shape, sagittal.shape)
        # try:
        #     show_array(np.vstack([axial[0], coronal[0], sagittal[0]]))
        # except:
        #     show_array(np.hstack([axial[0], coronal[0], sagittal[0]]))
        # exit()

        for axis in (0,1,2):
            new_study_uid = pydicom.uid.generate_uid()
            new_series_uid = pydicom.uid.generate_uid()
            
            if axis == 0: # TODO: make sure this is right
                pixel_spacing = [voxel_spacing_rot[2],voxel_spacing_rot[1]]
            elif axis == 1:
                pixel_spacing = [voxel_spacing_rot[2],voxel_spacing_rot[0]]
            elif axis == 2:
                pixel_spacing = voxel_spacing_rot[0:2].tolist()

            logger.info(f"Axis {axis} pixel spacing {pixel_spacing}")
            for i in range(volume.shape[axis+1]):
                t_array = volume[get_index(axis,i)]
                ds = prototype_ds.copy()
                ds.NumberOfFrames   = t_array.shape[0]
                ds.Rows             = t_array.shape[1]
                ds.Columns          = t_array.shape[2]
                ds.PixelData        = t_array.tobytes()
                ds.SliceLocation    = str(i)+".0"
                ds.SeriesNumber     = str(i)

                ds.StudyInstanceUID  = new_study_uid
                ds.SeriesInstanceUID = new_series_uid
                ds.SOPInstanceUID    = pydicom.uid.generate_uid()
                # ds.PixelSpacing      = pixel_spacing

                p = Path(dicom_sets[axis].set_location) / f"multiframe.{i}.dcm"
                ds.save_as(p)
                p.chmod(p.stat().st_mode | stat.S_IROTH | stat.S_IXOTH) #TODO: is this necessary?

                new_instance = DICOMInstance.from_dataset(ds)
                new_instance.dicom_set = dicom_sets[axis]
                new_instance.instance_location = f"multiframe.{i}.dcm"
                new_instance.save()

        return (
            {}, # {"views": {v.name: v.to_dict() for v in views}},
            dicom_sets
        )

