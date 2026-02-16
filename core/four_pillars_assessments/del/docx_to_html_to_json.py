"""
Two-step conversion: DOCX → HTML (with proper formatting) → JSON.

Step 1: Convert DOCX to HTML preserving structure (headings, bold, lists).
Step 2: Parse HTML to extract questions and scoring guide into the required JSON format.

Run from project root:
  python -m core.four_pillars_assessments.docx_to_html_to_json

Outputs: for each assessment, {slug}.html and {slug}.json in the same package directory.
"""
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

try:
    from docx import Document
except ImportError:
    print("Install python-docx: pip install python-docx")
    raise

ASSESSMENTS_DIR = Path("/home/itpc6/Public/share/content- Topteen/The Four Pillars Learning Framework/assessments")
OUT_DIR = Path(__file__).resolve().parent

FILES = [
    ("Learning Preferences Assessment questions.docx", "learning_preferences", "Learning Preferences"),
    ("Natural Abilities Assessment Questions.docx", "natural_abilities", "Natural Abilities"),
    ("Engagement Patterns assessment.docx", "engagement_patterns", "Engagement Patterns"),
    ("Interest Drivers assessment.docx", "interest_drivers", "Interest Drivers"),
]

DEFAULT_PROFILES = {
    "learning_preferences": {
        "A": {"name": "Scholarly Learner (Theoretical/Reading-focused)", "summary": "You learn best through deep reading, research, and careful analysis. Quiet study spaces, detailed notes, and comprehensive understanding are your strengths."},
        "B": {"name": "Experiential Learner (Kinesthetic/Hands-on)", "summary": "You learn best by doing. Hands-on activities, real-world applications, and experimentation help you understand and remember information."},
        "C": {"name": "Social Learner (Auditory/Collaborative)", "summary": "You learn best through discussion, collaboration, and verbal processing. Study groups, conversations, and teaching others help ideas stick."},
        "D": {"name": "Structured Learner (Visual/Organized)", "summary": "You learn best with clear structure, visual organization, and step-by-step guidance. Plans, checklists, and visual tools support your success."},
    },
    "natural_abilities": {
        "A": {"name": "Analytical & Technical", "summary": "You excel at pattern recognition, logical analysis, and systematic problem-solving. You naturally break down complexity and find structure."},
        "B": {"name": "Practical & Applied", "summary": "You thrive when completing concrete tasks and seeing tangible results. You are motivated by getting things done and real-world impact."},
        "C": {"name": "Communication & Interpersonal", "summary": "You naturally connect with others, ask probing questions, and communicate ideas clearly. You learn and contribute through dialogue."},
        "D": {"name": "Creative & Innovative", "summary": "You are drawn to new ideas, creative solutions, and exploring possibilities. You think in terms of what could be rather than only what is."},
    },
    "engagement_patterns": {
        "A": {"name": "Goal-Oriented Achiever", "summary": "You are energized by clear goals, measurable progress, and achieving specific outcomes. You like steady progress and milestones."},
        "B": {"name": "Hands-On Creator", "summary": "You are motivated by building, creating, and making things. You prefer learning by doing and seeing tangible results."},
        "C": {"name": "Knowledge Seeker", "summary": "You are driven by understanding concepts deeply and exploring ideas. You value insight and mastery of subject matter."},
        "D": {"name": "Balanced Innovator", "summary": "You combine theory and practice. You like both understanding why and applying how, with flexibility in your approach."},
    },
    "interest_drivers": {
        "A": {"name": "Analytical & Research-Focused", "summary": "You are drawn to data, facts, research, and logical analysis. You want to understand evidence and how conclusions are reached."},
        "B": {"name": "Practical & Systems-Focused", "summary": "You are interested in how things work, technical details, and practical applications. You like solving real problems."},
        "C": {"name": "People & Experience-Focused", "summary": "You are curious about people, stories, and human experience. You engage with ideas through conversation and narrative."},
        "D": {"name": "Creative & Big-Picture Focused", "summary": "You are drawn to creative expression, trends, and broader implications. You like connecting ideas and seeing the bigger picture."},
    },
}

