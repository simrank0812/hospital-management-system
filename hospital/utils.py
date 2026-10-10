def get_role(user):
    """Return 'admin', 'doctor', 'patient' or None for the given user."""
    if not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return "admin"
    if hasattr(user, "doctor_profile"):
        return "doctor"
    if hasattr(user, "patient_profile"):
        return "patient"
    return None
