from os import stat
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid



class ImageJob(models.Model):
    folder_path = models.CharField(max_length=10000, default=uuid.uuid1)
    rq_id = models.CharField(max_length=10000)
    results = models.CharField(max_length=100000)
    complete = models.BooleanField(default=False)

    class Meta:
        db_table = 'gravis_image_job'


class DockerJob(models.Model):
    docker_image = models.CharField(max_length=10000)
    input_folder = models.CharField(max_length=10000)
    output_folder = models.CharField(max_length=10000)
    complete = models.BooleanField(default=False)

    class Meta:
        db_table = 'gravis_docker_job'


class Case(models.Model):

    class CaseType(models.TextChoices):
        MRA = 'MRA', 'GRASP MRA'
        ONCO = 'Onco', 'GRASP Onco'

    patient_name = models.CharField(max_length=100, blank=False, null=False)
    mrn = models.CharField(max_length=100, blank=False, null=False)
    acc = models.CharField(max_length=100, blank=False, null=False)
    case_type = models.CharField(max_length=4, choices=CaseType.choices, default=CaseType.MRA)
    exam_time = models.DateTimeField(blank=False, null=False)
    receive_time = models.DateTimeField(default=timezone.now, blank=False)
    # status enum ???
    # num_spokes = models.IntegerField(default=0, blank=False, null=False)
    twix_id = models.CharField(max_length=10000, blank=False, null=False)
    
    case_location = models.CharField(max_length=10000, blank=False, null=False)
    incoming_payload = models.JSONField(null=False) 
    reader = models.ForeignKey(User, on_delete=models.SET_NULL, default=None, null=True)

    class Meta:
        db_table = 'gravis_case'


class ProcessingResult(models.Model):
   
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    category = models.CharField(max_length=100, blank=False, null=False) # dicom set, json, image
    status = models.CharField(max_length=100, blank=False, null=False) # success, fail, description
    json_result = models.JSONField(null=True) 
    dicom_set = models.ForeignKey('DICOMSet', on_delete=models.CASCADE, null=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)

    class Meta:
        db_table = 'gravis_processing_result'
        constraints = [
            models.CheckConstraint(
                check=models.Q(json_result__isnull=False) | models.Q(dicom_set__isnull=False),
                name='both_dicom_set_and_json_result_cannot_be_null'
            )
        ]

class DICOMSet(models.Model):

    set_location = models.CharField(max_length=10000, null=False)
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    type = models.CharField(max_length=100, blank=False, null=False) # Incoming, MIP, subtraction
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    processing_result = models.ForeignKey(ProcessingResult, on_delete=models.SET_NULL, default=None, null=True) # null if incoming, otherwise outcome of a processing step
  
    class Meta:
        db_table = 'gravis_dicom_set'


class DICOMInstance(models.Model):
    instance_location = models.CharField(max_length=10000, null=False)
    study_uid = models.CharField(max_length=100) 
    series_uid = models.CharField(max_length=100) 
    instance_uid = models.CharField(max_length=100)  
    json_metadata = models.JSONField(null=False)
    dicom_set = models.ForeignKey(DICOMSet, on_delete=models.CASCADE)
  
    class Meta:
        db_table = 'gravis_dicom_instance'
        constraints = [
            models.UniqueConstraint(
                fields=['dicom_set', 'study_uid', 'series_uid', 'instance_uid'],
                name="unique_uids",
            )
        ]
