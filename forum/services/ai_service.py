import openai
from django.conf import settings
from django.core.cache import cache
from forum.models import KnowledgeBaseEntry, Country, Category, Query, Response
import json
import re
from difflib import SequenceMatcher
from collections import Counter
import math


def extract_entities(query):
    """Extract country, course, and category from query"""
    query_lower = query.lower()
    
    # Extract country
    countries = Country.objects.all()
    country = None
    for c in countries:
        if c.name.lower() in query_lower or c.code.lower() in query_lower:
            country = c
            break
    
    # Extract category keywords - expanded list for better matching (career-focused)
    category_keywords = {
        'admission': ['admission', 'requirements', 'apply', 'application', 'entry', 'eligibility', 'qualification', 'prerequisite', 'university admission', 'college admission', 'enrollment', 'acceptance', 'cutoff', 'merit'],
        'visa': ['visa', 'permit', 'immigration', 'document', 'visa application', 'study permit', 'student visa', 'visa requirements', 'immigration process'],
        'finance': ['cost', 'fee', 'tuition', 'scholarship', 'financial', 'budget', 'price', 'expense', 'funding', 'loan', 'afford', 'cheap', 'expensive', 'cost of living', 'tuition fee', 'salary', 'earning', 'income'],
        'accommodation': ['accommodation', 'housing', 'hostel', 'dorm', 'rent', 'living', 'residence', 'apartment', 'room', 'lodging', 'stay', 'where to live'],
        'work': ['work', 'job', 'employment', 'part-time', 'earn', 'salary', 'working', 'work permit', 'work rights', 'employment rights', 'can i work', 'work while studying', 'student job', 'freelance'],
        'predeparture': ['pre-departure', 'before leaving', 'packing', 'preparation', 'what to bring', 'checklist', 'before travel', 'departure'],
        'stem': ['science', 'engineering', 'technology', 'math', 'physics', 'chemistry', 'biology', 'jee', 'neet', 'engineering', 'medical', 'pcm', 'pcb', 'pcmb'],
        'commerce': ['commerce', 'business', 'accounting', 'economics', 'ca', 'chartered accountant', 'company secretary', 'cs', 'finance', 'banking'],
        'arts': ['arts', 'humanities', 'design', 'psychology', 'sociology', 'literature', 'history', 'nid', 'nift', 'design', 'creative'],
        'vocational': ['vocational', 'diploma', 'iti', 'polytechnic', 'skill', 'certification', 'trade'],
        'emerging': ['emerging', 'ai', 'machine learning', 'data science', 'cybersecurity', 'blockchain', 'prompt engineer', 'climate', 'sustainability'],
        'studyabroad': ['study abroad', 'foreign', 'international', 'usa', 'uk', 'canada', 'australia', 'sat', 'ielts', 'toefl'],
    }
    
    category = None
    # Try to match categories - check in order of specificity
    # First check for exact matches, then partial matches
    for cat_name, keywords in category_keywords.items():
        if any(kw in query_lower for kw in keywords):
            try:
                category = Category.objects.get(slug=cat_name)
                break
            except Category.DoesNotExist:
                pass
    
    # If no category found, try to infer from common patterns
    if category is None:
        # Check for stream-related terms
        stream_terms = ['stream', 'science', 'commerce', 'arts', 'after 10th', 'after tenth', 'subject', 'subjects']
        if any(term in query_lower for term in stream_terms):
            try:
                # Try to match to specific stream categories
                if 'science' in query_lower or 'engineering' in query_lower or 'medical' in query_lower:
                    category = Category.objects.filter(slug='stem').first()
                elif 'commerce' in query_lower or 'business' in query_lower:
                    category = Category.objects.filter(slug='commerce').first()
                elif 'arts' in query_lower or 'design' in query_lower:
                    category = Category.objects.filter(slug='arts').first()
                else:
                    category = Category.objects.filter(slug='admission').first()
            except Category.DoesNotExist:
                pass
        # Check for career-related terms
        elif any(word in query_lower for word in ['career', 'job', 'profession', 'what should i do', 'which career']):
            try:
                category = Category.objects.filter(slug='work').first()
            except Category.DoesNotExist:
                pass
        # Check for admission-related terms
        admission_terms = ['university', 'college', 'degree', 'program', 'course', 'masters', 'bachelor', 'phd', 'ms', 'mba', 'bachelor', 'best universities', 'top universities', 'study in', 'admission']
        if category is None and any(term in query_lower for term in admission_terms):
            try:
                category = Category.objects.filter(slug='admission').first()
            except Category.DoesNotExist:
                pass
        # Check for country-specific queries (might be country category)
        elif category is None and any(word in query_lower for word in ['country', 'compare countries', 'which country', 'best country', 'study abroad', 'abroad']):
            try:
                category = Category.objects.filter(slug='studyabroad').first() or Category.objects.filter(slug='country').first()
            except Category.DoesNotExist:
                pass
    
    return country, category


def extract_subject_or_course(query_text):
    """
    Extract the subject/course from a query (e.g., 'computer science', 'science', 'commerce', 'engineering')
    Returns the subject string if found, None otherwise
    """
    query_lower = query_text.lower()
    
    # Common subjects/courses to look for (ordered by specificity - most specific first)
    subjects = [
        'computer science', 'data science', 'information technology', 'software engineering',
        'mechanical engineering', 'electrical engineering', 'civil engineering', 'chemical engineering',
        'business administration', 'commerce', 'accounting', 'finance', 'economics', 'marketing',
        'medicine', 'nursing', 'pharmacy', 'dentistry', 'veterinary',
        'law', 'legal studies', 'jurisprudence',
        'arts', 'humanities', 'literature', 'history', 'philosophy',
        'science', 'physics', 'chemistry', 'biology', 'mathematics', 'statistics',
        'psychology', 'sociology', 'political science', 'international relations',
        'architecture', 'design', 'fashion', 'fine arts',
        'education', 'teaching', 'pedagogy',
        'agriculture', 'environmental science', 'forestry',
        'journalism', 'media studies', 'communication',
    ]
    
    # First, try to find specific subjects in the query (check most specific first)
    for subject in subjects:
        if subject in query_lower:
            return subject.strip()
    
    # If no specific subject found, try pattern matching
    subject_patterns = [
        r'for\s+([a-z\s]+?)(?:\?|$|universit|program|course|degree|college)',
        r'in\s+([a-z\s]+?)(?:\?|$|universit|program|course|degree|college)',
        r'universit[ies]*\s+for\s+([a-z\s]+?)(?:\?|$)',
        r'best\s+([a-z\s]+?)\s+universit',
        r'top\s+([a-z\s]+?)\s+universit',
    ]
    
    for pattern in subject_patterns:
        match = re.search(pattern, query_lower)
        if match:
            extracted = match.group(1).strip()
            # Clean up common words
            extracted = re.sub(r'\b(for|in|the|a|an|and|or|best|top|universit|universities|program|course|degree)\b', '', extracted).strip()
            if extracted and len(extracted) > 2:
                return extracted
    
    return None


