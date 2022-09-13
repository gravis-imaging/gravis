from django.conf import settings


class CrossOriginEmbedderPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response[
            "Cross-Origin-Embedder-Policy"
        ] = settings.SECURE_CROSS_ORIGIN_EMBEDDER_POLICY

        return response
