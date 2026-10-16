from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from core.models import EntranceTestPrepExam, TrendingExam
from core.trending_exams import renumber_trending_positions, search_exams_for_trending, trending_exam_queryset
from topteenadmin.utils import build_admin_breadcrumb


@method_decorator(login_required, name="dispatch")
class TrendingExamWidgetView(TemplateView):
    template_name = "topteenadmin/trending_exams.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = (self.request.GET.get("q") or "").strip()
        ctx.update({
            "active_tab": "trendingexams",
            "title": "Trending exams",
            "meta_title": "Trending exams",
            "html_head": {"title": "Trending exams", "description": ""},
            "breadcrumb": build_admin_breadcrumb([
                {"title": "Trending exams", "text": "Trending exams", "url": reverse("topteenadminmanaged:trendingexamswidget")},
            ]),
            "query": query,
            "trending": trending_exam_queryset(),
            "search_results": search_exams_for_trending(query) if query else [],
        })
        return ctx

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        if action == "add":
            exam = get_object_or_404(EntranceTestPrepExam, pk=request.POST.get("exam_id"))
            if not TrendingExam.objects.filter(exam=exam).exists():
                last = TrendingExam.objects.order_by("-position").first()
                TrendingExam.objects.create(exam=exam, position=(last.position + 1) if last else 1)
                messages.success(request, f"{exam.name} is now a trending exam.")
            else:
                messages.info(request, f"{exam.name} is already trending.")
        elif action == "remove":
            row = get_object_or_404(TrendingExam, pk=request.POST.get("trending_id"))
            name = row.exam.name
            row.delete()
            renumber_trending_positions()
            messages.success(request, f"{name} was removed from trending exams.")
        elif action in ("up", "down"):
            row = get_object_or_404(TrendingExam, pk=request.POST.get("trending_id"))
            ordered = list(TrendingExam.objects.order_by("position", "id"))
            index = next((i for i, item in enumerate(ordered) if item.pk == row.pk), None)
            swap_with = None
            if index is not None and action == "up" and index > 0:
                swap_with = ordered[index - 1]
            elif index is not None and action == "down" and index < len(ordered) - 1:
                swap_with = ordered[index + 1]
            if swap_with is not None:
                row.position, swap_with.position = swap_with.position, row.position
                row.save(update_fields=["position"])
                swap_with.save(update_fields=["position"])
                renumber_trending_positions()
        elif action == "summary":
            row = get_object_or_404(TrendingExam, pk=request.POST.get("trending_id"))
            row.summary = (request.POST.get("summary") or "").strip()[:400]
            row.save(update_fields=["summary", "modified"])
            messages.success(request, f"Summary saved for {row.exam.name}.")
        query = (request.POST.get("q") or "").strip()
        url = reverse("topteenadminmanaged:trendingexamswidget")
        if query:
            url = f"{url}?q={quote(query)}"
        return redirect(url)