def normalize_query(query_text):
    """
    Normalize query text for comparison
    - Convert to lowercase
    - Remove extra whitespace
    - Remove punctuation (optional, for better matching)
    """
    # Convert to lowercase and strip
    normalized = query_text.lower().strip()
    # Remove multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove trailing punctuation (but keep question marks for context)
    normalized = normalized.rstrip('.,!;:')
    return normalized


def extract_keywords(text):
    """
    Extract meaningful keywords from text for semantic matching
    Removes common stop words and returns important terms
    Handles abbreviations and common education terms
    """
    # Common stop words in English
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'will', 'with', 'what', 'where', 'when', 'who', 'why',
        'how', 'can', 'could', 'should', 'would', 'may', 'might', 'must',
        'do', 'does', 'did', 'have', 'had', 'has', 'been', 'being',
        'i', 'you', 'we', 'they', 'this', 'these', 'those', 'there', 'their'
    }
    
    # Common abbreviations in education context (keep these)
    education_abbrevs = {'ms', 'mba', 'phd', 'bs', 'ba', 'ma', 'mfa', 'usa', 'uk', 'us', 'pr', 'gpa', 'gre', 'gmat', 'ielts', 'toefl', 'sop', 'lor', 'cv'}
    
    # Normalize and split into words
    normalized = normalize_query(text)
    # Remove punctuation and split
    words = re.findall(r'\b\w+\b', normalized)
    
    # Filter out stop words, but keep:
    # - Words longer than 2 characters
    # - Education abbreviations (even if 2-3 chars)
    keywords = []
    for w in words:
        w_lower = w.lower()
        if w_lower not in stop_words:
            if len(w) > 2 or w_lower in education_abbrevs:
                keywords.append(w_lower)
    
    return set(keywords)


def calculate_semantic_similarity(text1, text2):
    """
    Calculate semantic similarity between two texts using multiple methods
    Returns a score between 0.0 and 1.0
    
    IMPORTANT: If queries have different subjects/courses, they are treated as different
    even if the similarity score is high.
    """
    # Extract subjects/courses from both queries
    subject1 = extract_subject_or_course(text1)
    subject2 = extract_subject_or_course(text2)
    
    # If both queries have subjects and they're different, reduce similarity significantly
    if subject1 and subject2 and subject1 != subject2:
        # Check if one subject is contained in the other (e.g., "computer science" contains "science")
        # In that case, they're still different queries
        if subject1 not in subject2 and subject2 not in subject1:
            # Different subjects - reduce similarity by 50% to ensure they're treated as different
            # This ensures queries like "computer science" vs "commerce" are not matched
            pass  # We'll apply this reduction at the end
    
    # Method 1: Sequence-based similarity (handles word order)
    seq_similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    # Method 2: Keyword-based similarity (Jaccard similarity)
    keywords1 = extract_keywords(text1)
    keywords2 = extract_keywords(text2)
    
    if not keywords1 or not keywords2:
        # If no keywords, fall back to sequence similarity
        base_similarity = seq_similarity
    else:
        # Jaccard similarity: intersection / union
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        jaccard_similarity = intersection / union if union > 0 else 0.0
        
        # Method 3: Word frequency-based cosine similarity (simplified)
        all_words = keywords1 | keywords2
        vec1 = [1 if word in keywords1 else 0 for word in all_words]
        vec2 = [1 if word in keywords2 else 0 for word in all_words]
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        cosine_similarity = dot_product / (magnitude1 * magnitude2) if (magnitude1 * magnitude2) > 0 else 0.0
        
        # Combine methods with weighted average
        # Sequence similarity: 30% (handles exact matches and word order)
        # Jaccard similarity: 40% (handles keyword overlap)
        # Cosine similarity: 30% (handles semantic meaning)
        base_similarity = (
            seq_similarity * 0.3 +
            jaccard_similarity * 0.4 +
            cosine_similarity * 0.3
        )
    
    # Apply subject-based penalty if subjects are different
    if subject1 and subject2 and subject1 != subject2:
        # If subjects are completely different, significantly reduce similarity
        if subject1 not in subject2 and subject2 not in subject1:
            # Different subjects - reduce similarity significantly to ensure they're treated as different
            # Reduce by 50% to bring it well below threshold
            base_similarity = base_similarity * 0.5
        else:
            # One subject contains the other (e.g., "computer science" vs "science")
            # Still different queries, apply moderate penalty
            base_similarity = base_similarity * 0.7
    
    # Additional strictness: For queries asking about different things, require very high similarity
    # Only match if similarity is very high (close to exact match)
    return base_similarity


