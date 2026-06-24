"""
Service availability status: Redis, Celery (broker), Elasticsearch.
Populated at Django startup so the app can use these flags without re-checking.
Import from here: from topteens.services_status import REDIS_AVAILABLE, CELERY_AVAILABLE, ELASTICSEARCH_AVAILABLE
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Set by run_startup_checks(); safe defaults for use before ready()
REDIS_AVAILABLE = False
CELERY_AVAILABLE = False
ELASTICSEARCH_AVAILABLE = False

# Whether each service is enabled in settings (from .env)
REDIS_ENABLED = False
CELERY_ENABLED = False
ELASTICSEARCH_ENABLED = False

_startup_done = False


def run_startup_checks():
    """
    Check Redis, Celery broker, and Elasticsearch at startup.
    Log what's available and what's not; set module-level flags for the app.
    Call from AppConfig.ready() (e.g. core.apps).
    """
    global REDIS_AVAILABLE, CELERY_AVAILABLE, ELASTICSEARCH_AVAILABLE
    global REDIS_ENABLED, CELERY_ENABLED, ELASTICSEARCH_ENABLED
    global _startup_done

    if _startup_done:
        return
    _startup_done = True

    from django.conf import settings

    # With runserver, the reloader spawns two processes; only the child has RUN_MAIN=true. Print there so we show once.
    # When not runserver (e.g. gunicorn), print in the single process.
    print_services = (os.environ.get("RUN_MAIN") == "true") or ("runserver" not in sys.argv)

    REDIS_ENABLED = getattr(settings, 'ENABLE_REDIS', True)
    CELERY_ENABLED = getattr(settings, 'ENABLE_CELERY', True)
    ELASTICSEARCH_ENABLED = getattr(settings, 'ENABLE_ELASTICSEARCH', True)

    # Update module globals for imports
    import topteens.services_status as mod
    mod.REDIS_ENABLED = REDIS_ENABLED
    mod.CELERY_ENABLED = CELERY_ENABLED
    mod.ELASTICSEARCH_ENABLED = ELASTICSEARCH_ENABLED

    lines = ["--- Services (startup) ---"]

    # --- Redis ---
    if REDIS_ENABLED:
        try:
            redis_host = getattr(settings, 'REDIS_HOST', '127.0.0.1')
            redis_port = int(getattr(settings, 'REDIS_PORT', 6379))
            import redis
            r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=2)
            r.ping()
            r.close()
            REDIS_AVAILABLE = True
            mod.REDIS_AVAILABLE = True
            lines.append("  Redis:          available")
        except Exception as e:
            REDIS_AVAILABLE = False
            mod.REDIS_AVAILABLE = False
            lines.append(f"  Redis:          not available ({e})")
    else:
        REDIS_AVAILABLE = False
        mod.REDIS_AVAILABLE = False
        lines.append("  Redis:          disabled (ENABLE_REDIS=False)")

    # --- Celery (broker) ---
    if CELERY_ENABLED and REDIS_ENABLED:
        try:
            from celery import current_app
            with current_app.connection_or_acquire() as conn:
                conn.connect()
                conn.release()
            CELERY_AVAILABLE = True
            mod.CELERY_AVAILABLE = True
            lines.append("  Celery (broker): available")
        except Exception as e:
            CELERY_AVAILABLE = False
            mod.CELERY_AVAILABLE = False
            lines.append(f"  Celery (broker): not available ({e})")
    else:
        CELERY_AVAILABLE = False
        mod.CELERY_AVAILABLE = False
        if not CELERY_ENABLED:
            lines.append("  Celery (broker): disabled (ENABLE_CELERY=False)")
        else:
            lines.append("  Celery (broker): disabled (Redis disabled)")

    # --- Elasticsearch ---
    if ELASTICSEARCH_ENABLED:
        try:
            from elasticsearch import Elasticsearch
            es_host = getattr(settings, 'ELASTICSEARCH_HOST', 'localhost')
            es_port = getattr(settings, 'ELASTICSEARCH_PORT', 9200)
            es = Elasticsearch([f"http://{es_host}:{es_port}"], timeout=2)
            if es.ping():
                ELASTICSEARCH_AVAILABLE = True
                mod.ELASTICSEARCH_AVAILABLE = True
                lines.append("  Elasticsearch:  available")
            else:
                ELASTICSEARCH_AVAILABLE = False
                mod.ELASTICSEARCH_AVAILABLE = False
                lines.append("  Elasticsearch:  not available (ping failed)")
        except Exception as e:
            ELASTICSEARCH_AVAILABLE = False
            mod.ELASTICSEARCH_AVAILABLE = False
            lines.append(f"  Elasticsearch:  not available ({e})")
    else:
        ELASTICSEARCH_AVAILABLE = False
        mod.ELASTICSEARCH_AVAILABLE = False
        lines.append("  Elasticsearch:  disabled (ENABLE_ELASTICSEARCH=False)")

    # --- COMMON_BASE_PATH (static/media) ---
    try:
        common_base = getattr(settings, 'COMMON_BASE_PATH', None)
        if common_base:
            static_root = getattr(settings, 'STATIC_ROOT', '')
            media_root = getattr(settings, 'MEDIA_ROOT', '')
            lines.append("  COMMON_BASE_PATH:  " + str(common_base))
            lines.append("    STATIC_ROOT:     " + ("found" if os.path.isdir(static_root) else "not found") + " (" + str(static_root) + ")")
            lines.append("    MEDIA_ROOT:      " + ("found" if os.path.isdir(media_root) else "not found") + " (" + str(media_root) + ")")
        else:
            lines.append("  COMMON_BASE_PATH:  not set (using BASE_DIR)")
    except Exception as e:
        lines.append("  COMMON_BASE_PATH:  error checking (" + str(e) + ")")

    if print_services:
        logger.debug("\n".join(lines))
