from django import forms

from core import choices
from course_mindmap.registry import course_type_choices


class MindmapGenerateForm(forms.Form):
    course_type_key = forms.ChoiceField(
        label="Course type",
        choices=[],
        widget=forms.Select(attrs={"class": "vTextField", "id": "id_course_type_key"}),
    )
    course_id = forms.ChoiceField(
        label="Course",
        choices=[],
        widget=forms.Select(attrs={"class": "vTextField", "id": "id_course_id"}),
    )
    map_type = forms.ChoiceField(
        label="Map type",
        choices=choices.COURSE_MINDMAP_CONFIG_CHOICES,
        required=False,
        help_text="Leave default to use site DEFAULT_course_MINDMAP_TYPE.",
        widget=forms.Select(attrs={"class": "vTextField"}),
    )

    def __init__(self, *args, **kwargs):
        course_type_key = kwargs.pop("initial_course_type_key", None)
        super().__init__(*args, **kwargs)
        self.fields["course_type_key"].choices = [("", "— Select —")] + course_type_choices()
        self.fields["course_id"].choices = [("", "— Select course type first —")]
        if course_type_key:
            self._populate_courses(course_type_key)

    def _populate_courses(self, course_type_key: str):
        from course_mindmap.registry import get_adapter

        try:
            adapter = get_adapter(course_type_key)
            opts = [
                (c.pk, adapter.get_course_display_name(c))
                for c in adapter.get_course_queryset()[:500]
            ]
            self.fields["course_id"].choices = [("", "— Select —")] + opts
        except Exception:
            self.fields["course_id"].choices = [("", "— Unavailable —")]
