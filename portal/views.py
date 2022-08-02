import logging
from django.http import HttpResponse
from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import connections
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect, csrf_exempt

import django_rq

logger = logging.getLogger(__name__)

def add(a,b):
    return a+b

@login_required
def work_queue_test(request):
    django_rq.enqueue(add, 2, 2)

    return HttpResponse("ok")


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

