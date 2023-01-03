from __future__ import print_function
import time

import SimpleITK as sitk

import sys, time, os
from pathlib import Path
from collections import defaultdict

# Read the original series. First obtain the series file names using the
# image series reader.
data_directory = "/opt/gravis/data/cases/MF_GRASP_MRA#SSkyraCBI#F429595#M3267#D171018#T145156#GRASPMRAWHOLESAG_RGMW_YK8#P5_221018160934635/"

t = 0
tm = time.perf_counter()
# 120 series IDs
print("Calculating series_dic")



# series_IDs = sitk.ImageSeriesReader.GetGDCMSeriesIDs(data_directory)

# if not series_IDs:
#     print("ERROR: given directory \""+data_directory+"\" does not contain a DICOM series.")
#     sys.exit(1)


reader = sitk.ImageFileReader()
reader.LoadPrivateTagsOn()
reader.ReadImageInformation()

d_files = defaultdict(list)
d_idx = defaultdict(list)
for f in Path(data_directory).glob("*.dcm"):    
    
    reader.SetFileName(str(f))
    
    # series_id = reader.GetMetaData("0020|000e")
    acquisition_number = int(reader.GetMetaData("0020|0012"))
    slice_location = reader.GetMetaData("0020|1041")
    d_files[acquisition_number].append(str(f))
    d_idx[acquisition_number].append(int(slice_location))


print(f"Loaded tags in  {(time.perf_counter() - tm):0.2f} seconds")


tm = time.perf_counter()

series_reader = sitk.ImageSeriesReader()
series_reader.LoadPrivateTagsOn()
series_reader.MetaDataDictionaryArrayUpdateOn()

print("Reading data set")
for series_ID in sorted(d_files):
    print(series_ID)

    indexes = d_idx[series_ID]
    series_file_names = d_files[series_ID]
    file_names = [x for _, x in sorted(zip(indexes, series_file_names))]
    
    series_reader.SetFileNames(file_names)

    image = series_reader.Execute()

    # for i in range(image.GetDepth()):
    #     image_slice = image[:,:,i]
    #     # Tags shared by the series.
    #     for tag, value in series_tag_values:
    #         image_slice.SetMetaData(tag, value)
    #     # Slice specific tags.
    #     image_slice.SetMetaData("0008|0012", time.strftime("%Y%m%d")) # Instance Creation Date
    #     image_slice.SetMetaData("0008|0013", time.strftime("%H%M%S")) # Instance Creation Time
    #     image_slice.SetMetaData("0020|0032", '\\'.join(map(str, image.TransformIndexToPhysicalPoint((0,0,i))))) # Image Position (Patient)
    #     image_slice.SetMetaData("0020|0013", str(i)) # Instance Number

    #     # Write to the output directory and add the extension dcm, to force writing in DICOM format.
    #     writer.SetFileName(os.path.join(out_dir,"save." + f"{t:03d}" + "." + f"{i:03d}" + ".dcm"))
    #     writer.Execute(image_slice)
    # t += 1
print(f"Loaded data set in  {(time.perf_counter() - tm):0.4f} seconds")
sys.exit( 0 )