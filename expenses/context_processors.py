from .models import UserSettings


def user_settings(request):
    """Expose the current user's settings to every template as `app_settings`."""
    if request.user.is_authenticated:
        return {'app_settings': UserSettings.for_user(request.user)}
    return {}
