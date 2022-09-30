from http.client import HTTPResponse
import logging
import os, json
from pathlib import Path
from time import sleep
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
import numpy as np
from PIL import Image

from .models import *
import django_rq
import docker

# class ImageJob(models.Model):
#     folder_path = models.CharField(max_length=10000, default=uuid.uuid1)
#     rq_id = models.CharField(max_length=10000)
#     results = models.CharField(max_length=100000)
#     complete = models.BooleanField(default=False)

#     class Meta:
#         db_table = 'gravis_image_job'



# def mandelbrot(m: int = 512, n: int = 256):
#     x = np.linspace(-2, 1, num=m).reshape((1, m))
#     y = np.linspace(-1, 1, num=n).reshape((n, 1))
#     C = np.tile(x, (n, 1)) + 1j * np.tile(y, (1, m))

#     Z = np.zeros((n, m), dtype=complex)
#     M = np.full((n, m), True, dtype=bool)
#     for i in range(20):
#         Z[M] = Z[M] * Z[M] + C[M]
#         M[np.abs(Z) > 2] = False
#     return M.astype(np.uint8) * 255


# def julia(arg: complex, m: int = 256, n: int = 512):
#     x = np.linspace(-1, 1, num=m).reshape((1, m))
#     y = np.linspace(-2, 2, num=n).reshape((n, 1))
#     C = np.tile(x, (n, 1)) + 1j * np.tile(y, (1, m))

#     # Z = np.zeros((n, m), dtype=complex)
#     M = np.full((n, m), True, dtype=bool)
#     K = np.full((n, m), 1, dtype=np.uint16)

#     for i in range(20):
#         C[M] = C[M] * C[M] + arg
#         M[np.abs(C) > 2] = False
#         # np.log(np.abs(C)+.1).astype('uint16'))
#         np.putmask(K, np.abs(C) > 2, 0)
#         # K[np.abs(C) > 2] = np.abs(C)
#     return K * 255


# def image_job(job_id, a, b):
#     job: ImageJob = ImageJob.objects.get(id=job_id)
#     julia_data = mandelbrot()
#     sleep(5.0)
#     image = Image.fromarray(julia_data)

#     (Path(settings.DATA_FOLDER) / job.folder_path).mkdir(exist_ok=True)
#     image.save(Path(settings.DATA_FOLDER) / job.folder_path / "output.png")

#     job.results = str(a + b)
#     job.complete = True
#     job.save()

    
# @login_required
# def work_status(request, id):
#     job: ImageJob = ImageJob.objects.get(id=id)
#     if job.complete:
#         return HttpResponse(
#             f"""
#             <div class="card" style="width: 18rem;">
#             <div class="card-body">
#                 <p class="card-text">Job result</p>
#             </div>
#             <img src="/media/{job.folder_path}/output.png" class="card-img-bottom">
#             </div>""",
#             headers={"HX-Trigger": "jobComplete"},
#         )
#     else:
#         return HttpResponse(
#             f'<div hx-get="/work_status/{id}" hx-trigger="load delay:1s" hx-swap="outerHTML">Processing...</div>'
#         )

        
# @login_required
# def work_queue_test(request):
#     new_job = ImageJob()
#     new_job.save()
#     result = django_rq.enqueue(image_job, new_job.id, 2, 2)
#     new_job.rq_id = result.id
#     new_job.save()
#     return HttpResponseRedirect(f"/work_status/{new_job.id}/")



    
def do_docker_job(job_id):
    print(":::Docker job begin:::")
    docker_client = docker.from_env()

    job: DockerJob = DockerJob.objects.get(id=job_id)

    volumes = {
        job.input_folder: {"bind": "/tmp/data", "mode": "rw"},
        job.output_folder: {"bind": "/tmp/output", "mode": "rw"},
    }
    environment = dict(MERCURE_IN_DIR="/tmp/data", MERCURE_OUT_DIR="/tmp/output")

    container = docker_client.containers.run(
        job.docker_image,
        volumes=volumes,
        environment=environment,
        user=f"{os.getuid()}:{os.getegid()}",
        group_add=[os.getegid()],
        detach=True,
    )
    print("Docker is running...")
    docker_result = container.wait()
    print(docker_result)
    print("=== MODULE OUTPUT - BEGIN ========================================")
    if container.logs() is not None:
        logs = container.logs().decode("utf-8")
        print(logs)
    print("=== MODULE OUTPUT - END ==========================================")
    job.complete = True
    job.save()


@login_required
def docker_job(request):
    new_job = DockerJob(
        docker_image="mercureimaging/mercure-testmodule",
        input_folder="/home/vagrant/pineapple/in",
        output_folder="/home/vagrant/pineapple/out",
    )
    new_job.save()
    result = django_rq.enqueue(do_docker_job, new_job.id)
    new_job.rq_id = result.id
    new_job.save()
    return HttpResponse("OK")
    # return HttpResponseRedirect(f"/work_status/{new_job.id}/")


