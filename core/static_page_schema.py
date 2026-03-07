"""
Schema for static page JSON content. Each url_key can have a list of fields;
the edit form is generated from this and values are stored in StaticPage.content_json.
Frontend uses content_json to render the page.

Field types: text, textarea, richtext, image
"""
# url_key -> list of { "id", "type", "label", "placeholder" (optional), "default" (optional) }
STATIC_PAGE_JSON_SCHEMA = {
    "about": [
        {"id": "highlighter_text", "type": "text", "label": "Highlighter text (above header)", "placeholder": "e.g. Shaping Future Careers", "default": "Shaping Future Careers"},
        {"id": "title", "type": "text", "label": "Main heading", "placeholder": "e.g. About TopTeen!", "default": "About TopTeen!"},
        {"id": "subtitle", "type": "text", "label": "Subheading", "placeholder": "e.g. Empowering Future Careers!", "default": "Empowering Future Careers!"},
        {"id": "hero_body", "type": "richtext", "label": "Hero paragraph", "default": "<p>Welcome to TopTeen...</p>"},
        {"id": "hero_image", "type": "image", "label": "Hero image (right side)"},
        {"id": "section_1_title", "type": "text", "label": "Section 1 title", "default": "Empowering Choices, Enabling Futures"},
        {"id": "section_1_content", "type": "richtext", "label": "Section 1 content"},
        {"id": "section_2_title", "type": "text", "label": "Section 2 title", "default": "Harnessing Canam's Legacy"},
        {"id": "section_2_content", "type": "richtext", "label": "Section 2 content"},
        {"id": "section_3_title", "type": "text", "label": "Section 3 title", "default": "A Symphony of Comprehensive Services"},
        {"id": "section_3_content", "type": "richtext", "label": "Section 3 content"},
    ],
    "privacy": [
        {"id": "title", "type": "text", "label": "Page title", "placeholder": "Privacy Policy"},
        {"id": "body", "type": "richtext", "label": "Body content"},
    ],
    "terms": [
        {"id": "title", "type": "text", "label": "Page title", "placeholder": "Terms & Conditions"},
        {"id": "body", "type": "richtext", "label": "Body content"},
    ],
    "contact": [
        {"id": "title", "type": "text", "label": "Page title", "placeholder": "Contact Us"},
        {"id": "intro", "type": "textarea", "label": "Intro text"},
    ],
}


def get_static_page_schema(url_key):
    """Return the JSON schema for url_key, or None if not defined."""
    return STATIC_PAGE_JSON_SCHEMA.get(url_key)


def get_form_fields_with_values(schema, content_json):
    """Return list of dicts: [{"field": schema_field, "value": value}, ...]."""
    if not schema:
        return []
    content = content_json or {}
    return [
        {"field": f, "value": content.get(f.get("id")) or f.get("default") or ""}
        for f in schema
    ]


def get_static_pages_with_json_schema():
    """Return list of url_keys that have a JSON schema."""
    return list(STATIC_PAGE_JSON_SCHEMA.keys())
