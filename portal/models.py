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
