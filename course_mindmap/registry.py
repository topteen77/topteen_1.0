from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from course_mindmap.constants import COURSE_TYPE_SKILLLAB


class BaseCourseMindmapAdapter:
    course_type_key: str = ""
    label: str = ""

    def get_course_queryset(self):
        raise NotImplementedError

    def get_course_by_id(self, course_id: int):
        return self.get_course_queryset().filter(pk=course_id).first()

    def get_course_display_name(self, course) -> str:
        return str(course)

    def build_scopes(self, course, *, map_type: str = "classic_vertical") -> list[dict]:
        """
        Return list of scope dicts:
        {scope, scope_id, label, markdown, meta}
        """
        raise NotImplementedError

    def content_type(self) -> ContentType:
        qs = self.get_course_queryset()
        return ContentType.objects.get_for_model(qs.model)


def get_registered_adapters() -> dict[str, BaseCourseMindmapAdapter]:
    from course_mindmap.adapters.skilllab import SkillLabMindmapAdapter

    return {
        COURSE_TYPE_SKILLLAB: SkillLabMindmapAdapter(),
    }


def get_adapter(course_type_key: str) -> BaseCourseMindmapAdapter:
    adapters = get_registered_adapters()
    if course_type_key not in adapters:
        raise ValueError(f"Unknown course type: {course_type_key}")
    return adapters[course_type_key]


def course_type_choices():
    return [(k, a.label) for k, a in get_registered_adapters().items()]
