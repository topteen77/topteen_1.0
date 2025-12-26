"""
Career Matcher - Tinder-Style Career Discovery Platform
Production-ready application for high school students
"""

import json
import random
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class CareerCluster(Enum):
    """16 Career Clusters based on National Career Clusters Framework"""
    AGRICULTURE = "Agriculture, Food & Natural Resources"
    ARCHITECTURE = "Architecture & Construction"
    ARTS = "Arts, A/V Technology & Communications"
    BUSINESS = "Business Management & Administration"
    EDUCATION = "Education & Training"
    FINANCE = "Finance"
    GOVERNMENT = "Government & Public Administration"
    HEALTH = "Health Science"
    HOSPITALITY = "Hospitality & Tourism"
    HUMAN_SERVICES = "Human Services"
    IT = "Information Technology"
    LAW = "Law, Public Safety, Corrections & Security"
    MANUFACTURING = "Manufacturing"
    MARKETING = "Marketing"
    STEM = "Science, Technology, Engineering & Mathematics"
    TRANSPORTATION = "Transportation, Distribution & Logistics"


class PersonalityTrait(Enum):
    """Core personality dimensions"""
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    SOCIAL = "social"
    PRACTICAL = "practical"
    LEADERSHIP = "leadership"
    DETAIL_ORIENTED = "detail_oriented"
    ADVENTUROUS = "adventurous"
    HELPING = "helping"


@dataclass
class Career:
    """Individual career within a cluster"""
    id: str
    name: str
    cluster: CareerCluster
    description: str
    personality_match: List[PersonalityTrait]
    interests: List[str]
    aptitudes: List[str]
    education_level: str
    avg_salary: str
    growth_outlook: str
    image_url: str = ""
    
    def calculate_match_score(self, user_profile: 'UserProfile') -> float:
        """Calculate compatibility score (0-100)"""
        score = 0.0
        weights = {'personality': 0.4, 'interests': 0.35, 'aptitudes': 0.25}
        
        # Personality match
        personality_overlap = len(set(self.personality_match) & 
                                 set(user_profile.personality_traits))
        personality_score = (personality_overlap / 
                           max(len(self.personality_match), 1)) * 100
        
        # Interest match
        interest_overlap = len(set(self.interests) & 
                              set(user_profile.interests))
        interest_score = (interest_overlap / 
                         max(len(self.interests), 1)) * 100
        
        # Aptitude match
        aptitude_overlap = len(set(self.aptitudes) & 
                              set(user_profile.aptitudes))
        aptitude_score = (aptitude_overlap / 
                         max(len(self.aptitudes), 1)) * 100
        
        # Weighted total
        score = (personality_score * weights['personality'] +
                interest_score * weights['interests'] +
                aptitude_score * weights['aptitudes'])
        
        return round(score, 1)


@dataclass
class UserProfile:
    """Student profile with preferences"""
    user_id: str
    name: str
    personality_traits: List[PersonalityTrait]
    interests: List[str]
    aptitudes: List[str]
    preferred_education: List[str]
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class Match:
    """Represents a career match (swipe right)"""
    career_id: str
    match_score: float
    timestamp: str
    notes: str = ""


