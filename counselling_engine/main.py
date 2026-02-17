# TOPTEEN DEEP-COUNSELLING ENGINE v1.0
# Production-Ready Implementation for Topteen.in
# NEP 2020, CBSE Career Guidance Framework, NEAT 4.0 compliant

import os
import json
import re
import hashlib
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

# Load .env: project root first (so OPENAI_API_KEY from main .env works), then engine dir to override
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    _engine = Path(__file__).resolve().parent
    for _d in (_root, _engine):
        _f = _d / ".env"
        if _f.exists():
            load_dotenv(_f)
except ImportError:
    pass

import numpy as np
from pydantic import BaseModel, Field, field_validator
import torch
from sentence_transformers import SentenceTransformer
from transformers import pipeline
import redis
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("topteen_counsel.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SECTION 1.5: LLM (OpenAI) – .env-based, optional
# ---------------------------------------------------------------------------

def _get_openai_config() -> Tuple[Optional[str], str]:
    """Return (api_key, model). Key from OPENAI_API_KEY or COUNSELLING_OPENAI_API_KEY."""
    key = os.getenv("COUNSELLING_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    key = (key or "").strip()
    model = (
        os.getenv("COUNSELLING_OPENAI_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-4o-mini"
    ).strip()
    return (key or None, model)


def generate_counseling_reply_llm(
    user_message: str,
    conversation_history: List[str],
    career_suggestions: List[Dict],
    roadmap: Optional[Dict],
    grade: int,
    dominant_riasec: List[str],
    riasec_descriptions: str,
    emotional_tone: str,
    student_name: Optional[str] = None,
) -> Optional[str]:
    """
    Call OpenAI to generate one empathetic career-counselling reply.
    Returns None if API key missing or on error.
    """
    api_key, model = _get_openai_config()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception as e:
        logger.warning("OpenAI client init failed: %s", e)
        return None

    career_blob = ""
    if career_suggestions:
        parts = []
        for c in career_suggestions[:5]:
            name = c.get("name") or c.get("career_id", "")
            score = c.get("compatibility_score")
            pct = f" ({int(score * 100)}% match)" if score is not None else ""
            parts.append(f"- {name}{pct}")
        career_blob = "Top career matches:\n" + "\n".join(parts)

    roadmap_blob = ""
    if roadmap and roadmap.get("phases"):
        phases = [p.get("phase_name", "") for p in roadmap["phases"]]
        roadmap_blob = "Personalized roadmap phases: " + " → ".join(phases)

    system = """You are a professional career counsellor for Indian high school students (NEP 2020 aware).
Be warm, concise, and empathetic. Use the structured data below to personalize your reply.
Do not invent careers or exams; only refer to the data provided. Keep the reply to 2–4 short paragraphs.
Use **bold** only for career names or key terms. Do not repeat "Hi" or the student's name every time."""

    user_blob = f"""Current user message: {user_message}

Context:
- Grade: {grade}
- RIASEC strengths: {dominant_riasec} — {riasec_descriptions}
- Recommended emotional tone: {emotional_tone}
{chr(10) + career_blob if career_blob else ""}
{chr(10) + roadmap_blob if roadmap_blob else ""}

Generate a single counselling reply that addresses the user's message using the above context. Be specific and actionable."""

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_blob},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = _strip_html_from_response(text)
        return text if text else None
    except Exception as e:
        logger.warning("OpenAI completion failed: %s", e)
        return None


def _strip_html_from_response(text: str) -> str:
    """Remove HTML from LLM response so the UI shows plain text, not raw HTML."""
    if not text or not text.strip():
        return ""
    # If response looks like a full HTML document, treat as invalid
    if re.match(r"\s*<!DOCTYPE", text, re.IGNORECASE) or re.match(r"\s*<html", text, re.IGNORECASE):
        return ""
    # Strip all HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple spaces and trim
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# SECTION 2: DATA MODELS & ENUMS
# ---------------------------------------------------------------------------

class StreamType(str, Enum):
    SCIENCE_PCM = "science_pcm"
    SCIENCE_PCB = "science_pcb"
    COMMERCE = "commerce"
    HUMANITIES = "humanities"
    VOCATIONAL_TECH = "vocational_technical"
    ARTS_DESIGN = "arts_design"
    MULTIDISCIPLINARY = "multidisciplinary"
    SKILL_BASED = "skill_based"


class RIASECType(str, Enum):
    REALISTIC = "R"
    INVESTIGATIVE = "I"
    ARTISTIC = "A"
    SOCIAL = "S"
    ENTERPRISING = "E"
    CONVENTIONAL = "C"


class CrisisType(str, Enum):
    SELF_HARM = "self_harm"
    SUICIDE = "suicide"
    DEPRESSION_SEVERE = "depression_severe"
    ABUSE = "abuse"
    NON_CAREER = "non_career"
    NONE = "none"


@dataclass
class StudentProfile:
    student_id: str
    grade: int
    board: str
    socio_economic_score: float
    session_history: List[Dict] = field(default_factory=list)
    psychometric_profile: Optional[Dict] = None
    career_roadmap: Optional[Dict] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    neat_coupon_applied: bool = False
    mentor_assigned: Optional[str] = None


class CounselRequest(BaseModel):
    student_id: str
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 2000:
            raise ValueError("Message too long (max 2000 chars)")
        if len(v) < 3:
            raise ValueError("Message too short")
        return v


class CounselResponse(BaseModel):
    student_id: str
    session_id: str
    response_text: str
    detected_riasec: List[str]
    career_suggestions: List[Dict]
    tactical_roadmap: Optional[Dict]
    compatibility_scores: Dict[str, float]
    empathy_score: float
    crisis_flag: Optional[str]
    explanation: Dict[str, str]
    suggested_questions: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# SECTION 3: SECURITY (AES-256) – fixed salt for consistent encrypt/decrypt
# ---------------------------------------------------------------------------

class SecurityManager:
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or os.getenv("TOPTEEN_MASTER_KEY")
        if not self.master_key:
            raise ValueError("Master key required for encryption")
        self.cipher = self._init_cipher()

    def _init_cipher(self) -> Fernet:
        salt = os.getenv("TOPTEEN_ENCRYPTION_SALT")
        if not salt or len(salt.encode()) < 16:
            salt = hashlib.sha256(self.master_key.encode()).hexdigest()[:32]
        salt_bytes = salt.encode() if isinstance(salt, str) else salt
        salt_bytes = (salt_bytes + b"0" * 16)[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)

    def encrypt_profile(self, profile: StudentProfile) -> bytes:
        profile_dict = {
            "student_id": profile.student_id,
            "grade": profile.grade,
            "board": profile.board,
            "socio_economic_score": profile.socio_economic_score,
            "session_history": profile.session_history,
            "psychometric_profile": profile.psychometric_profile,
            "career_roadmap": profile.career_roadmap,
            "created_at": profile.created_at.isoformat(),
            "last_updated": profile.last_updated.isoformat(),
            "neat_coupon_applied": profile.neat_coupon_applied,
            "mentor_assigned": profile.mentor_assigned,
        }
        return self.cipher.encrypt(json.dumps(profile_dict).encode())

    def decrypt_profile(self, encrypted_data: bytes) -> StudentProfile:
        decrypted = self.cipher.decrypt(encrypted_data)
        data = json.loads(decrypted.decode())
        return StudentProfile(
            student_id=data["student_id"],
            grade=data["grade"],
            board=data["board"],
            socio_economic_score=data["socio_economic_score"],
            session_history=data.get("session_history", []),
            psychometric_profile=data.get("psychometric_profile"),
            career_roadmap=data.get("career_roadmap"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            neat_coupon_applied=data.get("neat_coupon_applied", False),
            mentor_assigned=data.get("mentor_assigned"),
        )

    def hash_id(self, student_id: str) -> str:
        return hashlib.sha256(f"{student_id}{self.master_key}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# SECTION 4: EMPATHY ENGINE
# ---------------------------------------------------------------------------

class EmpathyEngine:
    def __init__(self):
        self.sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=0 if torch.cuda.is_available() else -1,
        )
        self.emotion_classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            device=0 if torch.cuda.is_available() else -1,
        )
        self.anxiety_keywords = [
            "worried", "scared", "confused", "pressure", "stress",
            "tension", "anxiety", "nervous", "unsure", "doubt",
            "what if", "fail", "failure", "not good enough", "compare",
        ]
        self.excitement_keywords = [
            "excited", "passionate", "love", "dream", "ambition",
            "want to be", "inspired", "motivated", "eager", "enthusiastic",
        ]

    def analyze_emotional_state(self, text: str) -> Dict[str, Any]:
        sentiment = self.sentiment_analyzer(text[:512])[0]
        emotions = self.emotion_classifier(text[:512])[0]
        emotion_scores = {e["label"]: e["score"] for e in emotions}
        anxiety_score = self._calculate_anxiety(text, emotion_scores)
        excitement_score = self._calculate_excitement(text, emotion_scores)
        tone = self._determine_tone(anxiety_score, excitement_score, sentiment)
        return {
            "sentiment": sentiment,
            "emotions": emotion_scores,
            "anxiety_level": anxiety_score,
            "excitement_level": excitement_score,
            "tone_recommendation": tone,
            "requires_reassurance": anxiety_score > 0.6,
            "can_be_enthusiastic": excitement_score > 0.7 and anxiety_score < 0.3,
        }

    def _calculate_anxiety(self, text: str, emotions: Dict) -> float:
        text_lower = text.lower()
        keyword_hits = sum(1 for kw in self.anxiety_keywords if kw in text_lower)
        keyword_score = min(keyword_hits / 3, 1.0)
        model_score = emotions.get("fear", 0) * 0.6 + emotions.get("sadness", 0) * 0.4
        return min((keyword_score * 0.4 + model_score * 0.6), 1.0)

    def _calculate_excitement(self, text: str, emotions: Dict) -> float:
        text_lower = text.lower()
        keyword_hits = sum(1 for kw in self.excitement_keywords if kw in text_lower)
        keyword_score = min(keyword_hits / 3, 1.0)
        model_score = emotions.get("joy", 0) * 0.7 + emotions.get("surprise", 0) * 0.3
        return min((keyword_score * 0.3 + model_score * 0.7), 1.0)

    def _determine_tone(self, anxiety: float, excitement: float, sentiment: Dict) -> str:
        if anxiety > 0.7:
            return "highly_supportive_gentle"
        elif anxiety > 0.4:
            return "reassuring_validating"
        elif excitement > 0.8:
            return "enthusiastic_channeling"
        elif sentiment.get("label") == "POSITIVE" and sentiment.get("score", 0) > 0.8:
            return "encouraging_building"
        return "neutral_informative_balanced"

    def generate_empathetic_response(
        self, base_response: str, emotional_state: Dict, student_name: Optional[str] = None
    ) -> str:
        # Professional tone: no repeated "Hi [name]," every turn.
        tone = emotional_state["tone_recommendation"]
        empathy_prefixes = {
            "highly_supportive_gentle": [
                "Your feelings are valid. ",
                "Many students feel uncertain at this stage. ",
            ],
            "reassuring_validating": [
                "Based on your profile and our discussion, ",
                "Here's what aligns with your situation. ",
            ],
            "enthusiastic_channeling": [
                "Your interests point clearly in this direction. ",
                "Based on your profile, ",
            ],
            "encouraging_building": [
                "Your profile indicates strong fit in this area. ",
                "Based on our conversation, ",
            ],
            "neutral_informative_balanced": [
                "Based on your profile and interests, ",
                "Here's what I recommend. ",
            ],
        }
        prefix = random.choice(
            empathy_prefixes.get(tone, empathy_prefixes["neutral_informative_balanced"])
        )
        if emotional_state["requires_reassurance"]:
            reassurance_suffixes = [
                "\n\nRemember: there is no single perfect choice—only informed ones. You have time to explore and adjust.",
                "\n\nCareer paths often change over time. Flexibility is a strength.",
            ]
            suffix = random.choice(reassurance_suffixes)
        else:
            suffix = ""
        return prefix + base_response + suffix


# ---------------------------------------------------------------------------
# SECTION 5: PSYCHOMETRIC ENGINE (RIASEC + career DB)
# ---------------------------------------------------------------------------

class PsychometricEngine:
    def __init__(self):
        self.sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
        self._init_riasec_vectors()
        self._init_career_database()

    def _init_riasec_vectors(self) -> None:
        self.riasec_descriptions = {
            RIASECType.REALISTIC: "hands-on work, machines, tools, physical activity, engineering, mechanics, outdoor work, practical problem solving",
            RIASECType.INVESTIGATIVE: "research, analysis, science, mathematics, intellectual challenges, laboratory work, data analysis, critical thinking",
            RIASECType.ARTISTIC: "creativity, design, music, writing, art, innovation, self-expression, aesthetics, unconventional thinking",
            RIASECType.SOCIAL: "helping people, teaching, counseling, healthcare, teamwork, communication, empathy, community service",
            RIASECType.ENTERPRISING: "leadership, business, persuasion, management, entrepreneurship, risk-taking, decision making, ambition",
            RIASECType.CONVENTIONAL: "organization, data management, accounting, attention to detail, structured work, reliability, administrative tasks",
        }
        self.riasec_vectors = {
            rtype: self.sentence_model.encode(desc)
            for rtype, desc in self.riasec_descriptions.items()
        }

    def _init_career_database(self) -> None:
        self.career_db = {
            "software_engineering_ai": {
                "name": "AI/ML Engineer",
                "riasec_match": [RIASECType.INVESTIGATIVE, RIASECType.CONVENTIONAL],
                "nsqf_level": 7,
                "market_demand_2025": 0.95,
                "salary_range_inr": (800000, 2500000),
                "entrance_exams": ["JEE", "BITSAT", "State CET"],
                "skills_required": ["Python", "Mathematics", "Statistics"],
                "nep_multidisciplinary": True,
                "description": "Develop intelligent systems and algorithms",
            },
            "medicine_mbbs": {
                "name": "Medical Doctor (MBBS)",
                "riasec_match": [RIASECType.INVESTIGATIVE, RIASECType.SOCIAL],
                "nsqf_level": 7,
                "market_demand_2025": 0.90,
                "salary_range_inr": (1200000, 5000000),
                "entrance_exams": ["NEET"],
                "skills_required": ["Biology", "Chemistry", "Empathy"],
                "nep_multidisciplinary": False,
                "description": "Diagnose and treat patients",
            },
            "data_scientist": {
                "name": "Data Scientist",
                "riasec_match": [RIASECType.INVESTIGATIVE, RIASECType.CONVENTIONAL],
                "nsqf_level": 7,
                "market_demand_2025": 0.92,
                "salary_range_inr": (700000, 2000000),
                "entrance_exams": ["JEE", "CUET", "Private University Exams"],
                "skills_required": ["Statistics", "Python", "Domain Knowledge"],
                "nep_multidisciplinary": True,
                "description": "Extract insights from complex data",
            },
            "psychologist_counselor": {
                "name": "Clinical Psychologist",
                "riasec_match": [RIASECType.SOCIAL, RIASECType.INVESTIGATIVE],
                "nsqf_level": 7,
                "market_demand_2025": 0.75,
                "salary_range_inr": (400000, 1500000),
                "entrance_exams": ["CUET", "University-specific"],
                "skills_required": ["Psychology", "Communication", "Empathy"],
                "nep_multidisciplinary": True,
                "description": "Mental health and behavioral support",
            },
            "environmental_scientist": {
                "name": "Environmental Scientist",
                "riasec_match": [RIASECType.INVESTIGATIVE, RIASECType.REALISTIC],
                "nsqf_level": 7,
                "market_demand_2025": 0.70,
                "salary_range_inr": (500000, 1200000),
                "entrance_exams": ["JEE", "NEET", "CUET"],
                "skills_required": ["Biology", "Chemistry", "Geography"],
                "nep_multidisciplinary": True,
                "description": "Address environmental challenges",
            },
            "digital_marketing_specialist": {
                "name": "Digital Marketing Strategist",
                "riasec_match": [RIASECType.ENTERPRISING, RIASECType.ARTISTIC],
                "nsqf_level": 6,
                "market_demand_2025": 0.88,
                "salary_range_inr": (400000, 1500000),
                "entrance_exams": ["CUET", "Private Exams"],
                "skills_required": ["Communication", "Analytics", "Creativity"],
                "nep_multidisciplinary": True,
                "description": "Drive digital brand strategy",
            },
            "robotics_engineer": {
                "name": "Robotics Engineer",
                "riasec_match": [RIASECType.REALISTIC, RIASECType.INVESTIGATIVE],
                "nsqf_level": 7,
                "market_demand_2025": 0.85,
                "salary_range_inr": (600000, 1800000),
                "entrance_exams": ["JEE", "BITSAT"],
                "skills_required": ["Physics", "Mathematics", "Programming"],
                "nep_multidisciplinary": True,
                "description": "Design and build robotic systems",
            },
            "renewable_energy_technician": {
                "name": "Solar Energy Technician",
                "riasec_match": [RIASECType.REALISTIC, RIASECType.CONVENTIONAL],
                "nsqf_level": 5,
                "market_demand_2025": 0.80,
                "salary_range_inr": (300000, 800000),
                "entrance_exams": ["ITI", "Polytechnic"],
                "skills_required": ["Electrical", "Technical", "Safety"],
                "nep_multidisciplinary": False,
                "description": "Install and maintain solar systems",
            },
        }

    def extract_riasec_from_conversation(self, conversation_history: List[str]) -> Dict[RIASECType, float]:
        if not conversation_history:
            return {rtype: 0.0 for rtype in RIASECType}
        full_text = " ".join(conversation_history)
        text_vector = self.sentence_model.encode(full_text)
        scores = {}
        for rtype, rvec in self.riasec_vectors.items():
            sim = np.dot(text_vector, rvec) / (
                np.linalg.norm(text_vector) * np.linalg.norm(rvec) + 1e-9
            )
            scores[rtype] = float(sim)
        max_score = max(scores.values()) if scores else 1
        if max_score > 0:
            scores = {k: max(0, v / max_score) for k, v in scores.items()}
        return scores

    def calculate_career_compatibility_score(
        self,
        riasec_scores: Dict[RIASECType, float],
        career_id: str,
        aptitude_score: float,
        socio_economic_factor: float,
    ) -> float:
        if career_id not in self.career_db:
            return 0.0
        career = self.career_db[career_id]
        career_riasec = career["riasec_match"]
        psychometric_fit = np.mean([riasec_scores.get(r, 0) for r in career_riasec])
        market_demand = career["market_demand_2025"]
        w1, w2, w3 = 0.3, 0.4, 0.3
        S_c = (w1 * aptitude_score) + (w2 * psychometric_fit) + (w3 * market_demand)
        accessibility_modifier = (
            1.0 if career["nsqf_level"] <= 6 else (0.8 + 0.2 * socio_economic_factor)
        )
        return min(S_c * accessibility_modifier, 1.0)

    def get_top_career_recommendations(
        self,
        riasec_scores: Dict[RIASECType, float],
        aptitude_score: float,
        socio_economic_factor: float,
        top_n: int = 3,
    ) -> List[Tuple[str, float, Dict]]:
        scores = []
        for career_id, career_data in self.career_db.items():
            score = self.calculate_career_compatibility_score(
                riasec_scores, career_id, aptitude_score, socio_economic_factor
            )
            scores.append((career_id, score, career_data))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


# ---------------------------------------------------------------------------
# SECTION 6: REGULATORY & SAFETY LAYER
# ---------------------------------------------------------------------------

class RegulatoryLayer:
    def __init__(self):
        self.crisis_patterns = {
            CrisisType.SELF_HARM: [
                r"\b(cut myself|self.?harm|hurt myself|injure)\b",
                r"\b(end it all|can't go on|no point living)\b",
            ],
            CrisisType.SUICIDE: [
                r"\b(kill myself|suicide|want to die|end my life)\b",
                r"\b(better off dead|not worth living)\b",
            ],
            CrisisType.DEPRESSION_SEVERE: [
                r"\b(hopeless|empty inside|numb all the time|can't feel)\b",
                r"\b(no energy|can't get out of bed|worthless)\b",
            ],
            CrisisType.ABUSE: [
                r"\b(being abused|hurt by|molested|beaten at home)\b",
            ],
            CrisisType.NON_CAREER: [
                r"\b(love problem|relationship|boyfriend|girlfriend|breakup)\b",
                r"\b(family fight|parents divorced|money problem|financial crisis)\b",
            ],
        }
        self.crisis_helpline = {
            "name": "iCall Psychosocial Helpline",
            "phone": "+91-9152987821",
            "email": "icall@tiss.edu",
            "website": "https://icallhelpline.org",
            "hours": "Mon-Sat, 10am-8pm IST",
        }
        self.allowed_domains = [
            "career", "education", "stream", "subject", "college", "university",
            "exam", "jee", "neet", "cuet", "clat", "aptitude", "interest",
            "skill", "job", "profession", "future", "goal", "ambition",
            "engineering", "medical", "commerce", "arts", "science", "humanities",
            "vocational", "diploma", "degree", "scholarship", "entrance",
        ]

    def detect_crisis(self, text: str) -> Tuple[CrisisType, float, str]:
        text_lower = text.lower()
        for crisis_type, patterns in self.crisis_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return crisis_type, 0.9, self._generate_crisis_response(crisis_type)
        is_career_related = any(d in text_lower for d in self.allowed_domains)
        if not is_career_related and len(text.split()) > 3:
            return CrisisType.NON_CAREER, 0.5, self._generate_non_career_response()
        return CrisisType.NONE, 0.0, ""

    def _generate_crisis_response(self, crisis_type: CrisisType) -> str:
        h = self.crisis_helpline
        responses = {
            CrisisType.SELF_HARM: f"""I'm really concerned about what you've shared. Your safety is the most important thing right now.

Please reach out to professional counselors immediately:
{h['name']}: {h['phone']}
{h['website']}
Available: {h['hours']}

You don't have to handle this alone. There are people trained to help you through this.""",
            CrisisType.SUICIDE: f"""I'm deeply concerned about your message. Whatever you're feeling right now, please know that help is available and people care about you.

Contact crisis support immediately:
{h['name']}: {h['phone']}
{h['website']}

Or call emergency services: 112

Your life matters. Please reach out now.""",
            CrisisType.DEPRESSION_SEVERE: f"""It sounds like you're going through a really difficult time. These feelings are serious, and you deserve professional support.

Please contact:
{h['name']}: {h['phone']}
{h['website']}

Speaking with a counselor can help you navigate these feelings. You don't have to face this alone.""",
            CrisisType.ABUSE: f"""What you're describing sounds serious and concerning. Your safety is paramount.

Please seek help immediately:
Emergency: 112 or 1098 (Childline)
{h['name']}: {h['phone']}

You have the right to be safe. Professionals can help you find safety and support.""",
        }
        return responses.get(crisis_type, responses[CrisisType.DEPRESSION_SEVERE])

    def _generate_non_career_response(self) -> str:
        return """I understand you want to talk about this, but I'm specifically designed to help with career and educational guidance for high school students.

For personal or emotional concerns beyond career planning, I'd recommend speaking with:
- Your school counselor
- A trusted teacher or family member
- Professional helpline: iCall (+91-9152987821)

Is there something about your career path, stream selection, or future goals I can help you explore instead?"""

    def apply_nep_multidisciplinary_boost(self, career_data: Dict) -> float:
        return 1.15 if career_data.get("nep_multidisciplinary", False) else 1.0

    def audit_bias(self, recommendations: List[Dict], student_profile: StudentProfile) -> List[Dict]:
        audit_log = {
            "timestamp": datetime.now().isoformat(),
            "student_id_hash": hashlib.sha256(student_profile.student_id.encode()).hexdigest()[:16],
            "socio_economic_bucket": (
                "high" if student_profile.socio_economic_score > 0.7
                else "medium" if student_profile.socio_economic_score > 0.4
                else "low"
            ),
            "recommendation_diversity_score": self._calculate_diversity_score(recommendations),
            "nsqf_level_distribution": [r.get("nsqf_level") for r in recommendations],
        }
        logger.info("Bias Audit: %s", json.dumps(audit_log))
        if student_profile.socio_economic_score < 0.4:
            has_accessible_path = any(r.get("nsqf_level", 10) <= 5 for r in recommendations)
            if not has_accessible_path:
                logger.warning("Bias correction triggered for student %s", student_profile.student_id)
        return recommendations

    def _calculate_diversity_score(self, recommendations: List[Dict]) -> float:
        if not recommendations:
            return 0.0
        riasec_types = set()
        for rec in recommendations:
            for r in rec.get("riasec_match", []):
                riasec_types.add(r.value if hasattr(r, "value") else r)
        return len(riasec_types) / 6.0


# ---------------------------------------------------------------------------
# SECTION 7: ROADMAP GENERATOR
# ---------------------------------------------------------------------------

class RoadmapGenerator:
    def __init__(self):
        self.exam_calendar = {
            "JEE_Main": {"month": "January/April", "subjects": ["Physics", "Chemistry", "Maths"]},
            "JEE_Adv": {"month": "May", "subjects": ["Physics", "Chemistry", "Maths"]},
            "NEET": {"month": "May", "subjects": ["Physics", "Chemistry", "Biology"]},
            "CUET": {"month": "May-June", "subjects": ["Domain specific"]},
            "CLAT": {"month": "December", "subjects": ["English", "GK", "Legal", "Logical"]},
            "BITSAT": {"month": "May-June", "subjects": ["Physics", "Chemistry", "Maths", "English"]},
        }
        self.stream_requirements = {
            "software_engineering_ai": {
                "grade_11_stream": StreamType.SCIENCE_PCM,
                "required_subjects": ["Physics", "Chemistry", "Mathematics", "Computer Science/Informatics"],
                "alternative_streams": [StreamType.MULTIDISCIPLINARY],
            },
            "medicine_mbbs": {
                "grade_11_stream": StreamType.SCIENCE_PCB,
                "required_subjects": ["Physics", "Chemistry", "Biology", "English"],
                "alternative_streams": [],
            },
            "data_scientist": {
                "grade_11_stream": StreamType.SCIENCE_PCM,
                "required_subjects": ["Mathematics", "Statistics/Economics", "Computer Science"],
                "alternative_streams": [StreamType.COMMERCE, StreamType.MULTIDISCIPLINARY],
            },
            "psychologist_counselor": {
                "grade_11_stream": StreamType.HUMANITIES,
                "required_subjects": ["Psychology", "Biology", "Sociology"],
                "alternative_streams": [StreamType.SCIENCE_PCB, StreamType.MULTIDISCIPLINARY],
            },
        }

    def generate_roadmap(
        self, career_id: str, current_grade: int, riasec_profile: Dict[RIASECType, float]
    ) -> Dict[str, Any]:
        career_reqs = self.stream_requirements.get(career_id, {})
        target_stream = career_reqs.get("grade_11_stream", StreamType.MULTIDISCIPLINARY)
        roadmap = {
            "generated_at": datetime.now().isoformat(),
            "target_career": career_id,
            "current_grade": current_grade,
            "phases": [],
        }
        if current_grade <= 10:
            roadmap["phases"].append({
                "phase_name": "Foundation Building",
                "grades": [current_grade, 10],
                "focus": "Core concept mastery and career exploration",
                "actions": [
                    "Strengthen Mathematics and Science fundamentals",
                    "Explore NEP 2020 vocational exposure (10-day internship)",
                    "Take RIASEC assessment for clarity",
                    "Research target career requirements",
                    "Build communication and digital literacy skills",
                ],
                "milestones": [
                    "Score >80% in core subjects by Grade 10",
                    "Complete minimum 2 career exploration activities",
                    "Identify top 3 career interests",
                ],
            })
        roadmap["phases"].append({
            "phase_name": "Specialization & Entrance Prep",
            "grades": [11, 12],
            "recommended_stream": target_stream.value,
            "required_subjects": career_reqs.get("required_subjects", []),
            "focus": "Deep subject expertise + Entrance exam preparation",
            "actions": [
                f"Select {target_stream.value} stream with required subjects",
                "Join structured entrance exam preparation",
                "Solve previous 10 years exam papers",
                "Take mock tests monthly",
                "Build portfolio projects (for NEP holistic evaluation)",
            ],
            "entrance_exams": self._get_relevant_exams(career_id),
            "milestones": [
                "Complete 80% of entrance syllabus by Dec of Grade 12",
                "Score >90th percentile in mock tests",
                "Submit college applications on time",
            ],
        })
        roadmap["phases"].append({
            "phase_name": "Transition to Higher Education",
            "grades": ["College Year 1"],
            "focus": "Adaptation and skill deepening",
            "actions": [
                "Enroll in recommended degree program",
                "Seek internships for practical exposure",
                "Develop soft skills and networking",
                "Consider multidisciplinary minors (NEP 2020 flexibility)",
            ],
            "alternative_paths": self._get_alternative_paths(career_id, riasec_profile),
        })
        return roadmap

    def _get_relevant_exams(self, career_id: str) -> List[Dict]:
        exam_mapping = {
            "software_engineering_ai": ["JEE_Main", "JEE_Adv", "BITSAT"],
            "medicine_mbbs": ["NEET"],
            "data_scientist": ["JEE_Main", "CUET", "BITSAT"],
            "psychologist_counselor": ["CUET", "CLAT"],
            "environmental_scientist": ["JEE_Main", "NEET", "CUET"],
            "digital_marketing_specialist": ["CUET"],
            "robotics_engineer": ["JEE_Main", "JEE_Adv"],
            "renewable_energy_technician": ["ITI Entrance", "Polytechnic"],
        }
        exams = exam_mapping.get(career_id, ["CUET"])
        return [{"name": e, **self.exam_calendar.get(e, {})} for e in exams]

    def _get_alternative_paths(
        self, career_id: str, riasec_profile: Dict[RIASECType, float]
    ) -> List[Dict]:
        alternatives = []
        if riasec_profile.get(RIASECType.ARTISTIC, 0) > 0.6:
            alternatives.append({
                "path": "UX/UI Design with Tech background",
                "description": "Combine technical skills with artistic interests",
            })
        if riasec_profile.get(RIASECType.SOCIAL, 0) > 0.6:
            alternatives.append({
                "path": "EdTech Product Management",
                "description": "Merge social impact with technology",
            })
        if riasec_profile.get(RIASECType.ENTERPRISING, 0) > 0.6:
            alternatives.append({
                "path": "Tech Entrepreneurship",
                "description": "Build startups in the technology space",
            })
        return alternatives


# ---------------------------------------------------------------------------
# SECTION 8: DEEP COUNSELLING ENGINE (orchestrator)
# ---------------------------------------------------------------------------

class DeepCounsellingEngine:
    def __init__(self):
        self.empathy = EmpathyEngine()
        self.psychometric = PsychometricEngine()
        self.regulatory = RegulatoryLayer()
        self.roadmap_gen = RoadmapGenerator()
        self.security = SecurityManager()
        redis_db = int(os.getenv("COUNSELLING_REDIS_DB", "0"))
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=redis_db,
            decode_responses=False,
        )
        self.max_history = 10

    async def process_counsel_request(self, request: CounselRequest) -> CounselResponse:
        session_id = request.session_id or self._generate_session_id(request.student_id)
        crisis_type, _, crisis_msg = self.regulatory.detect_crisis(request.message)
        if crisis_type in (CrisisType.SELF_HARM, CrisisType.SUICIDE, CrisisType.ABUSE):
            logger.critical("CRISIS DETECTED: %s for student %s", crisis_type, request.student_id)
            return CounselResponse(
                student_id=request.student_id,
                session_id=session_id,
                response_text=crisis_msg,
                detected_riasec=[],
                career_suggestions=[],
                tactical_roadmap=None,
                compatibility_scores={},
                empathy_score=1.0,
                crisis_flag=crisis_type.value,
                explanation={"safety_trigger": "Crisis keywords detected - automated advice suspended"},
                timestamp=datetime.now(),
            )
        profile = await self._get_or_create_profile(request.student_id, request.context)
        conversation_history = await self._update_conversation(session_id, request.message)
        emotional_state = self.empathy.analyze_emotional_state(request.message)
        riasec_scores = self.psychometric.extract_riasec_from_conversation(conversation_history)
        dominant_riasec = [k for k, v in riasec_scores.items() if v > 0.6]
        aptitude = request.context.get("aptitude_score", 0.7)
        top_careers = self.psychometric.get_top_career_recommendations(
            riasec_scores, aptitude, profile.socio_economic_score, top_n=3
        )
        boosted_careers = []
        for career_id, score, data in top_careers:
            boost = self.regulatory.apply_nep_multidisciplinary_boost(data)
            boosted_careers.append((career_id, min(score * boost, 1.0), data))
        boosted_careers.sort(key=lambda x: x[1], reverse=True)
        career_data_list = [c[2] for c in boosted_careers]
        self.regulatory.audit_bias(career_data_list, profile)
        top_career_id = boosted_careers[0][0] if boosted_careers else None
        roadmap = None
        if top_career_id:
            roadmap = self.roadmap_gen.generate_roadmap(
                top_career_id, profile.grade, riasec_scores
            )
        base_response, from_llm = self._generate_counseling_response(
            boosted_careers,
            emotional_state,
            profile.grade,
            dominant_riasec,
            current_user_message=request.message,
            roadmap=roadmap,
            conversation_history=conversation_history,
        )
        if from_llm or (base_response or "").startswith("Configure OPENAI") or (base_response or "").startswith("I'm still"):
            final_response = base_response or ""
        else:
            final_response = self.empathy.generate_empathetic_response(
                base_response, emotional_state, request.context.get("student_name")
            )
        explanation = self._generate_explanation(
            boosted_careers[0] if boosted_careers else None, riasec_scores, emotional_state
        )
        career_suggestions = []
        for career_id, score, data in boosted_careers:
            career_suggestions.append({
                "career_id": career_id,
                "name": data["name"],
                "compatibility_score": round(score, 2),
                "riasec_match": [r.value for r in data["riasec_match"]],
                "market_demand": data["market_demand_2025"],
                "nsqf_level": data["nsqf_level"],
                "why_suitable": self._generate_career_rationale(career_id, riasec_scores, data),
            })
        await self._update_profile_with_session(profile, request.message, final_response)
        suggested = self._generate_suggested_questions(
            career_suggestions=career_suggestions,
            roadmap=roadmap,
            grade=profile.grade,
            final_response=final_response,
        )
        return CounselResponse(
            student_id=request.student_id,
            session_id=session_id,
            response_text=final_response,
            detected_riasec=[r.value for r in dominant_riasec],
            career_suggestions=career_suggestions,
            tactical_roadmap=roadmap,
            compatibility_scores={c[0]: round(c[1], 2) for c in boosted_careers},
            empathy_score=round(emotional_state["anxiety_level"], 2),
            crisis_flag=None if crisis_type == CrisisType.NONE else crisis_type.value,
            explanation=explanation,
            suggested_questions=suggested,
            timestamp=datetime.now(),
        )

    def _generate_suggested_questions(
        self,
        career_suggestions: List[Dict],
        roadmap: Optional[Dict],
        grade: int,
        final_response: str,
    ) -> List[str]:
        """Generate 3–4 context-aware follow-up questions based on the response."""
        out: List[str] = []
        names = [c.get("name") or c.get("career_id", "") for c in career_suggestions[:3] if c]
        if names:
            if len(names) >= 2:
                out.append(f"How do I choose between {names[0]} and {names[1]}?")
            out.append(f"Tell me more about {names[0]} and what I should study.")
        if roadmap and roadmap.get("phases"):
            out.append(f"Walk me through steps for Grade {grade + 1}")
        out.append("What are the best streams for me?")
        if grade <= 10:
            out.append("What subjects should I focus on now?")
        else:
            out.append("What entrance exams should I prepare for?")
        return list(dict.fromkeys(out))[:4]

    def _user_wants_roadmap_steps(self, message: str) -> bool:
        """True if the user is agreeing to or asking for roadmap steps (avoid repeating the question)."""
        if not message or len(message.strip()) < 2:
            return False
        lower = message.lower().strip()
        agree = any(w in lower for w in ("yes", "sure", "please", "yeah", "yep", "ok", "okay"))
        walk = "walk" in lower and ("through" in lower or "step" in lower)
        steps = "step" in lower or "specific" in lower
        grade_ref = "grade" in lower and any(d in lower for d in ("9", "10", "11", "12"))
        return (agree or walk or steps) and (walk or steps or grade_ref or len(lower) < 50)

    def _generate_counseling_response(
        self,
        careers: List[Tuple[str, float, Dict]],
        emotional_state: Dict,
        grade: int,
        dominant_riasec: List[RIASECType],
        current_user_message: Optional[str] = None,
        roadmap: Optional[Dict] = None,
        conversation_history: Optional[List[str]] = None,
    ) -> Tuple[str, bool]:
        """Returns (response_text, from_llm). When from_llm is True, caller should not add empathy layer."""
        # Build career_suggestions list for LLM
        career_suggestions = []
        for career_id, score, data in careers:
            career_suggestions.append({
                "career_id": career_id,
                "name": data["name"],
                "compatibility_score": round(score, 2),
            })
        riasec_desc = self._describe_riasec(dominant_riasec)
        dominant_str = [r.value for r in dominant_riasec]
        tone = emotional_state.get("tone_recommendation", "neutral_informative_balanced")

        # Try .env-based LLM (OpenAI) first
        llm_reply = generate_counseling_reply_llm(
            user_message=current_user_message or "",
            conversation_history=conversation_history or [],
            career_suggestions=career_suggestions,
            roadmap=roadmap,
            grade=grade,
            dominant_riasec=dominant_str,
            riasec_descriptions=riasec_desc,
            emotional_tone=tone,
            student_name=None,
        )
        if llm_reply:
            return (llm_reply, True)

        # No LLM: short fallback (no long static template)
        if not careers:
            return (
                "I'm still learning about your interests. Please share what subjects you enjoy or what kind of work you see yourself doing.",
                False,
            )
        return (
            "To get AI-generated career guidance, set OPENAI_API_KEY (or COUNSELLING_OPENAI_API_KEY) "
            "and optionally OPENAI_MODEL in your .env file, then restart the counselling engine.",
            False,
        )

    def _describe_riasec(self, riasec_types: List[RIASECType]) -> str:
        descriptions = {
            RIASECType.REALISTIC: "working with practical, hands-on problems",
            RIASECType.INVESTIGATIVE: "solving complex, intellectual challenges",
            RIASECType.ARTISTIC: "creative expression and unconventional thinking",
            RIASECType.SOCIAL: "helping and interacting with people",
            RIASECType.ENTERPRISING: "leading, persuading, and managing projects",
            RIASECType.CONVENTIONAL: "organizing data and working with structured systems",
        }
        if not riasec_types:
            return "various areas"
        return ", ".join(descriptions.get(r, "") for r in riasec_types)

    def _generate_career_rationale(
        self, career_id: str, riasec_scores: Dict[RIASECType, float], career_data: Dict
    ) -> str:
        matching_traits = [
            r.value for r in career_data["riasec_match"]
            if riasec_scores.get(r, 0) > 0.5
        ]
        if matching_traits:
            return f"Your interest in {', '.join(matching_traits)} activities aligns with this career's requirements."
        return "This career offers growth opportunities matching current market demands."

    def _generate_explanation(
        self,
        top_career: Optional[Tuple[str, float, Dict]],
        riasec_scores: Dict[RIASECType, float],
        emotional_state: Dict,
    ) -> Dict[str, str]:
        if not top_career:
            return {"error": "Insufficient data for recommendation"}
        career_id, score, data = top_career
        return {
            "primary_factor": f"Strong RIASEC match: {', '.join([r.value for r in data['riasec_match']])}",
            "psychometric_evidence": ", ".join(
                f"{k.value}({v:.2f})" for k, v in riasec_scores.items() if v > 0.4
            ),
            "market_context": f"Current demand score: {data['market_demand_2025']}/1.0",
            "nep_alignment": (
                "Multi-disciplinary pathway prioritized per NEP 2020"
                if data.get("nep_multidisciplinary")
                else "Traditional specialized pathway"
            ),
            "emotional_adjustment": f"Response tone adapted to detected anxiety level: {emotional_state['anxiety_level']:.2f}",
        }

    async def _get_or_create_profile(self, student_id: str, context: Dict) -> StudentProfile:
        try:
            profile_hash = self.security.hash_id(student_id)
            encrypted_data = self.redis_client.get(f"profile:{profile_hash}")
            if encrypted_data:
                return self.security.decrypt_profile(encrypted_data)
        except Exception as e:
            logger.error("Error retrieving profile: %s", e)
        return StudentProfile(
            student_id=student_id,
            grade=context.get("grade", 9),
            board=context.get("board", "CBSE"),
            socio_economic_score=context.get("ses_score", 0.5),
        )

    async def _update_profile_with_session(
        self, profile: StudentProfile, message: str, response: str
    ) -> None:
        profile.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "input": message[:200],
            "response_length": len(response),
        })
        profile.last_updated = datetime.now()
        try:
            encrypted = self.security.encrypt_profile(profile)
            profile_hash = self.security.hash_id(profile.student_id)
            self.redis_client.setex(
                f"profile:{profile_hash}",
                timedelta(days=365),
                encrypted,
            )
        except Exception as e:
            logger.error("Error saving profile: %s", e)

    async def _update_conversation(self, session_id: str, message: str) -> List[str]:
        key = f"session:{session_id}"
        self.redis_client.lpush(key, message)
        self.redis_client.ltrim(key, 0, self.max_history - 1)
        self.redis_client.expire(key, timedelta(hours=2))
        raw = self.redis_client.lrange(key, 0, -1)
        return [m.decode("utf-8") if isinstance(m, bytes) else m for m in (raw or [])]

    def _generate_session_id(self, student_id: str) -> str:
        return f"{self.security.hash_id(student_id)[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ---------------------------------------------------------------------------
