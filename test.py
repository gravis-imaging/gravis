# Standard Python includes
import numpy as np
import sys, time, os
from pathlib import Path

# Imports for loading, saving and manipulating DICOMs
import SimpleITK as sitk
from collections import defaultdict

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'app.settings'
import django
django.setup()
from django.conf import settings



def load_grasp_files(dir_name: str):

    if not Path(dir_name).exists():
        print("IN path does not exist")
        sys.exit(1)

    data_directory = os.path.dirname(dir_name)


    print("data_directory ", data_directory)

    # Get the list of series IDs.
    # reader = sitk.ImageSeriesReader()

    tm = time.perf_counter()
    print("load_grasp_files Reading data set")

    reader = sitk.ImageFileReader()
    d_files = defaultdict(list)
    d_idx = defaultdict(list)
    for f in Path(data_directory).glob("*.dcm"):    
    
        reader.SetFileName(str(f))
        reader.LoadPrivateTagsOn()
        reader.ReadImageInformation()
        # series_id = reader.GetMetaData("0020|000e")
        acquisition_number = int(reader.GetMetaData("0020|0012"))
        slice_location = reader.GetMetaData("0020|1041")
        d_files[acquisition_number].append(str(f))
        d_idx[acquisition_number].append(int(slice_location))


    # series_IDs = reader.GetGDCMSeriesIDs(data_directory)

    # if not series_IDs:
    #     print(
    #         'ERROR: given directory "'
    #         + data_directory
    #         + '" does not contain a DICOM series.'
    #     )
    #     sys.exit(1)

    # Configure the reader to load all of the DICOM tags (public+private):
    # By default tags are not loaded (saves time).
    # By default if tags are loaded, the private tags are not loaded.
    # We explicitly configure the reader to load tags, including the
    # private ones.

    series_reader = sitk.ImageSeriesReader()
    series_reader.MetaDataDictionaryArrayUpdateOn()
    series_reader.LoadPrivateTagsOn()

    # reader.MetaDataDictionaryArrayUpdateOn()
    # reader.LoadPrivateTagsOn()

    tags_to_save_dict = {}

    patient_tags_to_copy = [
        "0008|0020",  # Study Date
        "0008|0030",  # Study Time
        "0008|0050",  # Accession Number
        "0008|0060" "0010|0010",  # Modality  # Patient Name
        "0010|0020",  # Patient ID
        "0010|0030",  # Patient Birth Date
        "0020|000d",  # Study Instance UID, for machine consumption
        "0020|0010",  # Study ID, for human consumption
    ]

    t = 0
    images = []
    # Use the functional interface to read the image series.
    

    for series_ID in sorted(d_files):
        print(series_ID)

        indexes = d_idx[series_ID]
        series_file_names = d_files[series_ID]
        file_names = [x for _, x in sorted(zip(indexes, series_file_names))]
        # series_reader = sitk.ImageSeriesReader()
        series_reader.SetFileNames(file_names)
        # print("SERIES ID ", series_ID)
        # for f in file_names:
        #     print(f)
        image = series_reader.Execute()

        series_tag_values = [
            (k, series_reader.GetMetaData(0, k))
            for k in patient_tags_to_copy
            if series_reader.HasMetaDataKey(0, k)
        ] + [
            ("0008|0008", "DERIVED\\SECONDARY"),  # Image Type
            (
                "0008|103e",
                series_reader.GetMetaData(0, "0008|103e") + " GRASP MIP Projections",
            ),  # Series Description
            ("0018|0050", series_reader.GetMetaData(0, "0018|0050")),  # Slice Thickness
            ("0020|0011", f"{1000+t:04d}"),  # Series Number
            ("0020|0012", f"{t:04d}"),  # Acquisition Number
        ]

        tags_to_save_dict[t] = series_tag_values
        # image = sitk.Cast(image, sitk.sitkFloat32)
        images.append(image)
        t += 1

    print(f"load_grasp_files Loaded data set in  {(time.perf_counter() - tm):0.4f} seconds. time points = {len(images)}")

    return (images, tags_to_save_dict)

    
