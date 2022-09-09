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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["study_uid", "series_uid", "instance_uid"], name="unique_uids"
            )
        ]
