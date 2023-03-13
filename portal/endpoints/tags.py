import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from portal.endpoints.common import json_load_body

from portal.models import *



@login_required
@require_GET
def all_tags(request):
    '''
    Returns a JSON object containing information on all tags stored in the database.
    '''
    return JsonResponse({"tags": [(tag.name, tag.case_set.all().count()) for tag in Tag.objects.all()]}, safe=False)


@login_required
@require_GET
def case_tags(request, case):
    '''
    Returns a JSON object containing information on all tags stored in the database 
    and tags specific to the current case.
    '''
    case = get_object_or_404(Case, id=case)
    return JsonResponse({"tags": [tag.name for tag in Tag.objects.all()], 
                         "case_tags": [tag.name for tag in case.tags.all()]}, safe=False)


@login_required
@require_POST
@transaction.atomic
def update_case_tags(request, case):
    '''
    Updates tags for a given case and returns response.ok if successful
    '''
    case = get_object_or_404(Case, id=case)
    body = json_load_body(request)
    if 'tags' not in body:
        return HttpResponseBadRequest()

    tags = body['tags']

    # clear old tags from the case, but keep the tags in db
    old_tags = case.tags.all()
    for old_tag in old_tags:
        case.tags.remove(old_tag)

    for tag in tags:
        the_tag = Tag.objects.filter(name=tag).first()
        if the_tag is None:
            the_tag = Tag(name=tag)
            the_tag.save()
        case.tags.add(the_tag)
        
        
    return HttpResponse() 

 
@login_required
@require_POST
@transaction.atomic
def update_tags(request):
    '''
    Delete selected tags and returns response.ok if successful
    '''
    body = json_load_body(request)

    if 'tags' not in body:
        return HttpResponseBadRequest()
    
    tags = [ get_object_or_404(Tag, name=tag_name) for tag_name in body['tags'] ]
    for tag in tags:
        tag.delete()

    return HttpResponse() 

