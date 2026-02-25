import re
from django.utils.html import strip_tags

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


def extract_intro_html_from_description(html):
    """
    Extract a single introduction paragraph from description: the first <p> only.
    Keeps paragraph formatting; no h2. Returns HTML string, or empty string if no <p>.
    """
    if not html or not html.strip():
        return ""
    if BeautifulSoup is None:
        # Fallback: take content before first h2 and strip to first <p> with regex
        match = re.search(r'<\s*p\b[^>]*>.*?<\s*/\s*p\s*>', html, re.IGNORECASE | re.DOTALL)
        return match.group(0) if match else ""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for p in soup.find_all('p'):
            if p.get_text(strip=True):
                return str(p)
    except Exception:
        pass
    return ""


def extract_summary_from_description(html, max_chars=8000):
    """
    Extract summary text from description HTML at runtime.
    Takes all content before the first <h2> or <h3>; if no heading, uses full text (capped).
    Returns plain text, stripped of HTML and normalized whitespace.
    """
    if not html or not html.strip():
        return ""
    match = re.search(r'<\s*h[23]\b', html, re.IGNORECASE)
    if match:
        html_before_heading = html[: match.start()]
    else:
        html_before_heading = html
    text = strip_tags(html_before_heading)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3] + '...'
    return text


def career_media_directory(instance, filename):
    return 'upload/career/media/{0}/{1}'.format(instance.id, filename)

def get_formated_currency(amount,country_code=91):
    return "{sal}LPA".format(sal=(round(int(amount)/100000,2)))

def career_cluster_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/career/careercluster/{0}'.format(filename)


def career_track_icon_directory(instance, filename):
    """Upload path for home page scroller career track icons."""
    return 'upload/career/career_track_icons/{0}'.format(filename)