class CareerDatabase:
    """Database of careers across all 16 clusters"""
    
    def __init__(self):
        self.careers: List[Career] = self._initialize_careers()
    
    def _initialize_careers(self) -> List[Career]:
        """Initialize comprehensive career database"""
        return [
            # Agriculture, Food & Natural Resources
            Career(
                id="agr001",
                name="Agricultural Engineer",
                cluster=CareerCluster.AGRICULTURE,
                description="Design agricultural machinery and equipment, develop solutions for sustainable farming",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.PRACTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["sustainability", "technology", "problem-solving", "environment"],
                aptitudes=["math", "science", "engineering", "critical_thinking"],
                education_level="Bachelor's Degree",
                avg_salary="$82,000",
                growth_outlook="5% growth"
            ),
            Career(
                id="agr002",
                name="Environmental Scientist",
                cluster=CareerCluster.AGRICULTURE,
                description="Study the environment and develop solutions to environmental problems",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.ADVENTUROUS],
                interests=["environment", "research", "conservation", "data_analysis"],
                aptitudes=["science", "research", "writing", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$76,000",
                growth_outlook="6% growth"
            ),
            
            # Architecture & Construction
            Career(
                id="arc001",
                name="Architect",
                cluster=CareerCluster.ARCHITECTURE,
                description="Design buildings and structures, combining art and science",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["design", "art", "engineering", "sustainability"],
                aptitudes=["spatial_reasoning", "math", "drawing", "problem_solving"],
                education_level="Bachelor's + License",
                avg_salary="$89,000",
                growth_outlook="3% growth"
            ),
            Career(
                id="arc002",
                name="Civil Engineer",
                cluster=CareerCluster.ARCHITECTURE,
                description="Design and oversee construction of infrastructure projects",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.PRACTICAL, PersonalityTrait.LEADERSHIP],
                interests=["infrastructure", "problem_solving", "public_works"],
                aptitudes=["math", "engineering", "project_management"],
                education_level="Bachelor's Degree",
                avg_salary="$95,000",
                growth_outlook="7% growth"
            ),
            
            # Arts, A/V Technology & Communications
            Career(
                id="art001",
                name="Graphic Designer",
                cluster=CareerCluster.ARTS,
                description="Create visual content for digital and print media",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.DETAIL_ORIENTED],
                interests=["art", "design", "technology", "communication"],
                aptitudes=["creativity", "software_skills", "visual_thinking"],
                education_level="Bachelor's Degree",
                avg_salary="$57,000",
                growth_outlook="3% growth"
            ),
            Career(
                id="art002",
                name="Video Game Designer",
                cluster=CareerCluster.ARTS,
                description="Design gameplay experiences, mechanics, and narratives",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.ANALYTICAL],
                interests=["gaming", "storytelling", "technology", "art"],
                aptitudes=["programming", "creativity", "problem_solving"],
                education_level="Bachelor's Degree",
                avg_salary="$78,000",
                growth_outlook="16% growth"
            ),
            
            # Business Management & Administration
            Career(
                id="bus001",
                name="Business Analyst",
                cluster=CareerCluster.BUSINESS,
                description="Analyze business processes and recommend improvements",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED, PersonalityTrait.SOCIAL],
                interests=["problem_solving", "data_analysis", "strategy"],
                aptitudes=["critical_thinking", "communication", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$82,000",
                growth_outlook="11% growth"
            ),
            Career(
                id="bus002",
                name="Marketing Manager",
                cluster=CareerCluster.BUSINESS,
                description="Develop and implement marketing strategies",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.SOCIAL, PersonalityTrait.LEADERSHIP],
                interests=["marketing", "psychology", "communication", "strategy"],
                aptitudes=["creativity", "communication", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$135,000",
                growth_outlook="6% growth"
            ),
            
            # Education & Training
            Career(
                id="edu001",
                name="High School Teacher",
                cluster=CareerCluster.EDUCATION,
                description="Educate and inspire high school students",
                personality_match=[PersonalityTrait.SOCIAL, PersonalityTrait.HELPING, PersonalityTrait.LEADERSHIP],
                interests=["teaching", "mentoring", "subject_matter", "youth_development"],
                aptitudes=["communication", "patience", "organization"],
                education_level="Bachelor's + Certification",
                avg_salary="$62,000",
                growth_outlook="4% growth"
            ),
            Career(
                id="edu002",
                name="Instructional Designer",
                cluster=CareerCluster.EDUCATION,
                description="Create engaging educational content and curricula",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["education", "technology", "design", "psychology"],
                aptitudes=["creativity", "technical_skills", "communication"],
                education_level="Bachelor's Degree",
                avg_salary="$70,000",
                growth_outlook="6% growth"
            ),
            
            # Finance
            Career(
                id="fin001",
                name="Financial Analyst",
                cluster=CareerCluster.FINANCE,
                description="Analyze financial data and guide investment decisions",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["finance", "investing", "data_analysis", "economics"],
                aptitudes=["math", "analysis", "critical_thinking"],
                education_level="Bachelor's Degree",
                avg_salary="$95,000",
                growth_outlook="9% growth"
            ),
            Career(
                id="fin002",
                name="Actuary",
                cluster=CareerCluster.FINANCE,
                description="Assess financial risks using mathematics and statistics",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["mathematics", "statistics", "problem_solving"],
                aptitudes=["advanced_math", "analysis", "statistics"],
                education_level="Bachelor's + Exams",
                avg_salary="$113,000",
                growth_outlook="18% growth"
            ),
            
            # Government & Public Administration
            Career(
                id="gov001",
                name="Urban Planner",
                cluster=CareerCluster.GOVERNMENT,
                description="Develop plans for land use and community development",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.SOCIAL, PersonalityTrait.CREATIVE],
                interests=["community_development", "sustainability", "policy"],
                aptitudes=["analysis", "communication", "problem_solving"],
                education_level="Master's Degree",
                avg_salary="$78,000",
                growth_outlook="4% growth"
            ),
            Career(
                id="gov002",
                name="Policy Analyst",
                cluster=CareerCluster.GOVERNMENT,
                description="Research and analyze public policy issues",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["government", "research", "policy", "social_issues"],
                aptitudes=["research", "writing", "critical_thinking"],
                education_level="Master's Degree",
                avg_salary="$75,000",
                growth_outlook="5% growth"
            ),
            
            # Health Science
            Career(
                id="hea001",
                name="Registered Nurse",
                cluster=CareerCluster.HEALTH,
                description="Provide patient care and health education",
                personality_match=[PersonalityTrait.HELPING, PersonalityTrait.SOCIAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["healthcare", "helping_others", "medicine", "science"],
                aptitudes=["science", "communication", "compassion"],
                education_level="Bachelor's Degree + License",
                avg_salary="$81,000",
                growth_outlook="6% growth"
            ),
            Career(
                id="hea002",
                name="Physical Therapist",
                cluster=CareerCluster.HEALTH,
                description="Help patients recover from injuries and improve mobility",
                personality_match=[PersonalityTrait.HELPING, PersonalityTrait.SOCIAL, PersonalityTrait.PRACTICAL],
                interests=["healthcare", "fitness", "rehabilitation", "helping_others"],
                aptitudes=["science", "communication", "physical_fitness"],
                education_level="Doctoral Degree",
                avg_salary="$97,000",
                growth_outlook="14% growth"
            ),
            
            # Hospitality & Tourism
            Career(
                id="hos001",
                name="Event Planner",
                cluster=CareerCluster.HOSPITALITY,
                description="Coordinate and manage events and conferences",
                personality_match=[PersonalityTrait.SOCIAL, PersonalityTrait.CREATIVE, PersonalityTrait.LEADERSHIP],
                interests=["events", "coordination", "creativity", "people"],
                aptitudes=["organization", "communication", "multitasking"],
                education_level="Bachelor's Degree",
                avg_salary="$56,000",
                growth_outlook="8% growth"
            ),
            Career(
                id="hos002",
                name="Hotel Manager",
                cluster=CareerCluster.HOSPITALITY,
                description="Oversee daily operations of hotels and resorts",
                personality_match=[PersonalityTrait.LEADERSHIP, PersonalityTrait.SOCIAL, PersonalityTrait.PRACTICAL],
                interests=["hospitality", "management", "customer_service"],
                aptitudes=["leadership", "communication", "problem_solving"],
                education_level="Bachelor's Degree",
                avg_salary="$61,000",
                growth_outlook="6% growth"
            ),
            
            # Human Services
            Career(
                id="hum001",
                name="Social Worker",
                cluster=CareerCluster.HUMAN_SERVICES,
                description="Help individuals and families cope with challenges",
                personality_match=[PersonalityTrait.HELPING, PersonalityTrait.SOCIAL, PersonalityTrait.ANALYTICAL],
                interests=["helping_others", "social_justice", "counseling"],
                aptitudes=["empathy", "communication", "problem_solving"],
                education_level="Master's Degree",
                avg_salary="$58,000",
                growth_outlook="9% growth"
            ),
            Career(
                id="hum002",
                name="School Counselor",
                cluster=CareerCluster.HUMAN_SERVICES,
                description="Guide students through academic and personal challenges",
                personality_match=[PersonalityTrait.HELPING, PersonalityTrait.SOCIAL, PersonalityTrait.LEADERSHIP],
                interests=["helping_others", "education", "psychology"],
                aptitudes=["communication", "empathy", "counseling"],
                education_level="Master's Degree",
                avg_salary="$63,000",
                growth_outlook="8% growth"
            ),
            
            # Information Technology
            Career(
                id="it001",
                name="Software Developer",
                cluster=CareerCluster.IT,
                description="Design, develop, and maintain software applications",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.CREATIVE, PersonalityTrait.DETAIL_ORIENTED],
                interests=["programming", "technology", "problem_solving", "innovation"],
                aptitudes=["programming", "logic", "problem_solving"],
                education_level="Bachelor's Degree",
                avg_salary="$124,000",
                growth_outlook="22% growth"
            ),
            Career(
                id="it002",
                name="Cybersecurity Analyst",
                cluster=CareerCluster.IT,
                description="Protect computer systems and networks from threats",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED, PersonalityTrait.PRACTICAL],
                interests=["security", "technology", "problem_solving"],
                aptitudes=["technical_skills", "critical_thinking", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$112,000",
                growth_outlook="32% growth"
            ),
            
            # Law, Public Safety, Corrections & Security
            Career(
                id="law001",
                name="Lawyer",
                cluster=CareerCluster.LAW,
                description="Represent clients in legal matters and court",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.SOCIAL, PersonalityTrait.LEADERSHIP],
                interests=["law", "advocacy", "debate", "justice"],
                aptitudes=["critical_thinking", "communication", "research"],
                education_level="Doctoral Degree (JD)",
                avg_salary="$135,000",
                growth_outlook="8% growth"
            ),
            Career(
                id="law002",
                name="Forensic Scientist",
                cluster=CareerCluster.LAW,
                description="Analyze physical evidence from crime scenes",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["science", "criminal_justice", "investigation"],
                aptitudes=["science", "analysis", "attention_to_detail"],
                education_level="Bachelor's Degree",
                avg_salary="$64,000",
                growth_outlook="11% growth"
            ),
            
            # Manufacturing
            Career(
                id="man001",
                name="Industrial Engineer",
                cluster=CareerCluster.MANUFACTURING,
                description="Optimize manufacturing processes and systems",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.PRACTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["efficiency", "problem_solving", "technology"],
                aptitudes=["engineering", "math", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$95,000",
                growth_outlook="12% growth"
            ),
            Career(
                id="man002",
                name="Quality Control Inspector",
                cluster=CareerCluster.MANUFACTURING,
                description="Ensure products meet quality standards",
                personality_match=[PersonalityTrait.DETAIL_ORIENTED, PersonalityTrait.PRACTICAL],
                interests=["quality", "precision", "problem_solving"],
                aptitudes=["attention_to_detail", "technical_skills"],
                education_level="Associate Degree",
                avg_salary="$46,000",
                growth_outlook="2% growth"
            ),
            
            # Marketing
            Career(
                id="mar001",
                name="Digital Marketing Specialist",
                cluster=CareerCluster.MARKETING,
                description="Create and manage online marketing campaigns",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.ANALYTICAL, PersonalityTrait.SOCIAL],
                interests=["marketing", "social_media", "data_analysis", "creativity"],
                aptitudes=["creativity", "communication", "technical_skills"],
                education_level="Bachelor's Degree",
                avg_salary="$67,000",
                growth_outlook="10% growth"
            ),
            Career(
                id="mar002",
                name="Brand Manager",
                cluster=CareerCluster.MARKETING,
                description="Develop and maintain brand identity and strategy",
                personality_match=[PersonalityTrait.CREATIVE, PersonalityTrait.LEADERSHIP, PersonalityTrait.ANALYTICAL],
                interests=["branding", "strategy", "creativity", "marketing"],
                aptitudes=["creativity", "leadership", "analysis"],
                education_level="Bachelor's Degree",
                avg_salary="$105,000",
                growth_outlook="6% growth"
            ),
            
            # STEM
            Career(
                id="ste001",
                name="Data Scientist",
                cluster=CareerCluster.STEM,
                description="Extract insights from complex data using statistics and ML",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.DETAIL_ORIENTED],
                interests=["data", "statistics", "programming", "problem_solving"],
                aptitudes=["math", "programming", "statistics", "analysis"],
                education_level="Master's Degree",
                avg_salary="$130,000",
                growth_outlook="36% growth"
            ),
            Career(
                id="ste002",
                name="Biomedical Engineer",
                cluster=CareerCluster.STEM,
                description="Design medical devices and healthcare solutions",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.CREATIVE, PersonalityTrait.HELPING],
                interests=["medicine", "engineering", "innovation", "healthcare"],
                aptitudes=["engineering", "biology", "problem_solving"],
                education_level="Bachelor's Degree",
                avg_salary="$99,000",
                growth_outlook="10% growth"
            ),
            
            # Transportation, Distribution & Logistics
            Career(
                id="tra001",
                name="Supply Chain Manager",
                cluster=CareerCluster.TRANSPORTATION,
                description="Coordinate logistics and supply chain operations",
                personality_match=[PersonalityTrait.ANALYTICAL, PersonalityTrait.LEADERSHIP, PersonalityTrait.PRACTICAL],
                interests=["logistics", "management", "problem_solving"],
                aptitudes=["organization", "analysis", "leadership"],
                education_level="Bachelor's Degree",
                avg_salary="$98,000",
                growth_outlook="6% growth"
            ),
            Career(
                id="tra002",
                name="Airline Pilot",
                cluster=CareerCluster.TRANSPORTATION,
                description="Operate aircraft and ensure passenger safety",
                personality_match=[PersonalityTrait.ADVENTUROUS, PersonalityTrait.DETAIL_ORIENTED, PersonalityTrait.PRACTICAL],
                interests=["aviation", "travel", "technology"],
                aptitudes=["spatial_reasoning", "decision_making", "technical_skills"],
                education_level="Flight Training + License",
                avg_salary="$202,000",
                growth_outlook="6% growth"
            ),
        ]
    
    def get_career_by_id(self, career_id: str) -> Optional[Career]:
        """Retrieve career by ID"""
        for career in self.careers:
            if career.id == career_id:
                return career
        return None
    
    def get_careers_by_cluster(self, cluster: CareerCluster) -> List[Career]:
        """Get all careers in a specific cluster"""
        return [c for c in self.careers if c.cluster == cluster]