def find_similar_query(query_text, similarity_threshold=None):
    """
    Find similar queries in the database using semantic pattern matching
    Returns the response text if a similar query is found, None otherwise
    
    Uses multiple similarity methods:
    1. Exact match (case-insensitive)
    2. Normalized exact match
    3. Semantic similarity (keyword-based, sequence-based, cosine similarity)
    
    Args:
        query_text: The query text to search for
        similarity_threshold: Minimum similarity ratio (0.0 to 1.0)
                          If None, uses SEMANTIC_SIMILARITY_THRESHOLD from settings
    
    Returns:
        tuple: (response_text, cost) if found, (None, 0.0) otherwise
    """
    # Use threshold from settings if not provided
    # Default to 0.85 for strict matching (only very similar queries)
    if similarity_threshold is None:
        similarity_threshold = getattr(settings, 'SEMANTIC_SIMILARITY_THRESHOLD', 0.85)
    
    normalized_query = normalize_query(query_text)
    
    # First, try exact match (case-insensitive) - fastest
    try:
        exact_match = Query.objects.filter(
            question_text__iexact=query_text,
            status='completed'
        ).select_related('response').first()
        
        if exact_match and hasattr(exact_match, 'response'):
            response_text = exact_match.response.response_text
            # Skip error responses - regenerate them
            if response_text and (
                ('Error:' in response_text and 'API key' in response_text) or
                ('I apologize, but I can only assist' in response_text)
            ):
                pass  # Skip this error response, continue to AI generation
            else:
                return response_text, 0.0  # Free - from database
    except Exception:
        pass
    
    # Then try normalized exact match and semantic similarity
    try:
        # Get recent completed queries with responses (limit to last 1000 for performance)
        completed_queries = Query.objects.filter(
            status='completed'
        ).select_related('response').exclude(
            response=None
        ).order_by('-created_at')[:1000]  # Limit to recent queries for performance
        
        best_match = None
        best_similarity = 0.0
        
        for query in completed_queries:
            normalized_existing = normalize_query(query.question_text)
            
            # Check normalized exact match first (fastest)
            if normalized_query == normalized_existing:
                if hasattr(query, 'response'):
                    response_text = query.response.response_text
                    # Skip error responses - regenerate them
                    if response_text and (
                        ('Error:' in response_text and 'API key' in response_text) or
                        ('I apologize, but I can only assist' in response_text)
                    ):
                        continue  # Skip this error response
                    else:
                        return response_text, 0.0  # Free - from database
                continue
            
            # Extract subjects from both queries to check if they're different
            current_subject = extract_subject_or_course(query_text)
            existing_subject = extract_subject_or_course(query.question_text)
            
            # If subjects are different, skip this query (treat as different question)
            if current_subject and existing_subject:
                # Normalize subjects for comparison
                current_subject_norm = current_subject.lower().strip()
                existing_subject_norm = existing_subject.lower().strip()
                
                # If subjects are completely different, skip this match
                if (current_subject_norm != existing_subject_norm and 
                    current_subject_norm not in existing_subject_norm and 
                    existing_subject_norm not in current_subject_norm):
                    continue  # Different subjects - treat as different queries
            
            # Calculate semantic similarity (combines multiple methods)
            similarity = calculate_semantic_similarity(query_text, query.question_text)
            
            # Track best match (but skip error responses)
            if similarity > best_similarity:
                if hasattr(query, 'response'):
                    response_text = query.response.response_text
                    # Skip error responses when tracking best match
                    if response_text and not (
                        ('Error:' in response_text and 'API key' in response_text) or
                        ('I apologize, but I can only assist' in response_text)
                    ):
                        best_similarity = similarity
                        best_match = response_text
            
            # Early return if we find a very good match
            if similarity >= 0.95:  # Very high similarity
                if hasattr(query, 'response'):
                    response_text = query.response.response_text
                    # Skip error responses - regenerate them
                    if response_text and (
                        ('Error:' in response_text and 'API key' in response_text) or
                        ('I apologize, but I can only assist' in response_text)
                    ):
                        continue  # Skip this error response
                    else:
                        return response_text, 0.0  # Free - from database
        
        # Return best match if it meets threshold (but skip error responses)
        # Also verify subjects match for strict matching
        if best_match and best_similarity >= similarity_threshold:
            # Skip error responses - regenerate them
            if (
                ('Error:' in best_match and 'API key' in best_match) or
                ('I apologize, but I can only assist' in best_match)
            ):
                pass  # Skip this error response, continue to AI generation
            else:
                # For strict matching, verify subjects match if both queries have subjects
                current_subject = extract_subject_or_course(query_text)
                # Find the query that gave us best_match to check its subject
                best_match_query = None
                for q in completed_queries:
                    if hasattr(q, 'response') and q.response.response_text == best_match:
                        best_match_query = q
                        break
                
                if best_match_query:
                    existing_subject = extract_subject_or_course(best_match_query.question_text)
                    # If both have subjects, they must match
                    if current_subject and existing_subject:
                        if current_subject.lower().strip() != existing_subject.lower().strip():
                            # Subjects don't match - don't return cached response
                            return None, 0.0
                
                return best_match, 0.0  # Free - from database
            
    except Exception as e:
        # If there's an error, log it but continue to AI generation
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error finding similar query: {e}")
        pass
    
    return None, 0.0


def get_knowledge_base_context(query, country=None, category=None):
    """Retrieve relevant knowledge base entries"""
    entries = KnowledgeBaseEntry.objects.all()
    
    if country:
        entries = entries.filter(country=country)
    if category:
        entries = entries.filter(category=category)
    
    # Get most recent entries
    entries = entries[:5]
    
    context = []
    for entry in entries:
        context.append({
            'title': entry.title,
            'content': entry.content,
            'category': entry.category.name if entry.category else None,
            'country': entry.country.name if entry.country else None,
        })
    
    return json.dumps(context, indent=2)


