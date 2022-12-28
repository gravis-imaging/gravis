import pytest
from pathlib import Path 
import json


from django.conf import settings
import django_rq
from django_rq import get_worker

from fakeredis import FakeRedisConnSingleton
from pyfakefs.fake_filesystem import FakeFilesystem

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset

from .models import *
from .jobs import watch_incoming

@pytest.fixture(autouse=True)
def redis():
    django_rq.queues.get_redis_connection = FakeRedisConnSingleton()

def test_example(fs: FakeFilesystem):
    fs.create_dir(Path(settings.INCOMING_FOLDER) / "test" )
    assert (Path(settings.INCOMING_FOLDER) / "test").exists()

def generate_ds(location):
    ds = Dataset()
    ds.PatientName = "idk"
    ds.is_little_endian = False
    ds.is_implicit_VR=False
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.2'
    ds.file_meta.MediaStorageSOPInstanceUID='1.2.840.10008.5.1.4.1.1.4'
    ds.file_meta.MediaStorageSOPClassUID='1.2.840.10008.5.1.4.1.1.4'
    ds.SeriesDate = "19000101"
    ds.SeriesTime = "1200"
    ds.SeriesNumber = 1
    ds.SliceLocation = 1
    ds.NumberOfFrames = 1
    ds.StudyDate = ds.SeriesDate
    ds.StudyTime = ds.SeriesTime
    ds.ImageType = [ "ORIGINAL", "PRIMARY" ]
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.save_as(location, write_like_original=False)
    return ds

def test_2(fs: FakeFilesystem):

    incoming = Path(settings.INCOMING_FOLDER) 
    cases = Path(settings.CASES_FOLDER) 
    fs.create_dir(incoming / "test" )

    ds = generate_ds(incoming / "test" / "test.dcm")

    fs.create_file(incoming / "test" / "study.json", contents=json.dumps({
        "patient_name": "idk",
        "mrn": "12345",
        "acc": "00000",
        "case_type": "MRA",
        "num_spokes": 10,
        "exam_time": "2022-01-01 01:01",
        "receive_time": "2022-01-01 01:01",
        "twix_id": "TWIXID",
        "settings": {}})
    )
    
    watch_incoming.scan_incoming_folder()
    job = ProcessingJob.objects.all()
    assert len(job) == 0
    
    fs.create_file(incoming / "test" / ".complete")
    watch_incoming.scan_incoming_folder()
    job = ProcessingJob.objects.get()
    assert job.status == "Pending"

    # get_worker().work(burst=True)  
    watch_incoming.process_folder(1, incoming / "test")
    job.refresh_from_db()
    assert job.status == "Success"
    
    folder = next(cases.iterdir())
    assert (folder / "input" / "test.dcm").exists() and (folder / "input" / "study.json").exists() 

    instance = DICOMInstance.objects.get()
    assert instance.series_number == ds.SeriesNumber and instance.slice_location == ds.SliceLocation and instance.json_metadata == ds.to_json()
    
    set = DICOMSet.objects.get()
    assert instance.dicom_set == set

    case = Case.objects.get()
    assert set.case == case and set.processing_job.category == "CopyDICOMSet" and set.processing_job.parameters["incoming_case"] == str(incoming / "test")