CANONICAL_SCORING_GUIDE_LEARNING_PREFERENCES = {
    "intro": "Scoring Guide: Count your responses for each letter:",
    "A": {"heading": "Mostly A's: Scholarly Learner (Theoretical/Reading-focused)", "items": ["Prefers deep reading and research", "Thrives with written materials and quiet study", "Values thorough understanding and academic rigor", "Learns best through comprehensive analysis and reflection"]},
    "B": {"heading": "Mostly B's: Experiential Learner (Kinesthetic/Hands-on)", "items": ["Learns best through hands-on experience and experimentation", "Prefers active, practical applications over theory", "Motivated by real-world connections and immediate application", "Thrives in dynamic, interactive learning environments"]},
    "C": {"heading": "Mostly C's: Social Learner (Auditory/Collaborative)", "items": ["Learns through discussion, collaboration, and verbal processing", "Values different perspectives and group interactions", "Motivated by interpersonal connections and shared learning", "Processes information best through talking and listening"]},
    "D": {"heading": "Mostly D's: Structured Learner (Visual/Organized)", "items": ["Prefers organized, systematic approaches to learning", "Values clear guidance, visual aids, and measurable progress", "Thrives with balanced, methodical learning processes", "Learns best with clear structure and visual organization"]},
    "mixed_results": "Mixed Results: Many learners have a combination of preferences. Look at your top two categories to understand your primary and secondary learning styles.",
}


# --- Step 1: DOCX to HTML with proper formatting ---

def _is_list_paragraph(para) -> bool:
    try:
        name = (para.style and para.style.name) or ""
        if name and ("List" in name or "Bullet" in name):
            return True
    except Exception:
        pass
    try:
        pPr = para._element.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr")
        if pPr is not None and pPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr") is not None:
            return True
    except Exception:
        pass
    return False


def _render_paragraph_to_html(para, title: str) -> str:
    """Render one paragraph to HTML: bold via <strong>, escape text. Returns tag + content (e.g. <p>...</p> or <li>...</li>)."""
    parts = []
    for run in para.runs:
        text = (run.text or "").replace("\n", " ")
        if not text:
            continue
        escaped = html.escape(text)
        if getattr(run, "bold", False):
            parts.append(f"<strong>{escaped}</strong>")
        else:
            parts.append(escaped)
    content = "".join(parts).strip()
    plain = (para.text or "").strip()  # use plain text for heading detection
    if not content:
        return ""
    if _is_list_paragraph(para):
        return f"<li>{content}</li>"
    # Heuristic: use plain text (no HTML) to detect headings
    if re.match(r"^(Question\s+\d+|Mostly\s+[A-D]'?s\s*:?|Mixed\s+Results|Scoring\s+Guide|Count your responses|Step\s+[12]:)", plain, re.I):
        return f"<h3>{content}</h3>"
    if re.match(r"^[A-D]\s*[).]\s+", plain):
        return f"<h3>{content}</h3>"
    return f"<p>{content}</p>"


def docx_to_html(doc_path: Path, out_html_path: Path, title: str = "Assessment") -> None:
    """Convert a DOCX file to well-formed HTML with proper structure (headings, bold, lists)."""
    doc = Document(doc_path)
    body_parts = [f'<h1>{html.escape(title)}</h1>', "<div class=\"content\">"]
    in_list = False
    for para in doc.paragraphs:
        html_bit = _render_paragraph_to_html(para, title)
        if not html_bit:
            continue
        if html_bit.startswith("<li>"):
            if not in_list:
                body_parts.append("<ul>")
                in_list = True
            body_parts.append(html_bit)
        else:
            if in_list:
                body_parts.append("</ul>")
                in_list = False
            body_parts.append(html_bit)
    if in_list:
        body_parts.append("</ul>")
    body_parts.append("</div>")
    html_content = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>{html.escape(title)}</title>\n"
        "<style>body{font-family:system-ui,sans-serif;line-height:1.5;max-width:720px;margin:0 auto;padding:1rem;} h1{font-size:1.5rem;} h3{font-size:1.1rem;margin-top:1rem;} ul{margin:0.25rem 0;} li{margin:0.25rem 0;}</style>\n"
        "</head>\n<body>\n" + "\n".join(body_parts) + "\n</body>\n</html>"
    )
    out_html_path.parent.mkdir(parents=True, exist_ok=True)
    out_html_path.write_text(html_content, encoding="utf-8")


# --- Step 2: HTML to JSON ---