def is_education_related_query(query):
    """
    Check if query is related to career counseling/education for high school students
    Returns True if related, False otherwise
    """
    query_lower = query.lower()
    
    # Career and education-related keywords for high school students (Grades 8-12)
    education_keywords = [
        # Core education terms
        'study', 'studying', 'university', 'universities', 'college', 'colleges', 'education', 'student', 'students',
        'admission', 'admissions', 'apply', 'application', 'applications', 'admission guidance', 'admission queries',
        'degree', 'degrees', 'diploma', 'diplomas', 'certificate', 'certificates', 'qualification', 'qualifications',
        'masters', 'master', 'bachelor', 'bachelors', 'phd', 'doctorate', 'postgraduate', 'undergraduate',
        'course', 'courses', 'program', 'programs', 'programme', 'programmes', 'curriculum', 'curricula',
        # University and course recommendations (expanded)
        'best universities', 'top universities', 'best colleges', 'top colleges',
        'best university', 'top university', 'best college', 'top college',
        'universities for', 'colleges for', 'university for', 'college for',
        'best for', 'top for', 'recommended', 'recommendations', 'university recommendation', 'course recommendation',
        'education guidance', 'study guidance', 'academic guidance', 'career guidance', 'educational guidance',
        'global education', 'international education', 'study abroad', 'studying abroad',
        # Rankings and comparisons
        'ranking', 'rankings', 'qs ranking', 'times higher education', 'world ranking', 'university ranking',
        'compare universities', 'university comparison', 'program comparison',
        # Subject/course specific
        'computer science', 'engineering', 'business', 'medicine', 'law', 'arts', 'science',
        'mba', 'ms', 'masters', 'bachelor', 'phd', 'doctorate',
        'stem', 'humanities', 'vocational', 'professional training',
        # Program and course types
        'undergraduate program', 'graduate program', 'postgraduate program', 'diploma program', 'degree program',
        'online program', 'distance learning', 'full-time', 'part-time', 'evening program',
        'exchange program', 'semester abroad', 'gap year', 'internship', 'short-term course',
        'mooc', 'coursera', 'edx', 'online degree', 'virtual degree', 'blended learning',
        # Scholarships and financial aid
        'scholarship', 'scholarships', 'financial aid', 'grant', 'grants', 'fulbright', 'chevening', 'erasmus mundus',
        'work-study', 'budget', 'budgeting', 'tuition', 'living expenses', 'cost of living',
        # Visa and immigration
        'visa', 'visas', 'student visa', 'study permit', 'work permit', 'post-study work', 'opt', 'tier 4', 'pgwp',
        'immigration', 'permanent residency', 'pr', 'citizenship', 'settlement',
        # Cultural and adaptation
        'cultural shock', 'cultural adaptation', 'integration', 'mental health', 'diversity', 'inclusion',
        'safety', 'international network', 'networking',
        # Language and skills
        'language proficiency', 'ielts', 'toefl', 'pte', 'language test', 'preparatory course',
        'cross-cultural', 'global leadership', 'multilingual',
        # Career and post-study
        'job market', 'alumni network', 'employability', 'global certification', 'career opportunity',
        # Country-specific
        'bologna process', 'project 211', 'free education', 'low-cost education',
        # Emerging trends
        'sustainable education', 'ai in learning', 'climate-focused', 'remote work visa',
        # Accessibility
        'disability', 'lgbtq', 'underrepresented', 'accessibility', 'inclusivity',
        
        # Visa and immigration
        'visa', 'visas', 'permit', 'permits', 'immigration', 'immigrant', 'immigrate',
        'student visa', 'study permit', 'work permit', 'residence', 'residency',
        
        # Financial
        'scholarship', 'scholarships', 'tuition', 'fee', 'fees', 'cost', 'costs',
        'financial', 'funding', 'budget', 'expenses', 'expense', 'afford', 'affordable',
        'price', 'pricing', 'pay', 'payment', 'funded', 'grant', 'grants',
        
        # Accommodation and living
        'accommodation', 'housing', 'hostel', 'dorm', 'dormitory', 'rent', 'renting',
        'living', 'lifestyle', 'residence', 'residential',
        
        # Work and career
        'work', 'working', 'job', 'jobs', 'employment', 'employ', 'part-time', 'full-time',
        'career', 'salary', 'wage', 'earn', 'earning', 'income',
        
        # Countries and locations
        'abroad', 'overseas', 'international', 'country', 'countries',
        'usa', 'us', 'united states', 'america', 'american',
        'uk', 'united kingdom', 'britain', 'british', 'england', 'scotland',
        'canada', 'canadian', 'australia', 'australian', 'germany', 'german',
        'france', 'french', 'netherlands', 'dutch', 'new zealand', 'singapore',
        'sweden', 'swedish', 'europe', 'european',
        
        # Tests and requirements
        'requirements', 'requirement', 'deadline', 'deadlines', 'eligibility', 'eligible',
        'ielts', 'toefl', 'gre', 'gmat', 'sat', 'act', 'test', 'tests', 'exam', 'exams',
        'score', 'scores', 'gpa', 'grade', 'grades', 'transcript', 'transcripts',
        
        # Documents and process
        'document', 'documents', 'sop', 'statement of purpose', 'lor', 'letter of recommendation',
        'recommendation', 'cv', 'resume', 'certificate', 'certificates',
        'process', 'procedure', 'step', 'steps', 'timeline', 'timelines',
        
        # Permanent residence
        'pr', 'permanent residence', 'permanent residency', 'citizenship', 'citizen',
        'settle', 'settlement', 'migrate', 'migration',
        
        # Other related terms
        'enroll', 'enrollment', 'enrol', 'enrolment', 'register', 'registration',
        'semester', 'term', 'academic', 'academics', 'campus', 'faculty',
        'graduate', 'graduation', 'undergraduate', 'postgraduate', 'post-graduate',
        
        # Career and stream selection keywords (for high school students)
        'stream', 'streams', 'science stream', 'commerce stream', 'arts stream',
        'after 10th', 'after tenth', 'after 12th', 'after twelfth',
        'grade 8', 'grade 9', 'grade 10', 'grade 11', 'grade 12',
        'class 8', 'class 9', 'class 10', 'class 11', 'class 12',
        'career', 'careers', 'profession', 'professions', 'job', 'jobs',
        'which stream', 'what stream', 'choose stream', 'stream selection',
        'jee', 'neet', 'clat', 'nid', 'nift', 'ca', 'chartered accountant',
        'company secretary', 'cs', 'cma', 'entrance exam', 'entrance exams',
        'pcm', 'pcb', 'pcmb', 'physics chemistry math', 'physics chemistry biology',
        'psychometric', 'assessment', 'aptitude', 'interest',
        'part-time', 'part time', 'student job', 'student jobs',
        'salary', 'earning', 'income', 'pay', 'wage',
        'emerging career', 'future career', 'new career', 'trending career',
        'skill', 'skills', 'vocational', 'diploma', 'iti', 'polytechnic',
        'what should i do', 'what to do', 'which career', 'career options',
        'high school', 'school student', 'teenager', 'teen'
    ]
    
    # Check if query contains education or career-related keywords
    return any(keyword in query_lower for keyword in education_keywords)


def get_user_class_and_age(user=None):
    """
    Get user's class and approximate age from user profile
    Returns: (class_number, age_range, class_display)
    Default: class 6, age 11-12 if user not logged in or no grade set
    """
    if not user or not user.is_authenticated:
        return (6, "11-12", "Class 6")
    
    user_class = None
    class_display = "Class 6"
    age_range = "11-12"
    
    try:
        # First check UserProfile.grade
        if hasattr(user, 'user_profile') and user.user_profile:
            profile = user.user_profile
            if profile.grade:
                try:
                    user_class = int(profile.grade)
                except (ValueError, TypeError):
                    # If grade is not a number, try to extract it
                    import re
                    numbers = re.findall(r'\d+', str(profile.grade))
                    if numbers:
                        user_class = int(numbers[0])
        
        # If no grade from UserProfile, check StudentManagement
        if user_class is None:
            try:
                from institute.models import StudentManagement
                student_management = StudentManagement.objects.filter(student=user).first()
                if student_management and student_management.class_and_section:
                    class_name = student_management.class_and_section.class_and_section
                    if class_name:
                        import re
                        numbers = re.findall(r'\d+', class_name)
                        if numbers:
                            user_class = int(numbers[0])
            except Exception:
                pass
        
        # Map class to age range and display
        if user_class:
            if user_class <= 6:
                age_range = "11-12"
                class_display = f"Class {user_class}"
            elif user_class <= 8:
                age_range = "13-14"
                class_display = f"Class {user_class}"
            elif user_class == 9:
                age_range = "14-15"
                class_display = "Class 9"
            elif user_class == 10:
                age_range = "15-16"
                class_display = "Class 10"
            elif user_class == 11:
                age_range = "16-17"
                class_display = "Class 11"
            elif user_class >= 12:
                age_range = "17-18"
                class_display = "Class 12"
        else:
            # Default to class 6
            user_class = 6
            age_range = "11-12"
            class_display = "Class 6"
            
    except Exception:
        # Default to class 6 on any error
        user_class = 6
        age_range = "11-12"
        class_display = "Class 6"
    
    return (user_class, age_range, class_display)


