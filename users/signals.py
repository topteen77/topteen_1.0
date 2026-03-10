"""
Signals for users app. Ensures media/users_pdfs/<user_id> is created for every new user
(registration, Google/Facebook login, institute-created students, etc.).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.utils import ensure_user_pdf_folder


@receiver(post_save)
def ensure_user_pdf_folder_on_create(sender, instance, created, **kwargs):
    """Create users_pdfs/<user_id> folder when a new User is created (any source)."""
    if not created:
        return
    # Avoid importing User at module level to prevent circular imports
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if sender is not User:
        return
    if getattr(instance, 'id', None):
        ensure_user_pdf_folder(instance.id)
