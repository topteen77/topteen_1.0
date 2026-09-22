"""Seat capacity helpers: class 11/12 x stream, plus who may edit."""
from core import choices

STREAMS = ("pcm", "cbm", "comm", "hme", "hmb")
STREAM_CODES = ("PCM", "CBM", "COMM", "HME", "HMB")
STREAM_LABELS = {"PCM": "PCM", "CBM": "CB", "COMM": "COMM", "HME": "HUM", "HMB": "HM"}
STREAM_ALIASES = {
    "CB": "CBM", "CBM": "CBM", "MCOM": "COMM", "COMM": "COMM",
    "HUM": "HME", "HME": "HME", "HM": "HMB", "HMB": "HMB", "PCM": "PCM",
}
SEAT_CAPACITY_VALUE_FIELDS = (
    "id", "slug", "name", "address",
    "pcm", "cbm", "comm", "hme", "hmb",
    "pcm_12", "cbm_12", "comm_12", "hme_12", "hmb_12",
)


def _suffix(class_key):
    return "_12" if str(class_key or "").strip().lower() in ("12", "12th", "class12", "class 12") else ""


def _field(stream, class_key="11"):
    key = (stream or "").strip().lower()
    return (key + _suffix(class_key)) if key in STREAMS else ""


def _int(value, default=100):
    if value in (None, ""):
        return default
    n = int(value)
    if n < 0:
        raise ValueError("Seat capacity cannot be negative.")
    return n


def _get(obj, name, default=100):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return _int(obj.get(name, default), default)
    return _int(getattr(obj, name, default), default)


def capacity_for_stream(institute, stream, class_key="11"):
    field = _field(stream, class_key)
    return _get(institute, field, 100) if field else 100


def class_capacity_map(institute, class_key="11"):
    return {s: capacity_for_stream(institute, s, class_key) for s in STREAMS}


def serialize_institute_capacity(institute):
    c11 = class_capacity_map(institute, "11")
    c12 = class_capacity_map(institute, "12")
    get = institute.get if isinstance(institute, dict) else lambda k, d="": getattr(institute, k, d)
    return {
        "id": _get(institute, "id", 0),
        "slug": get("slug", "") or "",
        "name": get("name", "") or "",
        "address": get("address", "") or "",
        "pcm": c11["pcm"], "cbm": c11["cbm"], "comm": c11["comm"], "hme": c11["hme"], "hmb": c11["hmb"],
        "pcm_12": c12["pcm"], "cbm_12": c12["cbm"], "comm_12": c12["comm"], "hme_12": c12["hme"], "hmb_12": c12["hmb"],
        "class_11": c11, "class_12": c12,
    }


def parse_capacity_post(post):
    parsed = {"11": {}, "12": {}}
    for stream in STREAMS:
        raw11 = post.get("%s_11" % stream) or post.get("%s-11" % stream) or post.get(stream)
        raw12 = post.get("%s_12" % stream) or post.get("%s-12" % stream)
        if raw11 not in (None, ""):
            parsed["11"][stream] = _int(raw11)
        if raw12 not in (None, ""):
            parsed["12"][stream] = _int(raw12)
    return {k: v for k, v in parsed.items() if v}


def apply_seat_capacity(institute, parsed):
    for class_key, values in (parsed or {}).items():
        for stream, qty in (values or {}).items():
            field = _field(stream, class_key)
            if field:
                setattr(institute, field, _int(qty))
    return institute


def user_can_edit_institute_seat_capacity(user, institute):
    if not user or not getattr(user, "is_authenticated", False) or not institute:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    ut = getattr(user, "user_type", None)
    if ut == choices.UserType.INSTITUTE and getattr(institute, "created_by_id", None) == user.id:
        return True
    mg = getattr(institute, "marketing_group", None)
    if ut == choices.UserType.MARKETINGGROUPADMIN and mg and getattr(mg, "marketing_group_admin_id", None) == user.id:
        return True
    ig = getattr(institute, "institute_group", None)
    if ut == choices.UserType.INSTITUTEGROUPADMIN and ig and getattr(ig, "institute_group_admin_id", None) == user.id:
        return True
    return False


def _norm_stream(raw):
    key = (raw or "").strip().upper()
    return STREAM_ALIASES.get(key, key if key in STREAM_CODES else "")


def _class_from_label(label):
    text = (label or "").strip().lower()
    if "12" in text:
        return "12"
    if "11" in text:
        return "11"
    return ""


def attach_streams_capacity_context(ctx, institute, student_qs=None):
    streams_meta = [{"code": c, "label": STREAM_LABELS.get(c, c)} for c in STREAM_CODES]
    classes = ["11th", "12th"]
    cap_map_by_class = {
        "11th": {c: capacity_for_stream(institute, c.lower(), "11") for c in STREAM_CODES},
        "12th": {c: capacity_for_stream(institute, c.lower(), "12") for c in STREAM_CODES},
    }
    cap_map = {c: cap_map_by_class["11th"][c] + cap_map_by_class["12th"][c] for c in STREAM_CODES}
    filled = {"11": {c: 0 for c in STREAM_CODES}, "12": {c: 0 for c in STREAM_CODES}}
    if student_qs is not None:
        try:
            rows = student_qs.select_related("class_and_section")
        except Exception:
            rows = student_qs or []
        for sm in rows:
            cas = getattr(sm, "class_and_section", None)
            if not cas:
                continue
            ck = _class_from_label(getattr(cas, "class_and_section", None))
            code = _norm_stream(getattr(cas, "stream", None))
            if ck in filled and code in filled[ck]:
                filled[ck][code] += 1
    class_rows = []
    total_capacity = seats_filled = 0
    occupancy_acc = {c: {"filled": 0, "cap": 0} for c in STREAM_CODES}
    for idx, (label, ck) in enumerate(zip(classes, ("11", "12")), start=1):
        cells = {}
        row_total = row_filled = 0
        for code in STREAM_CODES:
            cap = cap_map_by_class[label][code]
            used = filled[ck][code]
            cells[code] = {"cap": cap, "filled": used, "available": max(0, cap - used)}
            row_total += cap
            row_filled += used
            occupancy_acc[code]["cap"] += cap
            occupancy_acc[code]["filled"] += used
        total_capacity += row_total
        seats_filled += row_filled
        class_rows.append({
            "idx": idx, "class_label": label, "streams": cells, "total": row_total,
            "filled": row_filled, "available": max(0, row_total - row_filled),
            "fill_pct": round(100.0 * row_filled / row_total, 2) if row_total else 0,
        })
    occupancy = []
    for code in STREAM_CODES:
        cap = occupancy_acc[code]["cap"]
        used = occupancy_acc[code]["filled"]
        occupancy.append({
            "code": code, "label": STREAM_LABELS.get(code, code),
            "filled": used, "cap": cap,
            "pct": round(100.0 * used / cap, 2) if cap else 0,
        })
    payload = {
        "streams_meta": streams_meta, "classes": classes, "cap_map": cap_map,
        "cap_map_by_class": cap_map_by_class, "occupancy_by_stream": occupancy, "class_rows": class_rows,
        "kpis": {
            "total_capacity": total_capacity, "seats_filled": seats_filled,
            "open_seats": max(0, total_capacity - seats_filled),
            "fill_rate_pct": round(100.0 * seats_filled / total_capacity, 2) if total_capacity else 0,
            "streams_count": len(STREAM_CODES), "classes_count": 2, "capacity_per_stream_default": 100,
        },
    }
    ctx["ttv2_streams_capacity"] = class_rows
    ctx["ttv2_streams_capacity_payload"] = payload
    return ctx
