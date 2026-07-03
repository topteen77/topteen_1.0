from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from course_mindmap.constants import DEBUG_COMMANDS
from course_mindmap.help_content import SIDEBAR_HELP_SECTIONS

register = template.Library()


@register.simple_tag
def course_mindmap_sidebar_help_body():
    parts = []

    generate_url = reverse("admin:course_mindmap_generate")
    generations_url = reverse("admin:course_mindmap_coursemindmapgeneration_changelist")
    config_url = reverse("admin:course_mindmap_coursemindmapconfig_changelist")

    parts.append(
        format_html(
            '<p class="cmm-help-intro">Quick links: '
            '<a href="{}">Generate</a> · '
            '<a href="{}">Generations</a> · '
            '<a href="{}">Configurations</a></p>',
            generate_url,
            generations_url,
            config_url,
        )
    )

    for section in SIDEBAR_HELP_SECTIONS:
        steps_html = "".join(f"<li>{s}</li>" for s in section["steps"])
        parts.append(
            format_html(
                '<section class="cmm-help-section" id="cmm-help-{}">'
                "<h4>{}</h4><ol>{}</ol></section>",
                section["id"],
                section["title"],
                mark_safe(steps_html),
            )
        )

    cmds = "".join(
        format_html(
            "<li><strong>{}</strong><pre class=\"cmm-debug-cmd\">{}</pre></li>",
            c["title"],
            c["command"],
        )
        for c in DEBUG_COMMANDS
    )
    parts.append(
        format_html(
            '<section class="cmm-help-section" id="cmm-help-debug">'
            "<h4>Debugging terminal commands</h4><ul class=\"cmm-debug-list\">{}</ul>"
            "<p class=\"help\">Mindmaps are stored in <code>CourseMindmapData</code> (database) for fast reads.</p>"
            "</section>",
            mark_safe(cmds),
        )
    )

    return mark_safe("".join(str(p) for p in parts))
