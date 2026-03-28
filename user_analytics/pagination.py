"""Pagination helpers for analytics views."""
import inspect

from django.core.paginator import Paginator
from django.utils.functional import cached_property
from django.utils.inspect import method_has_no_args


class KnownCountPaginator(Paginator):
    """
    Skips COUNT(*) when the caller already computed the total with the same filters
    (e.g. aggregate on the same queryset).
    """

    def __init__(
        self,
        object_list,
        per_page,
        orphans=0,
        allow_empty_first_page=True,
        *,
        total_count=None,
    ):
        self._total_count_override = total_count
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)

    @cached_property
    def count(self):
        if self._total_count_override is not None:
            return self._total_count_override
        c = getattr(self.object_list, "count", None)
        if callable(c) and not inspect.isbuiltin(c) and method_has_no_args(c):
            return c()
        return len(self.object_list)