class CareerMatcher:
    """Main application logic - Tinder-style career matching"""
    
    def __init__(self):
        self.db = CareerDatabase()
        self.user_profile: Optional[UserProfile] = None
        self.career_queue: List[Career] = []
        self.matches: List[Match] = []
        self.rejected_careers: List[str] = []
        self.current_index = 0
    
    def create_user_profile(self, name: str, personality_traits: List[str],
                           interests: List[str], aptitudes: List[str],
                           preferred_education: List[str]) -> UserProfile:
        """Create student profile"""
        # Convert string traits to enum
        trait_enums = []
        for trait in personality_traits:
            try:
                trait_enums.append(PersonalityTrait(trait.lower()))
            except ValueError:
                continue
        
        user_id = f"user_{datetime.now().timestamp()}"
        self.user_profile = UserProfile(
            user_id=user_id,
            name=name,
            personality_traits=trait_enums,
            interests=[i.lower() for i in interests],
            aptitudes=[a.lower() for a in aptitudes],
            preferred_education=[e.lower() for e in preferred_education]
        )
        
        # Initialize career queue with scored careers
        self._initialize_career_queue()
        
        return self.user_profile
    
    def _initialize_career_queue(self):
        """Sort careers by compatibility score"""
        if not self.user_profile:
            return
        
        scored_careers = []
        for career in self.db.careers:
            score = career.calculate_match_score(self.user_profile)
            scored_careers.append((career, score))
        
        # Sort by score descending
        scored_careers.sort(key=lambda x: x[1], reverse=True)
        self.career_queue = [c[0] for c in scored_careers]
        self.current_index = 0
    
    def get_next_career(self) -> Optional[Tuple[Career, float]]:
        """Get next career to display (Tinder card)"""
        if not self.user_profile or self.current_index >= len(self.career_queue):
            return None
        
        career = self.career_queue[self.current_index]
        score = career.calculate_match_score(self.user_profile)
        return career, score
    
    def swipe_right(self, notes: str = "") -> Match:
        """Like a career (swipe right)"""
        career, score = self.get_next_career()
        
        match = Match(
            career_id=career.id,
            match_score=score,
            timestamp=datetime.now().isoformat(),
            notes=notes
        )
        
        self.matches.append(match)
        self.current_index += 1
        
        return match
    
    def swipe_left(self):
        """Reject a career (swipe left)"""
        career, _ = self.get_next_career()
        self.rejected_careers.append(career.id)
        self.current_index += 1
    
    def get_matches(self) -> List[Tuple[Career, Match]]:
        """Get all matched careers with details"""
        results = []
        for match in self.matches:
            career = self.db.get_career_by_id(match.career_id)
            if career:
                results.append((career, match))
        return results
    
    def get_top_matches(self, n: int = 5) -> List[Tuple[Career, float]]:
        """Get top N career matches"""
        if not self.user_profile:
            return []
        
        scored = [(c, c.calculate_match_score(self.user_profile)) 
                  for c in self.db.careers]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]
    
    def export_matches(self) -> str:
        """Export matches as JSON"""
        export_data = {
            'user_profile': asdict(self.user_profile) if self.user_profile else {},
            'matches': [],
            'timestamp': datetime.now().isoformat()
        }
        
        for career, match in self.get_matches():
            export_data['matches'].append({
                'career': {
                    'name': career.name,
                    'cluster': career.cluster.value,
                    'description': career.description,
                    'education_level': career.education_level,
                    'avg_salary': career.avg_salary,
                    'growth_outlook': career.growth_outlook
                },
                'match_score': match.match_score,
                'timestamp': match.timestamp,
                'notes': match.notes
            })
        
        return json.dumps(export_data, indent=2)


