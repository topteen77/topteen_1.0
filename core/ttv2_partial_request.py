"""
Detect v2 dashboard ``?ttv2_partial=1`` loads that must return HTML body only.

The unified shell loads those URLs via ``fetch()`` and sets ``X-Requested-With: XMLHttpRequest``.
Plain browser navigations (e.g. GET from a ``<form>`` that echoes ``ttv2_partial``) must receive
the full template so CSS and layout still apply.
"""


def request_wants_ttv2_dashboard_body_partial(request) -> bool:
    if request.GET.get("ttv2_partial") != "1":
        return False
    return (request.headers.get("X-Requested-With") or "").lower() == "xmlhttprequest"
