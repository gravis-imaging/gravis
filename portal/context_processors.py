from .models import Case

def viewer_cases(request):
    if request.user.is_authenticated:
        return dict(viewer_cases=Case.get_user_viewing(request.user))
    return {}