class ConsoleUI:
    """Console-based user interface"""
    
    def __init__(self):
        self.matcher = CareerMatcher()
    
    def clear_screen(self):
        """Clear console (cross-platform)"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_banner(self):
        """Display app banner"""
        print("\n" + "=" * 60)
        print("🎯 CAREER MATCHER - Find Your Perfect Career Path")
        print("=" * 60 + "\n")
    
    def setup_profile(self):
        """Interactive profile setup"""
        self.clear_screen()
        self.display_banner()
        print("Let's create your profile!\n")
        
        name = input("What's your name? ").strip()
        
        print("\n📊 Select your personality traits (comma-separated):")
        print("Options: analytical, creative, social, practical,")
        print("         leadership, detail_oriented, adventurous, helping")
        traits_input = input("Your traits: ").strip()
        traits = [t.strip() for t in traits_input.split(',')]
        
        print("\n💡 What are your interests? (comma-separated)")
        print("Examples: technology, art, helping_others, problem_solving,")
        print("          science, business, communication, design")
        interests_input = input("Your interests: ").strip()
        interests = [i.strip() for i in interests_input.split(',')]
        
        print("\n🎓 What are your strongest aptitudes? (comma-separated)")
        print("Examples: math, programming, communication, creativity,")
        print("          analysis, leadership, writing, science")
        aptitudes_input = input("Your aptitudes: ").strip()
        aptitudes = [a.strip() for a in aptitudes_input.split(',')]
        
        print("\n🎓 Preferred education level? (comma-separated)")
        print("Options: associate, bachelor's, master's, doctoral, certificate")
        education_input = input("Education preference: ").strip()
        education = [e.strip() for e in education_input.split(',')]
        
        profile = self.matcher.create_user_profile(
            name, traits, interests, aptitudes, education
        )
        
        print(f"\n✅ Profile created for {profile.name}!")
        input("\nPress Enter to start exploring careers...")
    
    def display_career_card(self, career: Career, score: float):
        """Display career like a Tinder card"""
        self.clear_screen()
        print("\n" + "╔" + "═" * 58 + "╗")
        print(f"║ {'CAREER MATCH':^56} ║")
        print("╠" + "═" * 58 + "╣")
        print(f"║ {career.name:^56} ║")
        print(f"║ {career.cluster.value:^56} ║")
        print("╠" + "═" * 58 + "╣")
        print(f"║ Match Score: {score:.1f}%{' ' * 42}║")
        print("╠" + "═" * 58 + "╣")
        
        # Description
        desc_lines = [career.description[i:i+54] 
                      for i in range(0, len(career.description), 54)]
        for line in desc_lines:
            print(f"║ {line:<56} ║")
        
        print("╠" + "═" * 58 + "╣")
        print(f"║ 💼 Education: {career.education_level:<39} ║")
        print(f"║ 💰 Avg Salary: {career.avg_salary:<38} ║")
        print(f"║ 📈 Growth: {career.growth_outlook:<42} ║")
        print("╠" + "═" * 58 + "╣")
        
        # Personality match
        traits = ", ".join([t.value for t in career.personality_match[:3]])
        print(f"║ 🧠 Traits: {traits:<45} ║")
        
        # Interests
        interests = ", ".join(career.interests[:3])
        print(f"║ 💡 Interests: {interests:<42} ║")
        
        # Aptitudes
        aptitudes = ", ".join(career.aptitudes[:3])
        print(f"║ 🎯 Aptitudes: {aptitudes:<41} ║")
        
        print("╚" + "═" * 58 + "╝")
    
    def swipe_interface(self):
        """Main swipe interface"""
        while True:
            result = self.matcher.get_next_career()
            if not result:
                print("\n🎉 You've reviewed all careers!")
                break
            
            career, score = result
            self.display_career_card(career, score)
            
            print("\n" + "─" * 60)
            print("👈 [L] Swipe Left (Not Interested)")
            print("👉 [R] Swipe Right (I'm Interested!)")
            print("💬 [I] More Info")
            print("🏁 [Q] Finish and View Matches")
            print("─" * 60)
            
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == 'r':
                notes = input("Add notes (optional): ").strip()
                match = self.matcher.swipe_right(notes)
                print(f"✅ Added to your matches! (Score: {match.match_score:.1f}%)")
                input("Press Enter to continue...")
            elif choice == 'l':
                self.matcher.swipe_left()
                print("⏭️  Passed on this career")
                input("Press Enter to continue...")
            elif choice == 'i':
                self.show_detailed_info(career, score)
            elif choice == 'q':
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")
    
    def show_detailed_info(self, career: Career, score: float):
        """Show detailed career information"""
        self.clear_screen()
        print("\n" + "=" * 60)
        print(f" {career.name}")
        print("=" * 60)
        print(f"\nCluster: {career.cluster.value}")
        print(f"Match Score: {score:.1f}%")
        print(f"\nDescription:\n{career.description}")
        print(f"\n💼 Education Required: {career.education_level}")
        print(f"💰 Average Salary: {career.avg_salary}")
        print(f"📈 Job Growth Outlook: {career.growth_outlook}")
        
        print("\n🧠 Best Personality Traits:")
        for trait in career.personality_match:
            print(f"   • {trait.value.replace('_', ' ').title()}")
        
        print("\n💡 Key Interests:")
        for interest in career.interests:
            print(f"   • {interest.replace('_', ' ').title()}")
        
        print("\n🎯 Required Aptitudes:")
        for aptitude in career.aptitudes:
            print(f"   • {aptitude.replace('_', ' ').title()}")
        
        print("\n" + "=" * 60)
        input("\nPress Enter to return...")
    
    def show_matches(self):
        """Display all matched careers"""
        self.clear_screen()
        matches = self.matcher.get_matches()
        
        if not matches:
            print("\n❌ No matches yet! Start swiping to find careers.")
            input("\nPress Enter to continue...")
            return
        
        print("\n" + "=" * 60)
        print(" 🎯 YOUR CAREER MATCHES")
        print("=" * 60 + "\n")
        
        for i, (career, match) in enumerate(matches, 1):
            print(f"{i}. {career.name}")
            print(f"   Cluster: {career.cluster.value}")
            print(f"   Match Score: {match.match_score:.1f}%")
            print(f"   Salary: {career.avg_salary} | Growth: {career.growth_outlook}")
            if match.notes:
                print(f"   Notes: {match.notes}")
            print()
        
        print("=" * 60)
        
        # Export option
        export = input("\n📥 Export matches to JSON? (y/n): ").strip().lower()
        if export == 'y':
            filename = f"career_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                f.write(self.matcher.export_matches())
            print(f"✅ Matches exported to {filename}")
        
        input("\nPress Enter to continue...")
    
    def show_top_recommendations(self):
        """Show top career recommendations"""
        self.clear_screen()
        print("\n" + "=" * 60)
        print(" 🏆 TOP 10 CAREER RECOMMENDATIONS FOR YOU")
        print("=" * 60 + "\n")
        
        top_matches = self.matcher.get_top_matches(10)
        
        for i, (career, score) in enumerate(top_matches, 1):
            print(f"{i}. {career.name} - {score:.1f}% match")
            print(f"   {career.cluster.value}")
            print(f"   {career.education_level} | {career.avg_salary}")
            print()
        
        print("=" * 60)
        input("\nPress Enter to continue...")
    
    def main_menu(self):
        """Main application menu"""
        while True:
            self.clear_screen()
            self.display_banner()
            
            if self.matcher.user_profile:
                print(f"Welcome back, {self.matcher.user_profile.name}!\n")
            
            print("1. 🎯 Start Swiping Careers")
            print("2. 💼 View My Matches")
            print("3. 🏆 Top Recommendations")
            print("4. 👤 Create New Profile")
            print("5. 📊 Career Clusters Info")
            print("6. 🚪 Exit")
            
            choice = input("\nSelect an option: ").strip()
            
            if choice == '1':
                if not self.matcher.user_profile:
                    print("\n⚠️  Please create a profile first!")
                    input("Press Enter to continue...")
                    self.setup_profile()
                self.swipe_interface()
            elif choice == '2':
                self.show_matches()
            elif choice == '3':
                if not self.matcher.user_profile:
                    print("\n⚠️  Please create a profile first!")
                    input("Press Enter to continue...")
                else:
                    self.show_top_recommendations()
            elif choice == '4':
                self.setup_profile()
            elif choice == '5':
                self.show_career_clusters()
            elif choice == '6':
                print("\n👋 Thanks for using Career Matcher!")
                print("Good luck on your career journey! 🚀\n")
                break
            else:
                print("❌ Invalid option")
                input("Press Enter to continue...")
    
    def show_career_clusters(self):
        """Display information about all 16 career clusters"""
        self.clear_screen()
        print("\n" + "=" * 60)
        print(" 📚 16 NATIONAL CAREER CLUSTERS")
        print("=" * 60 + "\n")
        
        for i, cluster in enumerate(CareerCluster, 1):
            careers = self.matcher.db.get_careers_by_cluster(cluster)
            print(f"{i}. {cluster.value}")
            print(f"   Sample careers: {', '.join([c.name for c in careers[:2]])}")
            print()
        
        print("=" * 60)
        input("\nPress Enter to continue...")
    
    def run(self):
        """Start the application"""
        try:
            self.main_menu()
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please contact support if this persists.")


# Entry point
if __name__ == "__main__":
    app = ConsoleUI()
    app.run()