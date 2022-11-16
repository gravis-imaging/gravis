from django.http import HttpResponseNotAllowed, JsonResponse

from django.contrib.auth.decorators import login_required

from .models import Case

class RestfulView(object):
    def __call__(self, request, *args, **kw):
        # try and find a handler for the given HTTP method
        method = request.META['REQUEST_METHOD'].upper()
        handler = getattr(self, 'handle_%s' % method, None)

        if handler is None:
            # compile a list of all our methods and return an HTTP 405
            methods = []
            for x in dir(self):
                if x.startswith('handle_'):
                    methods.append(x[7:])
            return HttpResponseNotAllowed(methods)

        return handler(request, *args, **kw)

class CaseView(RestfulView):       
    @staticmethod
    @login_required
    def handle_POST(request):
        import json
        body = json.loads(request.body.decode('utf-8'))
        response = JsonResponse({'status':'OK'})
        response.status_code = 200
        # print(body['case_id'])
        case_id = body['case_id']
        case = Case.objects.get(id=case_id)
        case.status = Case.CaseStatus.DELETE
        case.save()
        return response
        