def _strip_html(raw: str) -> str:
    """Remove HTML tags and decode entities to get plain text."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


class _AssessmentHTMLParser(HTMLParser):
    """Collects text from elements into a flat list of (tag, text) for later parsing."""

    def __init__(self):
        super().__init__()
        self.items = []  # list of ("h3"|"p"|"li", text)
        self._current_tag = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "p", "li"):
            self._current_tag = tag
            self._current_text = []
        # do not reset _current_tag for inline tags (strong, em, span) so their text is collected

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "p", "li"):
            if self._current_tag and self._current_text:
                text = " ".join(self._current_text).strip()
                if text:
                    out_tag = "h3" if self._current_tag in ("h1", "h2", "h3") else self._current_tag
                    self.items.append((out_tag, text))
            self._current_tag = None
            self._current_text = []

    def handle_data(self, data):
        text = data.strip()
        if text and self._current_tag:
            self._current_text.append(text)


def _parse_options_line(line: str) -> dict:
    """Parse 'A) ... B) ... C) ... D) ...' into { A: ..., B: ..., C: ..., D: ... }."""
    line = line.replace("\n", " ").strip()
    parts = re.split(r"\s+(?=B\))\s*", line, maxsplit=1)
    a_text = parts[0].strip()
    if a_text.startswith("A)"):
        a_text = a_text[2:].strip()
    rest = parts[1] if len(parts) > 1 else ""
    parts = re.split(r"\s+(?=C\))\s*", rest, maxsplit=1)
    b_text = parts[0].strip()
    if b_text.startswith("B)"):
        b_text = b_text[2:].strip()
    rest = parts[1] if len(parts) > 1 else ""
    parts = re.split(r"\s+(?=D\))\s*", rest, maxsplit=1)
    c_text = parts[0].strip()
    if c_text.startswith("C)"):
        c_text = c_text[2:].strip()
    d_text = parts[1].strip() if len(parts) > 1 else ""
    if d_text.startswith("D)"):
        d_text = d_text[2:].strip()
    return {"A": a_text, "B": b_text, "C": c_text, "D": d_text}


RE_HEADING_A = re.compile(r"^\s*(?:Mostly\s+A'?s\s*:?|A\s*[).])", re.I)
RE_HEADING_B = re.compile(r"^\s*(?:Mostly\s+B'?s\s*:?|B\s*[).])", re.I)
RE_HEADING_C = re.compile(r"^\s*(?:Mostly\s+C'?s\s*:?|C\s*[).])", re.I)
RE_HEADING_D = re.compile(r"^\s*(?:Mostly\s+D'?s\s*:?|D\s*[).])", re.I)
RE_MIXED = re.compile(r"^\s*(?:Mixed\s+Results|Dual\s+|Balanced\s*:?|Multi[- ]?(?:Modal|Domain))", re.I)
SCORING_INTRO_TRIGGERS = ("Scoring Guide", "Count your responses", "Step 1: Count", "Step 2:")


def html_to_json(html_path: Path, slug: str) -> dict:
    """
    Parse the generated HTML and build the assessment JSON: questions, profiles (with scoring_heading/scoring_bullets), scoring_intro, mixed_results.
    """
    raw = html_path.read_text(encoding="utf-8")
    parser = _AssessmentHTMLParser()
    parser.feed(raw)
    items = parser.items

    # Build list of text blocks (merge contiguous text for options line)
    blocks = []
    i = 0
    while i < len(items):
        tag, text = items[i]
        if tag == "li" and blocks and blocks[-1][0] == "li":
            blocks.append(("li", text))
        else:
            blocks.append((tag, text))
        i += 1

    questions = []
    scoring = {"intro": "", "A": {"heading": "", "items": []}, "B": {"heading": "", "items": []}, "C": {"heading": "", "items": []}, "D": {"heading": "", "items": []}, "mixed_results": ""}
    i = 0
    while i < len(blocks):
        tag, text = blocks[i]
        # Questions: (h3 or p) "Question N", then one or more p (question text), then (h3 or p) with "A) ... B) ... C) ... D)"
        is_question_title = (tag in ("h3", "p")) and re.match(r"^Question\s+\d+", text, re.I)
        if is_question_title:
            title = text
            # Collect all consecutive <p> as question text, then find next block that looks like options (contains A) and B))
            j = i + 1
            text_parts = []
            while j < len(blocks) and blocks[j][0] == "p":
                text_parts.append(blocks[j][1])
                j += 1
            text_para = " ".join(text_parts).strip() if text_parts else ""
            options_line = ""
            if j < len(blocks):
                next_tag, next_text = blocks[j]
                if next_tag in ("h3", "p") and "A)" in next_text and "B)" in next_text:
                    options_line = next_text
            if options_line:
                try:
                    options = _parse_options_line(options_line)
                    questions.append({"title": title, "text": text_para, "options": options})
                except Exception:
                    pass
                i = j + 1
                continue
            i += 1
            continue

        # Scoring section
        if any(t in text for t in SCORING_INTRO_TRIGGERS):
            scoring["intro"] = text
            if i + 1 < len(blocks) and blocks[i + 1][0] == "p" and any(x in blocks[i + 1][1] for x in ("Step 2:", "Count your responses")):
                scoring["intro"] += " " + blocks[i + 1][1]
                i += 1
            i += 1
            continue

        def _is_next_heading(idx):
            if idx >= len(blocks):
                return True
            t = blocks[idx][1]
            return bool(RE_HEADING_A.search(t) or RE_HEADING_B.search(t) or RE_HEADING_C.search(t) or RE_HEADING_D.search(t) or RE_MIXED.search(t))

        if RE_HEADING_A.search(text):
            scoring["A"]["heading"] = text
            i += 1
            while i < len(blocks) and not _is_next_heading(i):
                if blocks[i][0] in ("li", "p"):
                    scoring["A"]["items"].append(blocks[i][1])
                i += 1
            continue
        if RE_HEADING_B.search(text):
            scoring["B"]["heading"] = text
            i += 1
            while i < len(blocks) and not _is_next_heading(i):
                if blocks[i][0] in ("li", "p"):
                    scoring["B"]["items"].append(blocks[i][1])
                i += 1
            continue
        if RE_HEADING_C.search(text):
            scoring["C"]["heading"] = text
            i += 1
            while i < len(blocks) and not _is_next_heading(i):
                if blocks[i][0] in ("li", "p"):
                    scoring["C"]["items"].append(blocks[i][1])
                i += 1
            continue
        if RE_HEADING_D.search(text):
            scoring["D"]["heading"] = text
            i += 1
            while i < len(blocks) and not _is_next_heading(i):
                if blocks[i][0] in ("li", "p"):
                    scoring["D"]["items"].append(blocks[i][1])
                i += 1
            continue
        if RE_MIXED.search(text):
            scoring["mixed_results"] = text
            if i + 1 < len(blocks) and blocks[i + 1][0] == "p" and not RE_HEADING_A.search(blocks[i + 1][1]):
                scoring["mixed_results"] += " " + blocks[i + 1][1]
                i += 1
            i += 1
            continue
        i += 1

    # Build output JSON
    base = DEFAULT_PROFILES.get(slug, DEFAULT_PROFILES["learning_preferences"])
    profiles = {k: dict(v) for k, v in base.items()}
    if slug == "learning_preferences":
        scoring = dict(CANONICAL_SCORING_GUIDE_LEARNING_PREFERENCES)
    for key in ("A", "B", "C", "D"):
        if scoring.get(key, {}).get("heading"):
            profiles[key]["scoring_heading"] = scoring[key]["heading"]
        items_list = scoring.get(key, {}).get("items") or []
        if items_list:
            profiles[key]["scoring_bullets"] = items_list
    data = {"questions": questions, "profiles": profiles}
    if scoring.get("intro"):
        data["scoring_intro"] = scoring["intro"]
    if scoring.get("mixed_results"):
        data["mixed_results"] = scoring["mixed_results"]
    return data


def main():
    if not ASSESSMENTS_DIR.exists():
        print("Assessments dir not found:", ASSESSMENTS_DIR)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, slug, title in FILES:
        path = ASSESSMENTS_DIR / filename
        if not path.exists():
            print("Skip (not found):", filename)
            continue
        html_path = OUT_DIR / f"{slug}.html"
        json_path = OUT_DIR / f"{slug}.json"
        print("Step 1: DOCX → HTML", html_path.name)
        docx_to_html(path, html_path, title=title)
        print("Step 2: HTML → JSON", json_path.name)
        data = html_to_json(html_path, slug)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Wrote", json_path, "with", len(data.get("questions", [])), "questions")
    print("Done.")


if __name__ == "__main__":
    main()
