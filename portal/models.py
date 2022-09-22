import uuid
from django.db import models

# Create your models here.


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


class DICOMInstance(models.Model):
    study_uid = models.CharField(max_length=100)
    series_uid = models.CharField(max_length=100)
    instance_uid = models.CharField(max_length=100)
    file_location = models.CharField(max_length=10000)
    json_metadata = models.JSONField(null=True)

    patient_name = models.CharField(max_length=10000, null=True)
    study_description = models.CharField(max_length=10000, null=True)
    series_description = models.CharField(max_length=10000, null=True)

    case = models.ForeignKey("Case", on_delete=models.PROTECT, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["study_uid", "series_uid", "instance_uid", "case"],
                name="unique_uids",
            )
        ]


class Case(models.Model):
    data_location = models.CharField(max_length=10000)


# DBML
# https://dbdiagram.io/
# Table DicomInstance {
#   id int [pk]
#   set int [ref: > DicomSet.id]
#   file_location path
#   study_uid "dcm uuid"
#   series_uid "dcm uuid"
#   instance_uid "dcm uuid"
#   json_metadata json

#   Indexes {
#     (set, study_uid, series_uid, instance_uid) [unique]
#   }
# }
# Table DicomSet {
#   id int [pk]
#   case int [ ref: > Case.id]
#   type text
#   folder_location path
#   created_by int [ ref: > ProcessingResult.id]
# }

# Table ProcessingResult {
#   id int [pk]
#   created_on timestamp
#   type text
#   json_result json
#   input_set int [ ref: > DicomSet.id ]
#   case int [ ref: > Case.id ]
# }

# Table Case {
#   id int [pk]
#   data_location varchar
# }