def get_time_index_of_minimum_intensities(images, n_slices):

    tm = time.perf_counter()
    print("get_time_index_of_minimum_intensities")

    intensities = []
    for image in images:
        vol_n = sitk.GetArrayFromImage(image[:, :, :n_slices])
        intensity = vol_n.sum()
        intensities.append(intensity)
    print("INTENSITIES ", intensities)
    min_intensity_value = min(intensities)
    min_intensity_index = intensities.index(min_intensity_value)
    print(f"get_time_index_of_minimum_intensities in  {(time.perf_counter() - tm):0.4f} seconds. min_intensity_index = {min_intensity_index}")
    return min_intensity_index


def subtract_images(images, min_intensity_index):
    tm = time.perf_counter()
    print("subtract_images")

    n = len(images)
    subtracted_images = []
    for i in range(min_intensity_index + 1, n):
        subtracted_image = images[i] - images[min_intensity_index]
        subtracted_images.append(subtracted_image)
    print(f"subtract_images in  {(time.perf_counter() - tm):0.4f} seconds. size = {len(subtracted_images)}")
    return subtracted_images



    
def create_projections(subtracted_images, angle_step, full_rotation_flag):
    tm = time.perf_counter()
    print("create_projections")
    processed_images = []
    projection = {
        "sum": sitk.SumProjection,
        "mean": sitk.MeanProjection,
        "std": sitk.StandardDeviationProjection,
        "min": sitk.MinimumProjection,
        "max": sitk.MaximumProjection,
    }
    ptype = "max"
    paxis = 1
    rotation_axis = [0, 0, 1]
    for image in subtracted_images:
        max_angle = np.pi
        max_angle_degree = 180.0
        if full_rotation_flag:
            max_angle = 2 * np.pi
            max_angle_degree = 360.0

        rotation_angles = np.linspace(
            0.0, max_angle, int(max_angle_degree / angle_step)
        )
        rotation_center = image.TransformContinuousIndexToPhysicalPoint(
            [(index - 1) / 2.0 for index in image.GetSize()]
        )

        rotation_transform = sitk.VersorRigid3DTransform()
        rotation_transform.SetCenter(rotation_center)

        # Compute bounding box of rotating volume and the resampling grid structure
        image_indexes = list(zip([0, 0, 0], [sz - 1 for sz in image.GetSize()]))
        image_bounds = []
        for i in image_indexes[0]:
            for j in image_indexes[1]:
                for k in image_indexes[2]:
                    image_bounds.append(image.TransformIndexToPhysicalPoint([i, j, k]))
        all_points = []
        for angle in rotation_angles:
            rotation_transform.SetRotation(rotation_axis, angle)
            all_points.extend(
                [rotation_transform.TransformPoint(pnt) for pnt in image_bounds]
            )
        all_points = np.array(all_points)
        min_bounds = all_points.min(0)
        max_bounds = all_points.max(0)
        # resampling grid will be isotropic so no matter which direction we project to
        # the images we save will always be isotropic
        new_spc = [np.min(image.GetSpacing())] * 3
        new_sz = [
            int(sz / spc + 0.5) for spc, sz in zip(new_spc, max_bounds - min_bounds)
        ]
        proj_images = []
        for angle in rotation_angles:
            rad = angle * np.pi / 180.0
            new_dir = (
                np.cos(rad),
                0,
                np.sin(rad),
                0,
                1,
                0,
                -np.sin(rad),
                0,
                np.cos(rad),
            )
            rotation_transform.SetRotation(rotation_axis, angle)
            resampled_image = sitk.Resample(
                image1=image,
                size=new_sz,
                transform=rotation_transform,
                interpolator=sitk.sitkLinear,
                outputOrigin=min_bounds,
                outputSpacing=new_spc,
                outputDirection=new_dir,
            )
            proj_image = projection[ptype](resampled_image, paxis)
            proj_image = sitk.DICOMOrient(proj_image, "LPI")
            # In cases when we rotate around x or y axises we need to
            # covert the image to 2D first and then add z axis to make the image 3D.
            # The image has to be 3D to be properly saved in DICOM format.
            extract_size = list(proj_image.GetSize())
            extract_size[paxis] = 0
            extracted_image = sitk.Extract(proj_image, extract_size)
            slice_volume = sitk.JoinSeries(extracted_image)
            slice_volume.SetOrigin((min_bounds + max_bounds) / 2)
            proj_images.append(slice_volume)
        processed_images.append(proj_images)
    print(f"create_projections in  {(time.perf_counter() - tm):0.4f} seconds, processed_images size: {len(processed_images)}")
    return processed_images