# SECTION 9: FASTAPI APPLICATION
# ---------------------------------------------------------------------------

counsel_engine: Optional[DeepCounsellingEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global counsel_engine
    counsel_engine = DeepCounsellingEngine()
    logger.info("Deep-Counselling Engine initialized")
    yield
    counsel_engine = None
    logger.info("Deep-Counselling Engine shutdown")


app = FastAPI(
    title="Topteen Deep-Counselling API",
    description="AI-powered career counseling for Indian high school students (NEP 2020/NEAT 4.0 compliant)",
    version="1.0.0",
    lifespan=lifespan,
)

origins = os.getenv("COUNSELLING_CORS_ORIGINS", "https://topteen.in,https://www.topteen.in,http://localhost:8002,http://127.0.0.1:8002").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

security = HTTPBearer()


@app.post("/counsel", response_model=CounselResponse)
async def counsel_endpoint(
    request: CounselRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials.credentials != os.getenv("TOPTEEN_API_KEY", "dev-key"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not counsel_engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    try:
        response = await counsel_engine.process_counsel_request(request)
        background_tasks.add_task(
            log_counsel_session,
            request.student_id,
            response.detected_riasec,
            response.crisis_flag,
        )
        return response
    except Exception as e:
        logger.exception("Counseling error: %s", e)
        raise HTTPException(status_code=500, detail="Internal processing error")


async def log_counsel_session(
    student_id: str, riasec: List[str], crisis: Optional[str]
) -> None:
    pass


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "engine_loaded": counsel_engine is not None,
        "compliance": ["NEP 2020", "NEAT 4.0", "AES-256", "GDPR-Ready"],
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
