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
from django.db import connections
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect, csrf_exempt
import numpy as np
from PIL import Image

from .models import *
import django_rq
import docker

logger = logging.getLogger(__name__)
from django.contrib.staticfiles import views as static_views


@login_required
def serve_file(request, path):
    """Serve a file that should only be available to logged-in users."""
    if "localhost" in request.headers["Host"] or "127.0.0.1" in request.headers["Host"]:
        # We're not running behind nginx so we are going to just serve the file ourselves.
        return static_views.serve(request, path)

    # Use nginx's implementation of "x-sendfile" to tell nginx to serve the actual file.
    # see: https://www.nginx.com/resources/wiki/start/topics/examples/x-accel/
    return HttpResponse(
        headers={"X-Accel-Redirect": "/secret/" + path, "Content-Type": ""}
    )


def mandelbrot(m: int = 512, n: int = 256):
    x = np.linspace(-2, 1, num=m).reshape((1, m))
    y = np.linspace(-1, 1, num=n).reshape((n, 1))
    C = np.tile(x, (n, 1)) + 1j * np.tile(y, (1, m))

    Z = np.zeros((n, m), dtype=complex)
    M = np.full((n, m), True, dtype=bool)
    for i in range(20):
        Z[M] = Z[M] * Z[M] + C[M]
        M[np.abs(Z) > 2] = False
    return M.astype(np.uint8) * 255


def julia(arg: complex, m: int = 256, n: int = 512):
    x = np.linspace(-1, 1, num=m).reshape((1, m))
    y = np.linspace(-2, 2, num=n).reshape((n, 1))
    C = np.tile(x, (n, 1)) + 1j * np.tile(y, (1, m))

    # Z = np.zeros((n, m), dtype=complex)
    M = np.full((n, m), True, dtype=bool)
    K = np.full((n, m), 1, dtype=np.uint16)

    for i in range(20):
        C[M] = C[M] * C[M] + arg
        M[np.abs(C) > 2] = False
        # np.log(np.abs(C)+.1).astype('uint16'))
        np.putmask(K, np.abs(C) > 2, 0)
        # K[np.abs(C) > 2] = np.abs(C)
    return K * 255


def image_job(job_id, a, b):
    job: ImageJob = ImageJob.objects.get(id=job_id)
    julia_data = mandelbrot()
    sleep(5.0)
    image = Image.fromarray(julia_data)

    (Path(settings.DATA_FOLDER) / job.folder_path).mkdir(exist_ok=True)
    image.save(Path(settings.DATA_FOLDER) / job.folder_path / "output.png")

    job.results = str(a + b)
    job.complete = True
    job.save()


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
def work_status(request, id):
    job: ImageJob = ImageJob.objects.get(id=id)
    if job.complete:
        return HttpResponse(
            f"""
            <div class="card" style="width: 18rem;">
            <div class="card-body">
                <p class="card-text">Job result</p>
            </div>
            <img src="/media/{job.folder_path}/output.png" class="card-img-bottom">
            </div>""",
            headers={"HX-Trigger": "jobComplete"},
        )
    else:
        return HttpResponse(
            f'<div hx-get="/work_status/{id}" hx-trigger="load delay:1s" hx-swap="outerHTML">Processing...</div>'
        )


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


@login_required
def work_queue_test(request):
    new_job = ImageJob()
    new_job.save()
    result = django_rq.enqueue(image_job, new_job.id, 2, 2)
    new_job.rq_id = result.id
    new_job.save()
    return HttpResponseRedirect(f"/work_status/{new_job.id}/")


def login_request(request):
    logger.debug("HELLO")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("/")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    form = AuthenticationForm()
    return render(request, "login.html", context={"form": form})


def logout_request(request):
    logout(request)
    return redirect("/login")


@login_required
def index(request):
    folder = settings.GRAVIS_DATA + '/cases'
    f = "series.json"
    file_paths = [ os.path.join(d,f) for d in os.scandir(folder) if d.is_dir() ]

    data = []
    for file_path in file_paths:
        if os.path.isfile(file_path):
            with open(file_path, 'r') as myfile:
                d=myfile.read()
            obj = json.loads(d)
            data.append(obj)
        # else:
            # invalid TODO
    context = {
        'data': data
    }
    return render(request, "index.html", context)


@login_required
def user(request):
    context = {}
    return render(request, "user.html", context)


@login_required
def config(request):
    context = {}
    return render(request, "config.html", context)


@login_required
def viewer(request, case=""):
    instances = DICOMInstance.objects.all()

    context = {
        "series": set(
            [(k.study_uid, k.series_uid, k.series_description) for k in instances]
        ),
        "studies": set([(k.study_uid, k.study_description) for k in instances]),
        "case": case,
    }
    # logging.info(context["series"])
    return render(request, "viewer.html", context)
