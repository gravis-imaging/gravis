# Standard Python includes
import stat
from loguru import logger
import numpy as np
import time, os
from pathlib import Path

# Imports for loading, saving and manipulating DICOMs
import SimpleITK as sitk
import pydicom
import math

# import json
import ast

from enum import Enum
from collections import defaultdict

# import psutil


class MRA:
    def __init__(self, vars):
        self.input_dir_name = vars["GRAVIS_IN_DIR"]
        
        self.output_dir_name_sub = vars["GRAVIS_OUT_DIR"] + "sub/"
        self.output_dir_name_mip = vars["GRAVIS_OUT_DIR"] + "mip/"

        logger.info(f" __output_dir_name_mip {self.output_dir_name_mip} input dir: {self.input_dir_name}")
        # Values for all module settings
        # n_slices - number of bottom slices to calculate image intensity
        # angle_step - angle between each projection
        # full_rotation_flag - create projections over 180 or 360 degrees
        
        self.n_slices = int(vars["GRAVIS_NUM_BOTTOM_SLICES"])
        self.return_codes = Enum('ReturnCodes', ast.literal_eval(vars["DOCKER_RETURN_CODES"]))
        self.min_intensity_index = 0
        self.tags_to_save_dict = {}
        self.d_files = defaultdict(list)
        self.d_indexes = defaultdict(list)

        self.angle_step = int(vars["GRAVIS_ANGLE_STEP"])
        full_rotation_flag = bool(int(vars["GRAVIS_MIP_FULL_ROTATION"]))
        
        angle_step = self.angle_step 
        max_angle = 180.0
        if full_rotation_flag:
            max_angle = 360.0
        cur_angle = 0.0
        self.rotation_angles = []
        while cur_angle <= max_angle:
            self.rotation_angles.append(cur_angle * np.pi / 180.0)
            cur_angle += angle_step
        
        self.mip_window = None

    def update_window(self, images, window):
        if window is None:
            extreme_values = [math.inf, 0]
        else:
            extreme_values = window[:]
        for _, image_slice in images:
            mmfilter = sitk.MinimumMaximumImageFilter()
            mmfilter.Execute(image_slice)
            extreme_values[0] = min(extreme_values[0],mmfilter.GetMinimum())
            extreme_values[1] = max(extreme_values[1],mmfilter.GetMaximum())


        return extreme_values
        logger.info(f"{window_min}, {window_middle}, {window_width}")

    # def print_RAM(self):
    #     print('RAM total memory excluding swap (GB):', psutil.virtual_memory()[0]/1000000000)
    #     print('RAM available memory (GB):', psutil.virtual_memory()[1]/1000000000)
    #     print('RAM memory % used:', psutil.virtual_memory()[2])
    #     print('RAM Used (GB):', psutil.virtual_memory()[3]/1000000000)
    #     print('RAM memory not used at and is readily available (GB):', psutil.virtual_memory()[4]/1000000000)

    def process_volume(self):

        if not Path(self.input_dir_name).exists():
            logger.exception(f"Input Path {self.input_dir_name} does not exist")
            return self.return_codes.INPUT_PATH_DOES_NOT_EXIST

        data_directory = os.path.dirname(self.input_dir_name)

        # print("=====MEMORY USAGE BEFORE=====")
        # self.print_RAM()

        # Create a map of SeriesIDs wih corresponding lists of files
        reader = sitk.ImageFileReader()
        for f in Path(data_directory).glob("*.dcm"):    
            
            reader.SetFileName(str(f))
            reader.LoadPrivateTagsOn()
            reader.ReadImageInformation()
            acquisition_number = int(reader.GetMetaData("0020|0012"))

            self.d_files[acquisition_number].append(str(f))

            # This will sort the dicoms spatially. 
            im_orientation_patient = np.asarray(list(map(float, reader.GetMetaData("0020|0037").split("\\")))).reshape((2,3))
            im_position_patient = np.asarray(list(map(float, reader.GetMetaData("0020|0032").split("\\"))))
            z_axis = np.cross(*im_orientation_patient)
            z = np.dot(z_axis, im_position_patient)
            self.d_indexes[acquisition_number].append(z)

        if len(self.d_files) == 0:
            logger.exception(
                'ERROR: given directory "'
                + data_directory
                + '" does not contain a DICOM series.'
            )
            return self.return_codes.NO_DICOMS_EXIST

        # Calculate Minimum Intensity index.
        try:
            # Read 50 first time points to find minimum intensity index:
            max_index_to_read = 50          
            beginning_times_volumes = []              
            series_reader = sitk.ImageSeriesReader()
            for acquisition_number in sorted(self.d_files)[0:max_index_to_read]:
                indexes = self.d_indexes[acquisition_number]
                series_file_names =  self.d_files[acquisition_number]
                file_names = [x for _, x in sorted(zip(indexes, series_file_names))]
                
                series_reader.SetFileNames(file_names)
                image = series_reader.Execute()
                beginning_times_volumes.append(image)

            intensities = []
            n_slices = self.n_slices
            for image in beginning_times_volumes:
                vol_n = sitk.GetArrayFromImage(image[:, :, :n_slices])
                intensity = vol_n.sum()
                intensities.append(intensity)

            min_intensity_value = min(intensities)
            # it is expected to have a minimum intensity index in the [10:30] range.
            # if minimum intensity index is the last in the time series of [0: max_index_to_read]
            # # there might be a problem with the data.
            if min_intensity_value == len(beginning_times_volumes) - 1:
                logger.exception("Error while calculating minimum intensity index.")
                return self.return_codes.INTENSITY_INDEX_SHOULD_BE_LESS_THAN_NUM_VOLUMES
            self.min_intensity_index = intensities.index(min_intensity_value) 
            # print("=====MEMORY USAGE AFTER CALCULATING MIN INTENSITY BEFORE CLEARING =====")
            # self.print_RAM()
            beginning_times_volumes.clear()
            # print("min_intensity_index ", self.min_intensity_index)
        except Exception as e:
            logger.exception("Error while calculating minimum intensity index.")
            return self.return_codes.CANNOT_CALCULATE_INTENSITY_INDEX      

        # print("=====MEMORY USAGE AFTER CALCULATING MIN INTENSITY AFTER CLEARING=====")
        # self.print_RAM()
    
        # Read the data, beginning from __min_intensity_index + 1, one time point at a time.
        # Calculate subtractions, and then MIPs for this time point. 
        try:               

            # Save empty subtracted slices for all time points less or equal to minimum intensity.
            # for acquisition_number in sorted(self.d_files)[0:self.min_intensity_index + 1]:
            #     ret_value, image = self.load_grasp_files(acquisition_number)
            #     if ret_value != self.return_codes.NO_ERRORS:
            #         return ret_value

            #     ret_value, subtracted_image = self.subtract_images(image, image)
            #     if ret_value != self.return_codes.NO_ERRORS:
            #         return ret_value

            #     ret_value = self.save_processed_images(
            #         acquisition_number,
            #         "sub",
            #         self.output_dir_name_sub,
            #         subtracted_image,
            #     )
            #     if ret_value != self.return_codes.NO_ERRORS:
            #         return ret_value

            # Create a base volume at the minimum intensity point. 
            ret_value, base_image = self.load_grasp_files(self.min_intensity_index)
            if ret_value != self.return_codes.NO_ERRORS:
                return ret_value


            # For all volumes, subtract base volume and calculate projections
            for acquisition_number in sorted(self.d_files): #[self.min_intensity_index + 1:]:

                ret_value, image = self.load_grasp_files(acquisition_number)
                if ret_value != self.return_codes.NO_ERRORS:
                    return ret_value
            
                ret_value, subtracted_image = self.subtract_images(base_image, image)
                if ret_value != self.return_codes.NO_ERRORS:
                    return ret_value
            
                ret_value, proj_image = self.create_projections(subtracted_image)
                if ret_value != self.return_codes.NO_ERRORS:
                    return ret_value
                
                ret_value = self.save_processed_images(
                    acquisition_number,
                    "mip",
                    self.output_dir_name_mip,
                    proj_image,
                )
                if ret_value != self.return_codes.NO_ERRORS:
                    return ret_value

                ret_value = self.save_processed_images(
                    acquisition_number,
                    "sub",
                    self.output_dir_name_sub,
                    subtracted_image,
                )
                if ret_value != self.return_codes.NO_ERRORS:
                    return ret_value

                # print("=====MEMORY USAGE AFTER EACH LOOP=====")
                # self.print_RAM()
            
            # Set the window size for each MIP dataset.
            # TODO: avoid writing, reading, and then writing over again?
            for mip in Path(self.output_dir_name_mip).glob("*.dcm"):
                ds = pydicom.dcmread(mip)
                window_min = math.floor(self.mip_window[0])
                window_max = math.ceil(self.mip_window[1])
                window_middle = (window_max + window_min) / 2
                window_width = window_max - window_min

                ds.WindowCenter = f"{window_middle:.2f}"
                ds.WindowWidth = f"{window_width:.2f}"
                ds.save_as(mip)

        except Exception as e:
            logger.exception(f"Problem reading DICOM files from {data_directory}.")
            return self.return_codes.DICOM_READING_ERROR

        return self.return_codes.NO_ERRORS


    def load_grasp_files(self, acquisition_number):

        try:

            # Configure the reader to load all of the DICOM tags (public+private):
            # By default tags are not loaded (saves time).
            # By default if tags are loaded, the private tags are not loaded.
            # We explicitly configure the reader to load tags, including the
            # private ones.        

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

            series_reader = sitk.ImageSeriesReader()
            series_reader.LoadPrivateTagsOn()
            series_reader.MetaDataDictionaryArrayUpdateOn()

            indexes = self.d_indexes[acquisition_number]
            series_file_names = self.d_files[acquisition_number]
            file_names = [x for _, x in sorted(zip(indexes, series_file_names))]
            
            series_reader.SetFileNames(file_names)
            image = series_reader.Execute()
            direction = image.GetDirection()
            series_tag_values = [
                (k, series_reader.GetMetaData(0, k))
                for k in patient_tags_to_copy
                if series_reader.HasMetaDataKey(0, k)
            ] + [
                ("0008|0021", series_reader.GetMetaData(0, "0008|0021")),  # Series Date
                ("0008|0031", series_reader.GetMetaData(0, "0008|0031")),  # Series Time
                (
                    "0008|103e",
                    series_reader.GetMetaData(0, "0008|103e") + " GRASP MIP Projections",
                ),  # Series Description
                (
                    "0018|0050",
                    series_reader.GetMetaData(0, "0018|0050"),
                ),  # Slice Thickness
                ("0020|0011", f"{1000+acquisition_number:04d}"),  # Series Number
                ("0020|0012", f"{acquisition_number:04d}"),  # Acquisition Number
                ("0020|0037", '\\'.join(map(str, (direction[0], direction[3], direction[6], # Image Orientation (Patient)
                                                    direction[1], direction[4], direction[7])))),
                ("0020|0052", series_reader.GetMetaData(0, "0020|0052")),  # Frame of Reference UID                
            ]
            self.tags_to_save_dict[acquisition_number] = series_tag_values
            image = sitk.Cast(image, sitk.sitkFloat32)
        except Exception as e:
            logger.exception(f"Problem loading DICOM files for acquisition number: {acquisition_number}.")
            return self.return_codes.DICOM_READING_ERROR
        return self.return_codes.NO_ERRORS, image


    def subtract_images(self, base_image, image):

        try:
            subtracted_image = image - base_image
            #  set all negative pixels to zero
            subtracted_image = sitk.Threshold(subtracted_image, 0, math.inf, 0)
        except Exception as e:
            logger.exception("Error while subtracting images.")
            return self.return_codes.ERROR_CALCULATING_SUBTRACTED_IMAGES
        return self.return_codes.NO_ERRORS, subtracted_image


    def create_projections(self, image):
        
        try:
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
            # max_angle = np.pi
            # max_angle_degree = 180.0
            # if self.full_rotation_flag:
            #     max_angle = 2 * np.pi
            #     max_angle_degree = 360.0
            image.SetDirection( tuple([round(i) for i in image.GetDirection()]) ) # TODO: snap
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
            for angle in self.rotation_angles:
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
                int(sz / spc + 0.5)
                for spc, sz in zip(new_spc, max_bounds - min_bounds)
            ]
            proj_images = []
            for angle in self.rotation_angles:
                rotation_transform.SetRotation(rotation_axis, angle)
                resampled_image = sitk.Resample(
                    image1=image,
                    size=new_sz,
                    transform=rotation_transform,
                    interpolator=sitk.sitkLinear,
                    outputOrigin=min_bounds,
                    outputSpacing=new_spc,
                    outputDirection=[1,0,0,0,1,0,0,0,1],
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
                #  set all negative pixels to zero
                slice_volume = sitk.Threshold(slice_volume, 0, math.inf, 0)                
                proj_images.append((angle, slice_volume))
        except Exception as e:
            logger.exception("Error calculating projections.")
            return self.return_codes.ERROR_CALCULATING_PROJECTIONS

        self.mip_window = self.update_window(proj_images, self.mip_window)

        return self.return_codes.NO_ERRORS, proj_images


    def save_processed_images(self, acquisition_number, type, output_dir_name, images):
        try:
            if not os.path.exists(output_dir_name):
                os.mkdir(output_dir_name)
                logger.info(f"Directory {output_dir_name} created ")
            outdir_path = Path(output_dir_name)
            outdir_path.chmod(outdir_path.stat().st_mode | stat.S_IROTH | stat.S_IXOTH | stat.S_IWOTH)
            # else:
            #     logger.info(f"Directory {output_dir_name} already exists")

            writer = sitk.ImageFileWriter()
            writer.KeepOriginalImageUIDOn()
          
            series_tag_values = self.tags_to_save_dict[acquisition_number]

            # modification_date = time.strftime("%Y%m%d")
            # modification_time = time.strftime("%H%M%S")
           
            if type == "sub":
                seriesID = pydicom.uid.generate_uid()
                for i in range(images.GetDepth()):
                    image_slice = images[:, :, i]
                    image_slice = sitk.Cast(image_slice, sitk.sitkInt16)
                    image_slice.SetMetaData("0020|0032", '\\'.join(map(str,images.TransformIndexToPhysicalPoint((0,0,i)))))  # image position patient
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
                    # image_slice.SetMetaData(
                    #     "0008|0021", modification_date
                    # )  # Series Date,
                    # image_slice.SetMetaData(
                    #     "0008|0031", modification_time
                    # )  # Series Time
                    image_slice.SetMetaData(
                        "0020|000e", seriesID
                    )  # Series Instance UID
                    image_slice.SetMetaData(
                        "0020|0013", f"{i+1:04d}"
                    )  # Instance Number

                    path_name = os.path.join(
                        output_dir_name,
                        "sub." + f"{acquisition_number:03d}" + "." + f"{i:03d}" + ".dcm",
                    )

                    writer.SetFileName(path_name)
                    writer.Execute(image_slice)
                    i += 1
            else:
                seriesID = pydicom.uid.generate_uid()
                # Different angles
                i = 0

                for angle, image_slice in images:
                    image_slice = sitk.Cast(image_slice, sitk.sitkInt16)

                    [
                        image_slice.SetMetaData(tag, value)
                        for tag, value in series_tag_values
                        if tag not in ("0018|0050", "0020|0037")
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
                    # image_slice.SetMetaData(
                    #     "0008|0021", modification_date
                    # )  # Series Date,
                    # image_slice.SetMetaData(
                    #     "0008|0031", modification_time
                    # )  # Series Time
                    image_slice.SetMetaData(
                        "0020|000e", seriesID
                    )  # Series Instance UID
                    image_slice.SetMetaData(
                        "0020|0013", f"{i+1:04d}"
                    )  # Instance Number
                    image_slice.SetMetaData(
                        "0020|1041", f"{angle:.2f}"
                    )
                    path_name = os.path.join(
                        output_dir_name,
                        "mip."
                        + f"{acquisition_number:03d}"
                        + "."
                        + f"{i*self.angle_step:03d}"
                        + ".dcm",
                    )

                    writer.SetFileName(path_name)
                    writer.Execute(image_slice)
                    i += 1

            for p in Path(output_dir_name).glob("**/*"):
                p.chmod(p.stat().st_mode | stat.S_IROTH | stat.S_IXOTH | stat.S_IWOTH)
        except Exception as e:
            logger.exception(f"Error saving files in {output_dir_name}.")
            return self.return_codes.ERROR_SAVING_FILES
        return self.return_codes.NO_ERRORS


    def calculateMIPs(self):

        ret_value = self.process_volume()
        return ret_value