def remove_duplicate_query_headers(response_text, query):
    """
    Remove any duplicate query headers and query text from response
    Returns cleaned response text
    """
    import re
    
    if not response_text:
        return response_text
    
    cleaned = response_text
    
    # First, remove ALL query headers (we'll add one at the end if needed)
    # Comprehensive patterns to remove query headers in various formats
    query_header_patterns = [
        # Standard query header formats (with query text)
        r'<h4>📝\s*Query:\s*</h4>\s*<p><strong>.*?</strong></p>\s*',
        r'<h4>Query:\s*</h4>\s*<p><strong>.*?</strong></p>\s*',
        r'<h3>Query:\s*</h3>\s*<p><strong>.*?</strong></p>\s*',
        r'<h2>Query:\s*</h2>\s*<p><strong>.*?</strong></p>\s*',
        r'Query:\s*<p><strong>.*?</strong></p>\s*',
        # With emoji variations
        r'<h4>📝\s*Query:\s*</h4>\s*.*?<p><strong>.*?</strong></p>\s*',
        r'<h4>.*?Query:.*?</h4>\s*<p><strong>.*?</strong></p>\s*',
        # Without strong tags
        r'<h4>📝\s*Query:\s*</h4>\s*<p>.*?</p>\s*',
        r'<h4>Query:\s*</h4>\s*<p>.*?</p>\s*',
        # Query text directly in paragraphs
        r'<p><strong>.*?Query:.*?</strong></p>\s*',
        # Just the header without content
        r'<h4>📝\s*Query:\s*</h4>\s*',
        r'<h4>Query:\s*</h4>\s*',
        r'<h3>Query:\s*</h3>\s*',
    ]
    
    # Remove ALL query headers (multiple passes to catch nested/overlapping patterns)
    for _ in range(3):  # Multiple passes to catch all variations
        for pattern in query_header_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove the actual query text if it appears verbatim at the beginning or after greeting
    if query:
        query_escaped = re.escape(query.strip())
        query_variations = [
            # Query in various HTML formats
            rf'<p><strong>{query_escaped}</strong></p>',
            rf'<strong>{query_escaped}</strong>',
            rf'<h4>.*?{query_escaped}.*?</h4>',
            rf'<h3>.*?{query_escaped}.*?</h3>',
            rf'<p>{query_escaped}</p>',
        ]
        
        for pattern in query_variations:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Also check if query appears in first 500 chars (case-insensitive)
        if len(query.strip()) > 5:
            first_500 = cleaned[:500]
            query_lower = query.lower().strip()
            first_500_lower = first_500.lower()
            
            # Check if query appears in first 500 chars
            if query_lower in first_500_lower:
                # Try to remove it more aggressively - find and remove the query text
                query_escaped_lower = re.escape(query_lower)
                patterns = [
                    rf'<p><strong>.*?{query_escaped_lower}.*?</strong></p>',
                    rf'<strong>.*?{query_escaped_lower}.*?</strong>',
                    rf'{query_escaped_lower}',
                ]
                for pattern in patterns:
                    first_500 = re.sub(pattern, '', first_500, flags=re.IGNORECASE)
                # Reconstruct response
                cleaned = first_500 + cleaned[500:]
    
    # Clean up extra whitespace and newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Max 2 consecutive newlines
    cleaned = cleaned.strip()
    
    return cleaned


