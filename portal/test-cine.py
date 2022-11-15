from pathlib import Path
import time
import pydicom
import numpy as np
import sys
start_time = time.time() 

timepoints = 120
slices_per_volume = 144
slices = list(Path("/opt/gravis/data/cases/e37501cf-dcf6-4d5b-9c76-5ce99d606267/input").glob("**/*.dcm"))


k = None
prototype_ds = None

for i, p in enumerate(slices):
    dcm = pydicom.dcmread(p)
    array = dcm.pixel_array # [ row, column ] order
    if k is None:
        k = np.empty_like(array,shape=(timepoints, *array.shape[::-1], slices_per_volume))
        # [ time, column, row, slice ] order
        prototype_ds = dcm
        print(k.shape)
    timepoint, slice_number = map(int,p.name.split(".")[1:3])
    k[timepoint,:,:,slice_number] = array.T
    if i % 1000 == 0:
        sys.stdout.write(f"{i} / {len(slices)} {(time.time() - start_time) / (i+1) :2f}\n")
assert prototype_ds is not None
assert k is not None
loaded_time = time.time() 
print(f"Loaded in {loaded_time - start_time:.2f}s")

# k in [slice, row, column ] order

# array in [time, column, row, slice] order
num_written = 0
for axis in range(3):
    indices = [slice(None) for x in range(4)]
    rows, columns = [ (axis + k)%3 +1 for k in range(1,3)]
    for i in range(k.shape[axis+1]):
        ds = prototype_ds.copy()
        ds.NumberOfFrames = k.shape[0]
        ds.Rows = k.shape[rows]
        ds.Columns = k.shape[columns]
        indices[axis+1] = i
        ds.PixelData = k[tuple(indices)].tobytes()
        ds.save_as(f"/home/vagrant/gravis/test/multiframe.{axis}.{i}.dcm")
        num_written += 1
        if i % 30 == 0:
            sys.stdout.write(f"Axis {axis}, {i}/{k.shape[axis+1]} {(time.time()-loaded_time)  / num_written:.2f} s/set\n")
written_time = time.time()
print(f"Wrote {num_written} in {written_time-loaded_time:.2f}s, {(written_time-loaded_time)  / num_written:.2f} s/set")
print(f"Total time: {written_time - start_time}")