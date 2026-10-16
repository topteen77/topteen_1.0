from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.email_layout import email_site_url
from core.trending_exams import serialize_trending_exam, trending_exam_queryset


class TrendingExamsAPI(APIView):
    """Public list of exams marked trending in TopTeen admin."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            limit = int(request.GET.get("limit") or 12)
        except (TypeError, ValueError):
            limit = 12
        limit = min(max(limit, 1), 50)
        origin = email_site_url()
        rows = trending_exam_queryset()[:limit]
        results = [serialize_trending_exam(row, origin) for row in rows]
        return Response({"count": len(results), "results": results})