def test_orientation():
    from .rqjobs import TestJob, VView
    import numpy as np

    def check_orientation(orientation, expected):
        calc_views =  TestJob.calc_views_for_set(orientation)
        # print(calc_views)
        views = [v.to_dict() for v in calc_views]
        expected_d = [v.to_dict() for v in expected]
        assert views == expected_d

    sagittal_orientation =  \
        [np.array(
            [[ 0, 1,  0 ],
             [ 0, 0, -1 ]]),
            [VView(name='SAG', normal=[1, 0, 0], viewUp=[0, 0, 1], viewHoriz=np.array([ 0, -1,  0]), transformed_axes=np.array([2, 1, 0]), flip_for_preview=[3], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([ 0.,  0., -1.]), transformed_viewUp=np.array([ 0., -1.,  0.]), transformed_viewHoriz=np.array([-1.,  0.,  0.])),
             VView(name='COR', normal=[0, 1, 0], viewUp=[0, 0, 1], viewHoriz=np.array([1, 0, 0]), transformed_axes=np.array([0, 1, 2]), flip_for_preview=[3], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([1., 0., 0.]), transformed_viewUp=np.array([ 0., -1.,  0.]), transformed_viewHoriz=np.array([ 0.,  0., -1.])),
             VView(name='AX', normal=[0, 0, -1], viewUp=[0, -1, 0], viewHoriz=np.array([-1,  0,  0]), transformed_axes=np.array([1, 0, 2]), flip_for_preview=[], flip_for_timeseries=[2], dicom_set=None, transformed_normal=np.array([0., 1., 0.]), transformed_viewUp=np.array([-1.,  0.,  0.]), transformed_viewHoriz=np.array([0., 0., 1.]))]
        ]
    check_orientation(*sagittal_orientation)

    axial_orientation =  \
        [np.array(
            [[ 1, 0, 0 ],
             [ 0, 1, 0 ]]),
            [VView(name='SAG', normal=[1, 0, 0], viewUp=[0, 0, 1], viewHoriz=np.array([ 0, -1,  0]), transformed_axes=np.array([0, 2, 1]), flip_for_preview=[3], flip_for_timeseries=[1], dicom_set=None, transformed_normal=np.array([1., 0., 0.]), transformed_viewUp=np.array([0., 0., 1.]), transformed_viewHoriz=np.array([ 0., -1.,  0.])), 
            VView(name='COR', normal=[0, 1, 0], viewUp=[0, 0, 1], viewHoriz=np.array([1, 0, 0]), transformed_axes=np.array([1, 2, 0]), flip_for_preview=[3, 1], flip_for_timeseries=[1, 2], dicom_set=None, transformed_normal=np.array([0., 1., 0.]), transformed_viewUp=np.array([0., 0., 1.]), transformed_viewHoriz=np.array([1., 0., 0.])), 
            VView(name='AX', normal=[0, 0, -1], viewUp=[0, -1, 0], viewHoriz=np.array([-1,  0,  0]), transformed_axes=np.array([2, 1, 0]), flip_for_preview=[], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([ 0.,  0., -1.]), transformed_viewUp=np.array([ 0., -1.,  0.]), transformed_viewHoriz=np.array([-1.,  0.,  0.]))]
        ]

    check_orientation(*axial_orientation)

    axial_orientation2 =  \
        [np.array(
            [[ 0, 1, 0 ],
             [ 1, 0, 0 ]]),
            [VView(name='SAG', normal=[1, 0, 0], viewUp=[0, 0, 1], viewHoriz=np.array([ 0, -1,  0]), transformed_axes=np.array([1, 2, 0]), flip_for_preview=[3], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([0., 1., 0.]), transformed_viewUp=np.array([ 0.,  0., -1.]), transformed_viewHoriz=np.array([-1.,  0.,  0.])),
             VView(name='COR', normal=[0, 1, 0], viewUp=[0, 0, 1], viewHoriz=np.array([1, 0, 0]), transformed_axes=np.array([0, 2, 1]), flip_for_preview=[3, 2], flip_for_timeseries=[2], dicom_set=None, transformed_normal=np.array([1., 0., 0.]), transformed_viewUp=np.array([ 0.,  0., -1.]), transformed_viewHoriz=np.array([0., 1., 0.])), 
             VView(name='AX', normal=[0, 0, -1], viewUp=[0, -1, 0], viewHoriz=np.array([-1,  0,  0]), transformed_axes=np.array([2, 0, 1]), flip_for_preview=[3], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([0., 0., 1.]), transformed_viewUp=np.array([-1.,  0.,  0.]), transformed_viewHoriz=np.array([ 0., -1.,  0.]))]
        ]

    check_orientation(*axial_orientation2)

    coronal_orientation = \
        [np.array(
            [[ 1, 0,  0 ],
             [ 0, 0, -1 ]]),
             [VView(name='SAG', normal=[1, 0, 0], viewUp=[0, 0, 1], viewHoriz=np.array([ 0, -1,  0]), transformed_axes=np.array([0, 1, 2]), flip_for_preview=[], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([1., 0., 0.]), transformed_viewUp=np.array([ 0., -1.,  0.]), transformed_viewHoriz=np.array([ 0.,  0., -1.])), 
              VView(name='COR', normal=[0, 1, 0], viewUp=[0, 0, 1], viewHoriz=np.array([1, 0, 0]), transformed_axes=np.array([2, 1, 0]), flip_for_preview=[1], flip_for_timeseries=[2], dicom_set=None, transformed_normal=np.array([0., 0., 1.]), transformed_viewUp=np.array([ 0., -1.,  0.]), transformed_viewHoriz=np.array([1., 0., 0.])), 
              VView(name='AX', normal=[0, 0, -1], viewUp=[0, -1, 0], viewHoriz=np.array([-1,  0,  0]), transformed_axes=np.array([1, 2, 0]), flip_for_preview=[], flip_for_timeseries=[], dicom_set=None, transformed_normal=np.array([0., 1., 0.]), transformed_viewUp=np.array([ 0.,  0., -1.]), transformed_viewHoriz=np.array([-1.,  0.,  0.]))]
        ]
    check_orientation(*coronal_orientation)