def generate_ai_response(query, country=None, category=None, user=None):
    """
    Generate AI response using GPT-4o-mini with knowledge base context
    Only responds to career/education-related queries
    Checks database first (if enabled) to avoid duplicate AI calls
    Adapts response style based on user's age/class
    """
    # Get user's class for personalized message
    user_class, age_range, class_display = get_user_class_and_age(user)
    
    # Validate query is career/education-related
    if not is_education_related_query(query):
        greeting = "Hi there! 😊" if user_class <= 8 else "Hello! 👋"
        return (
            f"{greeting} I'm sorry, but I'm here only to help with career advice for students. "
            "Can you ask something about choosing a job or studying for it?\n\n"
            "I can help you with:\n"
            "• Understanding different jobs and careers\n"
            "• What subjects to study in school\n"
            "• Which courses to pursue after class 10 or 12\n"
            "• Entrance exams and colleges\n"
            "• Skills needed for different careers\n"
            "• Study abroad opportunities\n"
            "• Career planning and goal setting\n\n"
            "What would you like to know about careers? 🎯",
            0.0
        )
    
    # STEP 1: Check database for similar queries (if enabled)
    # This can be disabled via USE_DATABASE_CACHE setting
    use_db_cache = getattr(settings, 'USE_DATABASE_CACHE', True)
    
    if use_db_cache:
        similarity_threshold = getattr(settings, 'SEMANTIC_SIMILARITY_THRESHOLD', 0.85)
        db_response, _ = find_similar_query(query, similarity_threshold=similarity_threshold)
        if db_response:
            # Remove any existing query header from cached response to prevent duplication
            import re
            
            # Comprehensive patterns to remove query headers
            query_header_patterns = [
                r'<h4>📝\s*Query:\s*</h4>\s*<p><strong>.*?</strong></p>\s*',
                r'<h4>Query:\s*</h4>\s*<p><strong>.*?</strong></p>\s*',
                r'<h3>Query:\s*</h3>\s*<p><strong>.*?</strong></p>\s*',
                r'<h2>Query:\s*</h2>\s*<p><strong>.*?</strong></p>\s*',
                r'Query:\s*<p><strong>.*?</strong></p>\s*',
                r'<h4>📝\s*Query:\s*</h4>\s*.*?<p><strong>.*?</strong></p>\s*',
                r'<h4>.*?Query:.*?</h4>\s*<p><strong>.*?</strong></p>\s*',
                r'<h4>📝\s*Query:\s*</h4>\s*<p>.*?</p>\s*',
                r'<h4>Query:\s*</h4>\s*<p>.*?</p>\s*',
                r'<p><strong>.*?Query:.*?</strong></p>\s*',
            ]
            
            cleaned_response = db_response
            for pattern in query_header_patterns:
                cleaned_response = re.sub(pattern, '', cleaned_response, flags=re.IGNORECASE | re.DOTALL)
            
            # Also remove the actual query text if it appears verbatim
            query_escaped = re.escape(query.strip())
            query_variations = [
                rf'^\s*<p><strong>{query_escaped}</strong></p>\s*',
                rf'^\s*<strong>{query_escaped}</strong>\s*',
                rf'^\s*{query_escaped}\s*',
            ]
            
            for pattern in query_variations:
                cleaned_response = re.sub(pattern, '', cleaned_response, flags=re.IGNORECASE | re.MULTILINE)
            
            cleaned_response = cleaned_response.strip()
            
            # Check if query header already exists before adding
            has_query_header = bool(re.search(r'<h[234]>.*?Query:.*?</h[234]>', cleaned_response, re.IGNORECASE))
            
            if not has_query_header:
                # Only add query header if it doesn't already exist
                formatted_response = f'<h4>📝 Query:</h4>\n<p><strong>{query}</strong></p>\n\n{cleaned_response}'
            else:
                # If header exists, just return cleaned response
                formatted_response = cleaned_response
            
            return formatted_response, 0.0
    
    # STEP 2: Check cache (temporary cache for same session)
    cache_key = f"ai_response_{hash(query)}"
    cached_response = cache.get(cache_key)
    if cached_response:
        # Cached response is a tuple (response_text, cost)
        if isinstance(cached_response, tuple):
            response_text, cost = cached_response
        else:
            response_text = cached_response
            cost = 0.0
        
        # Remove any duplicate query headers from cached response
        cleaned_text = remove_duplicate_query_headers(response_text, query)
        
        # Check if query header already exists
        import re
        has_query_header = bool(re.search(r'<h[234]>.*?Query:.*?</h[234]>', cleaned_text, re.IGNORECASE))
        
        if not has_query_header:
            cleaned_text = f'<h4>📝 Query:</h4>\n<p><strong>{query}</strong></p>\n\n{cleaned_text}'
        
        return cleaned_text, cost
    
    # Get OpenAI API key
    api_key = settings.OPENAI_API_KEY
    if not api_key or api_key.strip() == '':
        error_message = "Error: OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
        
        # Show error in server console when DEBUG is True
        if getattr(settings, 'DEBUG', False):
            print("\n" + "="*80)
            print("⚠️  OPENAI API KEY ERROR")
            print("="*80)
            print(f"Error: {error_message}")
            print("\nTo fix this:")
            print("1. Open your .env file")
            print("2. Add: OPENAI_API_KEY=your_api_key_here")
            print("3. Get your API key from: https://platform.openai.com/api-keys")
            print("4. Restart your Django development server")
            print("="*80 + "\n")
        
        return (error_message, 0.0)
    
    # Extract entities if not provided
    if not country or not category:
        extracted_country, extracted_category = extract_entities(query)
        country = country or extracted_country
        category = category or extracted_category
    
    # Get knowledge base context
    kb_context = get_knowledge_base_context(query, country, category)
    
    # Get user's class and age for age-appropriate responses
    user_class, age_range, class_display = get_user_class_and_age(user)
    
    # Determine age-appropriate language and examples based on class
    if user_class <= 8:
        # Younger students (Class 6-8, ages 11-14)
        language_style = "very simple and friendly, like talking to a younger friend"
        example_complexity = "simple, relatable examples from their daily life"
        detail_level = "basic concepts, avoid too much technical detail"
        encouragement_tone = "very encouraging and supportive, like a friendly teacher"
        greeting_style = "Hi there! 😊"
    elif user_class <= 10:
        # Middle school students (Class 9-10, ages 14-16)
        language_style = "clear and friendly, like chatting with a friend"
        example_complexity = "practical examples they can relate to"
        detail_level = "moderate detail, explain concepts clearly"
        encouragement_tone = "encouraging and positive, like a supportive counselor"
        greeting_style = "Hello! 👋"
    else:
        # High school students (Class 11-12, ages 16-18)
        language_style = "professional yet friendly, like a career counselor"
        example_complexity = "detailed, real-world examples"
        detail_level = "comprehensive information with specifics"
        encouragement_tone = "professional and supportive, like a mentor"
        greeting_style = "Hello! 👋"
    
    # Build optimized prompt with age-appropriate tone based on reference
    prompt = f"""You are TopTeen Career AI, a helpful guide designed for school students from class 6 and above (ages 11 and up). You are currently helping a student in {class_display} (approximately {age_range} years old). Your role is to assist with career choices, helping students explore options in their home country (like India, if that's where they live) and abroad (in other countries around the world). 

IMPORTANT: Adapt your language and examples to match the student's age level. Use {language_style}. Provide {example_complexity}. Give {detail_level}. Be {encouragement_tone}. Start with a friendly greeting like "{greeting_style}"

You cover all areas of choosing a career, such as:

1. Understanding different jobs and fields (like engineering, medicine, arts, business, technology, teaching, sports, and more).
2. Education paths: What subjects to study in school, which courses or degrees to pursue after class 10 or 12, entrance exams, colleges, or universities.
3. Skills needed: What abilities or hobbies can lead to certain careers, and how to build them.
4. Pros and cons: Benefits like salary, job satisfaction, work-life balance, and challenges like competition or travel.
5. Opportunities at home vs. abroad: Jobs in the home country, moving to other countries for study or work, visas, cultural differences, and success stories.
6. Steps to get started: Goal setting, internships, online resources, talking to mentors, or career tests.

Always explain things in simple, easy-to-understand language, like you're chatting with a friend. Use short sentences, avoid big words, and give examples to make it clear. Be professional (like a teacher or counselor) and polite—start with a friendly greeting, encourage the student, and end positively.

BOUNDARIES: Only answer questions related to career choices, education for careers, or skills for jobs in the home country or abroad. If a query is not about careers (like homework in math, personal problems, games, or anything unrelated), politely say: "I'm sorry, but I'm here only to help with career advice for students. Can you ask something about choosing a job or studying for it?" Do not give advice on illegal activities, harmful ideas, or topics outside careers. If unsure, ask for more details to keep it on track.

RESPOND STEP BY STEP: 1. Understand the question. 2. Give clear info with examples. 3. Suggest next steps. 4. Ask if they have more questions. Keep answers helpful, encouraging, and fun!

DETAILED AREAS YOU COVER:

1. Stream Selection After 10th:
   - Guide students on choosing between Science, Commerce, and Arts streams
   - Subject combinations and their career implications
   - Career options available in each stream
   - Factors to consider: interests, strengths, career goals, family background
   - Age-appropriate advice for Grade 10 students

2. Career Options by Stream:
   - Science Stream: Engineering, Medicine, Research, Data Science, AI/ML, etc.
   - Commerce Stream: CA, CS, CMA, Finance, Business, Economics, etc.
   - Arts Stream: Design, Psychology, Law, Journalism, Teaching, etc.
   - Vocational courses and skill-based careers
   - Emerging careers across all streams

3. Entrance Exam Guidance:
   - JEE (Main & Advanced) for engineering
   - NEET for medical courses
   - CLAT for law
   - NID/NIFT for design
   - CA Foundation, CS Foundation for commerce
   - Preparation strategies and timelines
   - Alternative paths without competitive exams

4. Study Abroad After 12th:
   - Requirements for studying abroad (SAT, IELTS, TOEFL, etc.)
   - Country-specific guidance (USA, UK, Canada, Australia, etc.)
   - Scholarships and financial aid for international students
   - Visa processes and post-study work opportunities
   - Cost comparisons and budgeting

5. Emerging Careers and Future Jobs:
   - AI/ML careers, Data Science, Cybersecurity
   - Climate and sustainability careers
   - Digital marketing, Content creation
   - Prompt engineering, AI ethics
   - Job market trends and growth sectors

6. Part-time Work and Skill Development:
   - Part-time job options for students (online tutoring, content writing, etc.)
   - Skills to develop alongside studies
   - Building a portfolio and work experience
   - Time management for students

7. College and University Selection:
   - Top colleges in India for different streams
   - Factors to consider: location, fees, placement, infrastructure
   - Government vs private colleges
   - Distance learning and online degree options

8. Psychometric Assessment Integration:
   - How assessment results relate to career choices
   - Personality-based career matching
   - Interest-based stream and career recommendations

9. Career Planning and Timeline:
   - What to do in 9th-10th grade
   - 11th-12th grade preparation
   - Post-12th options and pathways
   - Long-term career planning

10. Vocational and Skill-Based Careers:
    - Diploma courses and certifications
    - ITI, polytechnic courses
    - Skill development programs
    - Apprenticeship opportunities

11. Salary and Career Growth:
    - Realistic salary expectations for different careers
    - Career growth paths and progression
    - Industry trends and future demand
    - High-paying careers without competitive exams

12. Parent-Student Guidance:
    - How parents can support career decisions
    - Balancing parental expectations with student interests
    - Financial planning for education

13. Special Needs and Alternative Paths:
    - Careers for students who don't want traditional paths
    - Options without competitive exams
    - Skill-based careers and entrepreneurship
    - Part-time and flexible career options

AGE-APPROPRIATE GUIDANCE:
- For Class 6-8 students ({age_range} years): Keep explanations very simple, use lots of examples, focus on exploring interests and basic career concepts
- For Class 9-10 students (14-16 years): Provide clear explanations with practical examples, help them understand stream selection and career paths
- For Class 11-12 students (16-18 years): Give detailed, comprehensive information with real-world examples, help with specific career decisions and planning

LANGUAGE STYLE:
- Use {language_style}
- Keep sentences short and clear
- Avoid jargon - if you must use technical terms, explain them simply
- Use examples that students can relate to
- Be encouraging and positive throughout

Question: {query}

Knowledge Base Context:
{kb_context}

Please provide a comprehensive, professional answer following these guidelines:

FORMATTING REQUIREMENTS:
1. Use emojis strategically to enhance readability (🤖 for AI analysis, 📋 for requirements, 💰 for costs, ✅ for confirmations, ⚠️ for warnings, 🎯 for recommendations, etc.)
2. Structure your response with clear sections using HTML headings:
   - Start with a brief AI analysis section (🤖 AI ANALYSIS)
   - Use 📋 for requirements/checklists
   - Use 💰 for cost information
   - Use ✅ for confirmations/positive information
   - Use ⚠️ for important warnings or conditions
   - Use 🎯 for recommendations
   - Use 📊 for statistics/data
3. Format with clear HTML headings (h4, h5) and well-organized bullet points
4. Use tables for structured data when appropriate (costs, comparisons, timelines)

RESPONSE STRUCTURE (Following TopTeen Career AI Guidelines):
1. Start with a friendly greeting (e.g., "Hi there! 😊" or "Hello! 👋")
2. Then provide a summary of the query to show understanding (DO NOT repeat the exact query text verbatim)
3. Address the question directly and thoroughly with specific, accurate information
4. Provide detailed information with pros/cons where relevant
5. Include age-appropriate examples and real-world scenarios
6. Suggest next steps or resources (e.g., official websites, career counseling, psychometric assessments)
7. End with an encouraging message and offer for follow-up questions

CRITICAL: Do NOT include the user's query text verbatim anywhere in your response. Do NOT start with "Query:" or repeat the question. The system will automatically add the query header. Just start with a greeting like "Hi there! 😊" and then answer the question naturally without repeating it.

CONTENT REQUIREMENTS:
1. Use specific data from the knowledge base when available - cite specific numbers, dates, and requirements
2. Include relevant details: costs (with ranges), requirements (complete lists), timelines, processes, deadlines
3. If data might be outdated, recommend verifying with official sources
4. Never provide legal or financial advice—direct users to professionals
5. Stay neutral on political topics and promote ethical practices like avoiding fraudulent agents

SPECIFIC QUERY TYPE GUIDELINES:

For stream selection queries:
- Explain differences between Science, Commerce, and Arts streams
- Subject combinations and their career implications
- Factors to consider: interests, strengths, career goals
- Career options available in each stream
- Age-appropriate guidance for Grade 10 students

For career option queries:
- List careers available in the chosen stream
- Salary ranges, growth prospects, and job market demand
- Education requirements and pathways
- Entrance exams needed (if any)
- Alternative paths without competitive exams
- Pros and cons of different career options

For entrance exam queries:
- Exam pattern, syllabus, and preparation strategy
- Timeline for preparation (when to start)
- Study materials and resources
- Coaching vs self-study options
- Alternative paths if not interested in competitive exams

For college/university queries (e.g., "Best colleges for engineering?", "Top commerce colleges?", "Good arts colleges?"):
   - Provide a comprehensive list of top colleges in India for the specific course/stream
   - Include both government and private options
   - Mention key strengths, rankings, and specializations
   - Include admission requirements, entrance exams, and cutoffs
   - Discuss factors like placement records, infrastructure, faculty
   - Compare different colleges with pros/cons
   - Include cost comparisons (government vs private)
   - Suggest resources like official college websites and admission portals

For study abroad queries (after 12th):
- Explain requirements for studying abroad (SAT, IELTS, TOEFL, etc.)
- Country-specific guidance (USA, UK, Canada, Australia, etc.)
- Application processes and timelines
- Cost breakdowns and scholarship opportunities
- Visa processes and post-study work options
- Suggest official embassy websites and study abroad portals

For part-time work queries:
- Age-appropriate part-time job options for students
- Online work opportunities (tutoring, content writing, etc.)
- Legal guidelines and time management
- Skills development through part-time work
- Earning potential and career benefits

For career planning queries:
- Step-by-step career planning for different grades
- Timeline for preparation and decision-making
- Skills to develop at each stage
- How to explore career interests
- Connecting interests to career options

For emerging careers queries:
- Explain new and growing career fields (AI, Data Science, Climate, etc.)
- Education requirements and pathways
- Job market demand and growth projections
- Skills needed and how to develop them
- Pros/cons and realistic expectations

For vocational/skill-based queries:
- Diploma courses and certifications available
- ITI, polytechnic, and skill development programs
- Career outcomes and salary expectations
- Comparison with degree programs
- How to choose the right vocational course

For alternative path queries (without competitive exams):
- Careers that don't require JEE/NEET/CLAT
- Professional courses (CA, CS, CMA, etc.)
- Skill-based careers and freelancing
- Entrepreneurship options
- Part-time work and side hustles

RESPONSE TONE:
- Start with a friendly greeting: "{greeting_style}"
- Be {encouragement_tone}
- Use {language_style}
- Provide {example_complexity}
- Give {detail_level}
- End positively with encouragement and an offer to help with more questions
- Always end with something like: "I hope this helps! Feel free to ask me any other questions about careers. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯"

EXAMPLE FORMAT (Note: The system will automatically add the query header, so you don't need to include it):

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: [Admission/Work Rights/Costs/etc.]<br>
Country: [Country]<br>
Course: [If applicable]</p>

<h4>📋 COMPLETE REQUIREMENTS</h4>
<ul>
<li>Requirement 1</li>
<li>Requirement 2</li>
</ul>

<h4>💰 COST BREAKDOWN</h4>
<ul>
<li>Tuition: [range]</li>
<li>Living: [range]</li>
<li>Total: [range]</li>
</ul>

Format your response in clean HTML with proper headings, lists, and strategic emoji usage. Be professional, clear, helpful, and always maintain a courteous demeanor."""

    try:
        # Call OpenAI API with configured model (default: GPT-4o-mini)
        model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        
        # Initialize OpenAI client
        try:
            client = openai.OpenAI(api_key=api_key)
        except Exception as e:
            # Handle API key validation errors during client initialization
            error_msg = f"Error initializing OpenAI client: {str(e)}"
            
            # Show error in server console when DEBUG is True
            if getattr(settings, 'DEBUG', False):
                print("\n" + "="*80)
                print("⚠️  OPENAI CLIENT INITIALIZATION ERROR")
                print("="*80)
                print(f"Error: {str(e)}")
                print("\nThis error occurred while initializing the OpenAI client.")
                print("Possible causes:")
                print("  - Invalid or malformed API key")
                print("  - API key is missing")
                print("  - OpenAI library version issue")
                print("\nTo fix:")
                print("1. Verify OPENAI_API_KEY in your .env file")
                print("2. Check API key format (should start with 'sk-')")
                print("3. Get a valid key from: https://platform.openai.com/api-keys")
                print("4. Update OpenAI library: pip install --upgrade openai")
                print("5. Restart your Django development server")
                print("="*80 + "\n")
            
            return (error_msg, 0.0)
        
        # Make API call with age-appropriate system message
        user_class, age_range, class_display = get_user_class_and_age(user)
        system_message = f"""You are TopTeen Career AI, a helpful guide designed for school students from class 6 and above (ages 11 and up). You are currently helping a student in {class_display} (approximately {age_range} years old). 

Your role is to assist with career choices, helping students explore options in their home country (like India) and abroad. Always explain things in simple, easy-to-understand language, like you're chatting with a friend. Use short sentences, avoid big words, and give examples to make it clear. Be professional (like a teacher or counselor) and polite—start with a friendly greeting, encourage the student, and end positively.

Only answer questions related to career choices, education for careers, or skills for jobs. If a query is not about careers, politely redirect. Respond step by step: 1. Understand the question. 2. Give clear info with examples. 3. Suggest next steps. 4. Ask if they have more questions. Keep answers helpful, encouraging, and fun!"""

        from core.llm_quota import LLMQuotaExceeded, ensure_can_use_llm

        try:
            ensure_can_use_llm(user, feature="forum")
        except LLMQuotaExceeded as exc:
            # Surface as a friendly HTML answer so existing forum UI can show it
            pay = exc.payload or {}
            cta = pay.get("cta_url") or "/ai-tokens/"
            label = pay.get("cta_label") or "Recharge AI tokens"
            return (
                f"<h4>{pay.get('headline') or 'AI token limit reached'}</h4>"
                f"<p>{pay.get('body') or pay.get('detail') or ''}</p>"
                f"<p><a href=\"{cta}\">{label}</a></p>",
                0.0,
            )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": system_message
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,  # Balanced creativity and consistency
            max_tokens=800,  # Limit to control costs
        )
        
        ai_response = response.choices[0].message.content
        
        # Clean markdown code blocks if present (OpenAI sometimes wraps HTML in ```html blocks)
        if ai_response.startswith('```html'):
            ai_response = ai_response.replace('```html\n', '').replace('```html', '')
        if ai_response.endswith('```'):
            ai_response = ai_response.rsplit('```', 1)[0]
        ai_response = ai_response.strip()
        
        # Remove any existing query header from AI response to prevent duplication
        ai_response = remove_duplicate_query_headers(ai_response, query)
        
        # Check if query header already exists before adding
        import re
        has_query_header = bool(re.search(r'<h[234]>.*?Query:.*?</h[234]>', ai_response, re.IGNORECASE))
        
        if not has_query_header:
            # Only add query header if it doesn't already exist
            ai_response = f'<h4>📝 Query:</h4>\n<p><strong>{query}</strong></p>\n\n{ai_response}'
        
        # Calculate approximate cost (GPT-4o-mini: $0.15/1M input, $0.60/1M output)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = (input_tokens * 0.15 / 1_000_000) + (output_tokens * 0.60 / 1_000_000)

        try:
            from core.llm_billing import log_openai_response
            log_openai_response(
                feature='forum',
                response=response,
                model=model,
                call_type='chat',
                user=user,
                consume=True,
                metadata={'source': 'forum.generate_ai_response'},
            )
        except Exception:
            pass
        
        # Cache response for 24 hours (save money on similar queries)
        cache.set(cache_key, (ai_response, cost), 86400)
        
        return ai_response, cost
        
    except openai.APIError as e:
        error_msg = f"Error calling OpenAI API: {str(e)}"
        
        # Show detailed error in server console when DEBUG is True
        if getattr(settings, 'DEBUG', False):
            print("\n" + "="*80)
            print("⚠️  OPENAI API ERROR")
            print("="*80)
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            
            # Check for common API key related errors
            error_str = str(e).lower()
            if 'api key' in error_str or 'authentication' in error_str or 'invalid' in error_str:
                print("\n🔑 This appears to be an API key authentication error.")
                print("Possible causes:")
                print("  - OPENAI_API_KEY is missing or incorrect in .env file")
                print("  - API key has been revoked or expired")
                print("  - API key doesn't have required permissions")
                print("\nTo fix:")
                print("1. Check your .env file for OPENAI_API_KEY")
                print("2. Verify the key is correct at: https://platform.openai.com/api-keys")
                print("3. Ensure the key has access to the model you're using")
                print("4. Restart your Django development server")
            
            print("="*80 + "\n")
        
        return error_msg, 0.0
    except TypeError as e:
        # Handle client initialization errors
        error_msg = f"Error initializing OpenAI client: {str(e)}. Please check your OpenAI library version."
        
        # Show error in server console when DEBUG is True
        if getattr(settings, 'DEBUG', False):
            print("\n" + "="*80)
            print("⚠️  OPENAI CLIENT INITIALIZATION ERROR")
            print("="*80)
            print(f"Error: {str(e)}")
            print("\nPossible causes:")
            print("  - OpenAI library version mismatch")
            print("  - Missing or incorrect API key")
            print("\nTo fix:")
            print("1. Update OpenAI library: pip install --upgrade openai")
            print("2. Check your .env file for OPENAI_API_KEY")
            print("3. Restart your Django development server")
            print("="*80 + "\n")
        
        return error_msg, 0.0
    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        
        # Show full traceback in server console when DEBUG is True
        if getattr(settings, 'DEBUG', False):
            import traceback
            print("\n" + "="*80)
            print("⚠️  UNEXPECTED ERROR IN AI SERVICE")
            print("="*80)
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Message: {str(e)}")
            print("\nFull Traceback:")
            print(traceback.format_exc())
            print("="*80 + "\n")
        
        return error_msg, 0.0
