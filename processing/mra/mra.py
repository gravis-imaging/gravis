# Standard Python includes
import numpy as np
import sys, time, os
from pathlib import Path

# Imports for loading, saving and manipulating DICOMs
import SimpleITK as sitk


class MRA:
    def __init__(self, vars):
        print("ENVIRONMENT INSIDE ", vars, vars["GRAVIS_IN_DIR"])
        self.__input_dir_name = vars["GRAVIS_IN_DIR"]
        self.__output_dir_name_sub = vars["GRAVIS_OUT_DIR"] + "sub/"
        self.__output_dir_name_mip = vars["GRAVIS_OUT_DIR"] + "mip/"
        # Values for all module settings
        # n_slices - number of bottom slices to calculate image intensity
        # angle_step - angle between each projection
        # full_rotation_flag - create projections over 180 or 360 degrees
        self.__angle_step = int(vars["GRAVIS_ANGLE_STEP"])
        self.__full_rotation_flag = bool(vars["GRAVIS_MIP_FULL_ROTATION"])
        print("N SLICES: ", vars["GRAVIS_NUM_BOTTOM_SLICES"])
        self.__n_slices = int(vars["GRAVIS_NUM_BOTTOM_SLICES"])
        self.__min_intensity_index = 0

    def load_grasp_files(self):

        if not Path(self.__input_dir_name).exists():
            print(f"load_grasp_files() IN path does not exist {self.__input_dir_name}")
            sys.exit(1)

        data_directory = os.path.dirname(self.__input_dir_name)

        # Get the list of series IDs.
        reader = sitk.ImageSeriesReader()
        series_IDs = reader.GetGDCMSeriesIDs(data_directory)

        if not series_IDs:
            print(
                'ERROR: given directory "'
                + data_directory
                + '" does not contain a DICOM series.'
            )
            sys.exit(1)

        # Configure the reader to load all of the DICOM tags (public+private):
        # By default tags are not loaded (saves time).
        # By default if tags are loaded, the private tags are not loaded.
        # We explicitly configure the reader to load tags, including the
        # private ones.
        reader.MetaDataDictionaryArrayUpdateOn()
        reader.LoadPrivateTagsOn()

        tags_to_save_dict = {}

        patient_tags_to_copy = [
            "0008|0020",  # Study Date
            "0008|0030",  # Study Time
            "0008|0050",  # Accession Number
            "0008|0060",  # Modality
            "0010|0010",  # Patient Name
            "0010|0020",  # Patient ID
            "0010|0030",  # Patient Birth Date
            "0020|000d",  # Study Instance UID, for machine consumption
            "0020|0010",  # Study ID, for human consumption
        ]

        t = 0
        images = []
        # Use the functional interface to read the image series.
        for series_ID in series_IDs[0:5]:
            print("AAA ", series_ID)
            series_file_names = reader.GetGDCMSeriesFileNames(data_directory, series_ID)
            reader.SetFileNames(series_file_names)
            image = reader.Execute()

            series_tag_values = [
                (k, reader.GetMetaData(0, k))
                for k in patient_tags_to_copy
                if reader.HasMetaDataKey(0, k)
            ] + [
                (
                    "0008|103e",
                    reader.GetMetaData(0, "0008|103e") + " GRASP MIP Projections",
                ),  # Series Description
                ("0018|0050", reader.GetMetaData(0, "0018|0050")),  # Slice Thickness
                ("0020|0011", f"{1000+t:04d}"),  # Series Number
                ("0020|0012", f"{t:04d}"),  # Acquisition Number
            ]

            tags_to_save_dict[t] = series_tag_values

            images.append(image)
            t += 1

        return (images, tags_to_save_dict)

    def get_time_index_of_minimum_intensities(self, images):

        intensities = []
        print("self.__n_slices ", self.__n_slices, len(images))
        n_slices = self.__n_slices
        for image in images:
            vol_n = sitk.GetArrayFromImage(image[:, :, :n_slices])
            intensity = vol_n.sum()
            intensities.append(intensity)

        min_intensity_value = min(intensities)
        self.__min_intensity_index = intensities.index(min_intensity_value) - 2
        print("min_intensity_index ", self.__min_intensity_index)

    def subtract_images(self, images):

        n = len(images)
        subtracted_images = []
        for i in range(self.__min_intensity_index + 1, n):
            subtracted_image = images[i] - images[self.__min_intensity_index]
            subtracted_image = sitk.Cast(subtracted_image, sitk.sitkFloat32)
            subtracted_images.append(subtracted_image)

        return subtracted_images

    def create_projections(self, subtracted_images):

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
        max_angle = np.pi
        max_angle_degree = 180.0
        if self.__full_rotation_flag:
            max_angle = 2 * np.pi
            max_angle_degree = 360.0
        rotation_angles = np.linspace(
            0.0, max_angle, int(max_angle_degree / self.__angle_step)
        )
        print("subtracted_images ", len(subtracted_images))
        for image in subtracted_images:

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
                        image_bounds.append(
                            image.TransformIndexToPhysicalPoint([i, j, k])
                        )
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

        return processed_images

    def save_processed_images(
        self, type, output_dir_name, processed_images, tags_to_save_dict
    ):
        print("save_processed_images called")
        if not os.path.exists(output_dir_name):
            os.mkdir(output_dir_name)
            print("Directory ", output_dir_name, " Created ")
        else:
            print("Directory ", output_dir_name, " already exists")

        writer = sitk.ImageFileWriter()
        writer.KeepOriginalImageUIDOn()

        print("BBB ", len(processed_images))

        # Different times
        t = self.__min_intensity_index
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
            if type == "sub":
                for i in range(images.GetDepth()):
                    image_slice = images[:, :, i]
                    image_slice = sitk.Cast(image_slice, sitk.sitkInt16)

                    [
                        image_slice.SetMetaData(tag, value)
                        for tag, value in series_tag_values
                        if tag not in ("0018|0050")
                    ]
                    [
                        image_slice.SetMetaData(
                            tag, f"{float(value)*max(image_slice.GetSize())}"
                        )
                        for tag, value in series_tag_values
                        if tag in ("0018|0050")
                    ]
                    image_slice.SetMetaData(
                        "0008|0008", "DERIVED\\SECONDARY\\SUB"
                    ),  # Image Type
                    image_slice.SetMetaData(
                        "0008|0012", time.strftime("%Y%m%d")
                    )  # Instance Creation Date
                    image_slice.SetMetaData(
                        "0008|0013", time.strftime("%H%M%S")
                    )  # Instance Creation Time
                    image_slice.SetMetaData(
                        "0008|0021", modification_date
                    )  # Series Date,
                    image_slice.SetMetaData(
                        "0008|0031", modification_time
                    )  # Series Time
                    image_slice.SetMetaData(
                        "0020|000e", seriesID
                    )  # Series Instance UID
                    image_slice.SetMetaData(
                        "0020|0013", f"{i+1:04d}"
                    )  # Instance Number

                    path_name = os.path.join(
                        output_dir_name,
                        "sub." + f"{t:03d}" + "." + f"{i:03d}" + ".dcm",
                    )

                    writer.SetFileName(path_name)
                    writer.Execute(image_slice)
                    i += 1
            else:
                # Different angles
                i = 0
                for image_slice in images:
                    image_slice = sitk.Cast(image_slice, sitk.sitkInt16)

                    [
                        image_slice.SetMetaData(tag, value)
                        for tag, value in series_tag_values
                        if tag not in ("0018|0050")
                    ]
                    [
                        image_slice.SetMetaData(
                            tag, f"{float(value)*max(image_slice.GetSize())}"
                        )
                        for tag, value in series_tag_values
                        if tag in ("0018|0050")
                    ]
                    image_slice.SetMetaData(
                        "0008|0008", "DERIVED\\SECONDARY\\MIP"
                    ),  # Image Type
                    image_slice.SetMetaData(
                        "0008|0012", time.strftime("%Y%m%d")
                    )  # Instance Creation Date
                    image_slice.SetMetaData(
                        "0008|0013", time.strftime("%H%M%S")
                    )  # Instance Creation Time
                    image_slice.SetMetaData(
                        "0008|0021", modification_date
                    )  # Series Date,
                    image_slice.SetMetaData(
                        "0008|0031", modification_time
                    )  # Series Time
                    image_slice.SetMetaData(
                        "0020|000e", seriesID
                    )  # Series Instance UID
                    image_slice.SetMetaData(
                        "0020|0013", f"{i+1:04d}"
                    )  # Instance Number

                    path_name = os.path.join(
                        output_dir_name,
                        "mip."
                        + f"{t:03d}"
                        + "."
                        + f"{i*self.__angle_step:03d}"
                        + ".dcm",
                    )

                    writer.SetFileName(path_name)
                    writer.Execute(image_slice)
                    i += 1
            t += 1

    def calculateMIPs(self):

        # n_slices = 20
        # angle_step = 10
        # full_rotation_flag = False

        images, tags_to_save_dict = self.load_grasp_files()

        self.get_time_index_of_minimum_intensities(images)

        subtracted_images = self.subtract_images(images)

        processed_images = self.create_projections(subtracted_images)
        print("will call save subtracted images")
        self.save_processed_images(
            "sub",
            self.__output_dir_name_sub,
            subtracted_images,
            tags_to_save_dict,
        )
        print("will call save processed images")
        self.save_processed_images(
            "mip",
            self.__output_dir_name_mip,
            processed_images,
            tags_to_save_dict,
        )
