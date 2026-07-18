"""
Class 10 assessment PDF background jobs.

Keeps WeasyPrint off the Gunicorn request path under concurrent load.
"""
import logging
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory

from core.utils import (
    class10_assessment_pdf_filename,
    class10_pdf_lock_key,
    user_pdf_exists,
)
from topteens.celery import app

logger = logging.getLogger(__name__)
User = get_user_model()

PDF_LOCK_TTL_SECONDS = 600


def enqueue_class10_assessment_pdf(user_id, test_paper, base_url):
    """
    Queue PDF generation once per user/test (Redis lock).

    Returns True if work is already done, already queued, or successfully queued.
    Returns False if the caller should fall back to synchronous generation
    (Celery disabled / broker unavailable).
    """
    if not user_id or not test_paper:
        return False

    filename = None
    try:
        user = User.objects.only('id', 'name', 'email').get(pk=user_id)
        filename = class10_assessment_pdf_filename(user, test_paper)
        if user_pdf_exists(user_id, filename):
            return True
    except User.DoesNotExist:
        logger.warning("enqueue_class10_assessment_pdf: user %s missing", user_id)
        return True
    except Exception:
        logger.exception("enqueue_class10_assessment_pdf: pre-check failed user=%s", user_id)

    lock_key = class10_pdf_lock_key(user_id, test_paper)
    if not cache.add(lock_key, '1', PDF_LOCK_TTL_SECONDS):
        # Another worker is already generating this PDF.
        return True

    if not getattr(settings, 'ENABLE_CELERY', True):
        cache.delete(lock_key)
        return False

    try:
        generate_class10_assessment_pdf.delay(user_id, test_paper, base_url or '')
        return True
    except Exception:
        cache.delete(lock_key)
        logger.exception(
            "enqueue_class10_assessment_pdf: failed to queue user=%s test=%s",
            user_id,
            test_paper,
        )
        return False


@app.task(ignore_result=True)
def generate_class10_assessment_pdf(user_id, test_paper, base_url=''):
    """Run the existing download_pdf WeasyPrint path off the web workers."""
    lock_key = class10_pdf_lock_key(user_id, test_paper)
    try:
        user = User.objects.get(pk=user_id)
        filename = class10_assessment_pdf_filename(user, test_paper)
        if user_pdf_exists(user_id, filename):
            return {'status': 'exists', 'user_id': user_id, 'test_paper': test_paper}

        parsed = urlparse(base_url or getattr(settings, 'TOPTEEN_SITE_URL', 'https://www.topteen.in'))
        host = parsed.netloc or 'www.topteen.in'
        scheme = parsed.scheme or 'https'
        factory = RequestFactory()
        path = f'/psychometric/download_pdf/{test_paper}/'
        request = factory.get(path, HTTP_HOST=host)
        request.user = user
        request.META['wsgi.url_scheme'] = scheme
        if scheme == 'https':
            request.META['HTTP_X_FORWARDED_PROTO'] = 'https'

        # Lazy import avoids circular import at module load.
        from app.views import download_pdf

        download_pdf(request, test_paper, _sync_generate=True)
        return {'status': 'generated', 'user_id': user_id, 'test_paper': test_paper}
    except Exception:
        logger.exception(
            "generate_class10_assessment_pdf failed user=%s test=%s",
            user_id,
            test_paper,
        )
        raise
    finally:
        cache.delete(lock_key)
