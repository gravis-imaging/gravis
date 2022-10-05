import logging
import os, json

from time import sleep
from django.http import HttpResponse
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

from .models import Case

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

    data = []
    objects = Case.objects.all()
    for object in objects:
        data.append(
            {
                "patient_name": object.patient_name,
                "mrn": object.mrn,
                "acc": object.acc,
                "case_type": object.case_type,
                "exam_time": object.exam_time,
                "receive_time": object.receive_time,
                "status": object.status,
                "reader": object.reader,
            }
        )

    context = {"data": data}
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
    instances = Case.objects.all()

    context = {
        "series": set([(k.study_uid, k.series_uid) for k in instances]),
        "studies": set([(k.study_uid,) for k in instances]),
        "case": case,
    }
    # logging.info(context["series"])
    return render(request, "viewer.html", context)