def save_grasp_files(
    output_dir_name, processed_images, tags_to_save_dict, angle_step, begin_time_index
):
    tm = time.perf_counter()
    print("save_grasp_files")

    if not os.path.exists(output_dir_name):
        os.mkdir(output_dir_name)
        print("Directory ", output_dir_name, " Created ")
    else:
        print("Directory ", output_dir_name, " already exists")

    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Different times
    t = begin_time_index
    for images in processed_images:
        series_tag_values = tags_to_save_dict[t]

        modification_date = time.strftime("%Y%m%d")
        modification_time = time.strftime("%H%M%S")
        seriesID = (
            "1.2.826.0.1.3680043.2.1125."
            + modification_date
            + modification_time
            + f".{t:03d}"
        )
        # Different angles
        i = 0
        for image in images:
            image = sitk.Cast(image, sitk.sitkInt16)

            [
                image.SetMetaData(tag, value)
                for tag, value in series_tag_values
                if tag not in ("0018|0050")
            ]
            [
                image.SetMetaData(tag, f"{float(value)*max(image.GetSize())}")
                for tag, value in series_tag_values
                if tag in ("0018|0050")
            ]
            image.SetMetaData(
                "0008|0012", time.strftime("%Y%m%d")
            )  # Instance Creation Date
            image.SetMetaData(
                "0008|0013", time.strftime("%H%M%S")
            )  # Instance Creation Time
            image.SetMetaData("0008|0021", modification_date)  # Series Date,
            image.SetMetaData("0008|0031", modification_time)  # Series Time
            image.SetMetaData("0020|000e", seriesID)  # Series Instance UID
            image.SetMetaData("0020|0013", f"{i+1:04d}")  # Instance Number

            writer.SetFileName(
                os.path.join(
                    output_dir_name,
                    "reco." + f"{t:03d}" + "." + f"{i*angle_step:03d}" + ".dcm",
                )
            )
            writer.Execute(image)
            i += 1
        t += 1
    
    print(f"save_grasp_files in  {(time.perf_counter() - tm):0.4f} seconds")



def main():

    import os

    tmt = time.perf_counter()

    # dir_name = os.environ["GRAVIS_IN_DIR"]
    # input_dir_name = dir_name + "/input/"

    dir_name = "/opt/gravis/data/incoming"
    # input_dir_name = "/opt/gravis/data/cases/to_copy_full/"
    
    input_dir_name = settings.TEST_FOLDER_PATH
    print(input_dir_na
    if not Path(input_dir_name).exists():
        print("IN path does not exist")
        sys.exit(1)

    # Create default values for all module settings
    # n_slices - number of bottom slices to calculate image intensity
    # angle_step - angle between each projection
    # full_rotation_flag - create projections over 180 or 360 degrees
    # settings = {"n_slices": 20, "angle_step": 10, "full_rotation_flag": False}
    # n_slices = 20
    # angle_step = 10
    # full_rotation_flag = False

    # processed_images, tags_to_save_dict = load_grasp_files(input_dir_name)

    # # min_intensity_index = get_time_index_of_minimum_intensities(images, n_slices)

    # # subtracted_images = subtract_images(images, min_intensity_index)

    # # processed_images = create_projections(
    # #     subtracted_images, angle_step, full_rotation_flag
    # # )

    # output_dir_name = dir_name + "/processed/"
    # save_grasp_files(
    #     output_dir_name,
    #     processed_images,
    #     tags_to_save_dict
    #     # angle_step,
    #     # min_intensity_index + 1,
    # )

    n_slices = 20
    angle_step = 10
    full_rotation_flag = False

    images, tags_to_save_dict = load_grasp_files(input_dir_name)

    min_intensity_index = get_time_index_of_minimum_intensities(images, n_slices)

    subtracted_images = subtract_images(images, min_intensity_index)

    processed_images = create_projections(
        subtracted_images, angle_step, full_rotation_flag
    )

    output_dir_name = dir_name + "/tmp_to_delete9/"
    save_grasp_files(
        output_dir_name,
        processed_images,
        tags_to_save_dict,
        angle_step,
        min_intensity_index + 1,
    )
    print(f"total time {(time.perf_counter() - tmt):0.4f} seconds")
    sys.exit(0)


if __name__ == "__main__":
    main()