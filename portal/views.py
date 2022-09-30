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

from .models import *
logger = logging.getLogger(__name__)
from django.contrib.staticfiles import views as static_views

# TODO: Work with Roy to remove test/extra functions
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
    # TODO
    # wait until disk/db decision is made: invalid when series.json does not exist or cannot be opened
    # wait until disk/db decision is made: validate values from json
    # lock cases.json file while preprocessor is working

    cases = {}
    folder = settings.GRAVIS_DATA + '/cases'
    cases_json = folder + '/cases.json'
    if os.path.isfile(cases_json) and os.access(cases_json, os.R_OK):
        try:
            with open(cases_json, 'r') as cases_cache:
                cases=json.load(cases_cache)       
        except Exception:
            logger.warning(  # handle_error
                            f"Unable to read cases.json in {folder}. It will be recreated."
                          )

    f = "study.json"
    file_paths = [ os.path.join(d,f) for d in os.scandir(folder) if d.is_dir() ]

    data = []
    for file_path in file_paths:
        if os.path.isfile(file_path):
            if file_path not in cases:
                try:
                    with open(file_path, 'r') as myfile:
                        d=myfile.read()
                    obj = json.loads(d)
                    data.append(obj)
                    cases[file_path] = data
                except Exception:
                    logger.error(  # handle_error
                        f"Unable to read series.json in {folder}."
                        # invalid TODO
                    )
            else:
                data = cases[file_path]

        # else:
            # invalid TODO

    with open(cases_json, 'w') as f:
        json.dump(cases, f)  

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
    instances = Case.objects.all()

    context = {
        "series": set(
            [(k.study_uid, k.series_uid, k.series_description) for k in instances]
        ),
        "studies": set([(k.study_uid, k.study_description) for k in instances]),
        "case": case,
    }
    # logging.info(context["series"])
    return render(request, "viewer.html", context)
