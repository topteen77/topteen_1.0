from django.db.utils import OperationalError, ProgrammingError
from core.models import URLIndexRule


class URLIndexingMiddleware:
    """
    Apply X-Robots-Tag headers based on admin-managed URLIndexRule records.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or "/"
        try:
            for rule in URLIndexRule.get_active_rules().filter(apply_x_robots_tag=True):
                if rule.matches(path):
                    response["X-Robots-Tag"] = "noindex, nofollow"
                    break
        except (ProgrammingError, OperationalError):
            # Table may not exist yet before migrations are applied.
            return response
        return response

