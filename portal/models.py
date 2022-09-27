from django.db import models
import uuid


class ImageJob(models.Model):
    folder_path = models.CharField(max_length=10000, default=uuid.uuid1)
    rq_id = models.CharField(max_length=10000)
    results = models.CharField(max_length=100000)
    complete = models.BooleanField(default=False)


class DockerJob(models.Model):
    docker_image = models.CharField(max_length=10000)
    input_folder = models.CharField(max_length=10000)
    output_folder = models.CharField(max_length=10000)
    complete = models.BooleanField(default=False)


class Case(models.Model):
    case_location = models.CharField(max_length=10000, blank=False, null=False)

    class Meta:
        db_table = 'portal_case'


# class ProcessingResult(models.Model):
    
#     # processing_type = models.CharField(max_length=100) # either MRA or Onco
    
#     dicom_set = models.ForeignKey('DICOMSet', on_delete=models.CASCADE)
#     # case = models.ForeignKey(Case, on_delete=models.CASCADE)

#     class Meta:
#         db_table = 'portal_processing_result'


class DICOMSet(models.Model):
    from datetime import datetime
    # processing_type =  models.CharField(max_length=100)  # either MRA or Onco, will be inside study.json
    set_location = models.CharField(max_length=10000, null=False)
    created_at =  models.DateTimeField(default=datetime.now, blank = True)
    json_payload = models.JSONField(null=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    # origin = models.ForeignKey(ProcessingResult, on_delete=models.CASCADE, null=True) # null if incoming, otherwise outcome of a processing step
    is_incoming = models.BooleanField()
    class Meta:
        db_table = 'portal_dicom_set'


class DICOMInstance(models.Model):
    instance_location = models.CharField(max_length=10000, null=False)
    study_uid = models.CharField(max_length=100) 
    series_uid = models.CharField(max_length=100) 
    instance_uid = models.CharField(max_length=100)  
    json_metadata = models.JSONField(null=False)
    dicom_set = models.ForeignKey(DICOMSet, on_delete=models.CASCADE)
  
    class Meta:
        db_table = 'portal_dicom_instance'
        constraints = [
            models.UniqueConstraint(
                fields=['dicom_set', 'study_uid', 'series_uid', 'instance_uid'],
                name="unique_uids",
            )
        ]
