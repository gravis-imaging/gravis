from http.client import HTTPResponse
import logging
from pathlib import Path
from time import sleep
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import connections
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect, csrf_exempt
import numpy as np
from PIL import Image

from .models import *
import django_rq

logger = logging.getLogger(__name__)


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
    return K*255

def image_job(job_id, a, b):
    job: ImageJob = ImageJob.objects.get(id=job_id)
    julia_data = mandelbrot()
    sleep(5.0)
    image = Image.fromarray(julia_data)
    
    (Path(settings.DATA_FOLDER) / job.folder_path).mkdir(exist_ok=True)
    image.save(Path(settings.DATA_FOLDER) / job.folder_path / "output.png" )
    
    job.results = str(a+b)
    job.complete = True
    job.save()


@login_required
def work_status(request, id):
    job: ImageJob = ImageJob.objects.get(id=id)
    if job.complete:
        return HttpResponse(f'''
            <div class="card" style="width: 18rem;">
            <div class="card-body">
                <p class="card-text">Job result</p>
            </div>
            <img src="/media/{job.folder_path}/output.png" class="card-img-bottom">
            </div>''', 
            headers={'HX-Trigger':'jobComplete'})
    else:
        return HttpResponse(f'<div hx-get="/work_status/{id}" hx-trigger="load delay:1s" hx-swap="outerHTML">Processing...</div>')

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
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("/")
            else:
                messages.error(request,"Invalid username or password.")
        else:
            messages.error(request,"Invalid username or password.")    
    form = AuthenticationForm()
    return render(request, 'login.html', context={"form": form})


def logout_request(request):
    logout(request)
    return redirect("/login")


@login_required
def index(request):

    #with connections['yarralog'].cursor() as cursor:
    #    cursor.execute("select * from scanners;")
    #    print(cursor.fetchall())

    context = {}
    return render(request, 'index.html', context)

