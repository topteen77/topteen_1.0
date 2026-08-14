from django.http import HttpResponse


class HealthCheckMiddleware:
    """Return 200 for ALB/ECS health checks before ALLOWED_HOSTS is enforced.

    The load balancer sends the target's internal IP as Host. Django would
    otherwise reject that with 400 if the IP is not in ALLOWED_HOSTS.
    This middleware must be first in MIDDLEWARE so it runs before
    SecurityMiddleware / CommonMiddleware call request.get_host().
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ('/health/', '/health'):
            return HttpResponse("OK", status=200)
        return self.get_response(request)
