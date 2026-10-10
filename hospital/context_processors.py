from .utils import get_role


def user_role(request):
    """Makes `user_role` ('admin' / 'doctor' / 'patient') available in every template."""
    return {"user_role": get_role(request.user)}
