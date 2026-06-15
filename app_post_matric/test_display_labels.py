"""Student-facing test titles for the post-matric (+2) dashboard and reports."""

TEST_DISPLAY_TITLES = {
    'Career Interest Inventory': 'Career Interest Assessment',
}


def test_display_title(title):
    raw = str(title or '').strip()
    return TEST_DISPLAY_TITLES.get(raw, raw)
