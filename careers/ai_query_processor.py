"""
AI Query Processor for Careers - Works without AI, optional AI enhancement
Supports OpenAI and Google Gemini with embedding caching
"""
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q
from django.urls import reverse
from django.core.cache import cache
from .models import Career, Skill, Profession, CareerCluster
from django.utils.html import strip_tags
import re
import json
import logging
import numpy as np
import hashlib

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Process natural language queries with optional AI enhancement"""
    
    def __init__(self):
        self.use_ai = getattr(settings, 'ENABLE_AI_FEATURES', False)
        self.use_ai_summaries = getattr(settings, 'ENABLE_AI_SUMMARIES', False)
        self.use_semantic_search = getattr(settings, 'ENABLE_SEMANTIC_SEARCH', False)
        self.enable_embedding_cache = getattr(settings, 'ENABLE_EMBEDDING_CACHE', True)
        self.embedding_cache_ttl = getattr(settings, 'EMBEDDING_CACHE_TTL', 86400)
        self.query_cache_ttl = getattr(settings, 'QUERY_EMBEDDING_CACHE_TTL', 3600)
        self.ai_client = None
        self.ai_provider = None
        self.embedding_model = None
        
        if self.use_ai or self.use_semantic_search:
            self._init_ai_client()
    
    def _init_ai_client(self):
        """Initialize AI client if enabled - supports OpenAI and Gemini"""
        provider = getattr(settings, 'AI_PROVIDER', 'none')
        self.ai_provider = provider
        
        if provider == 'openai':
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if api_key:
                try:
                    import openai
                    self.ai_client = openai.OpenAI(api_key=api_key)
                    self.embedding_model = "text-embedding-3-small"
                    logger.info("AI client initialized (OpenAI)")
                except ImportError:
                    logger.warning("OpenAI package not installed, falling back to rule-based")
                    self.use_ai = False
                    self.use_semantic_search = False
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI client: {e}, falling back to rule-based")
                    self.use_ai = False
                    self.use_semantic_search = False
            else:
                logger.warning("OpenAI API key not provided")
                self.use_ai = False
                self.use_semantic_search = False
                
        elif provider == 'gemini':
            api_key = getattr(settings, 'GOOGLE_API_KEY', None)
            if api_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    self.ai_client = genai
                    self.embedding_model = "models/text-embedding-004"  # Gemini embedding model
                    logger.info("AI client initialized (Google Gemini)")
                except ImportError:
                    logger.warning("google-generativeai package not installed, falling back to rule-based")
                    self.use_ai = False
                    self.use_semantic_search = False
                except Exception as e:
                    logger.warning(f"Failed to initialize Gemini client: {e}, falling back to rule-based")
                    self.use_ai = False
                    self.use_semantic_search = False
            else:
                logger.warning("Google API key not provided")
                self.use_ai = False
                self.use_semantic_search = False
        else:
            self.use_ai = False
            self.use_semantic_search = False
    
    def _progress(self, progress_callback, message):
        if progress_callback and callable(progress_callback):
            try:
                progress_callback(message)
            except Exception:
                pass

    def process_query(self, query, progress_callback=None):
        """
        Process query - uses semantic search, AI, or rule-based parsing
        Returns: dict with 'criteria', 'careers', 'method'
        progress_callback(message): optional, called with actual progress messages (no repeat).
        """
        # Try semantic search ONLY if explicitly enabled in env
        if self.use_semantic_search:
            has_cache = self.has_cached_embeddings()
            if self.ai_client or has_cache:
                try:
                    logger.info("Using semantic search (ENABLE_SEMANTIC_SEARCH=True)")
                    result = self._process_with_semantic_search(query, progress_callback)
                    return result
                except Exception as e:
                    logger.error(f"Semantic search failed: {e}, falling back to AI/rule-based")
            else:
                logger.warning("Semantic search enabled but no API key or cached embeddings. Run 'python manage.py generate_career_embeddings'")
        
        # Try AI-enhanced processing if enabled
        if self.use_ai:
            if self.ai_client:
                try:
                    logger.info("Using AI-enhanced search (ENABLE_AI_FEATURES=True)")
                    return self._process_with_ai(query, progress_callback)
                except Exception as e:
                    logger.error(f"AI processing failed: {e}, falling back to rule-based")
                    return self._process_rule_based(query, progress_callback)
            else:
                logger.warning("AI client not available (check API keys)")
        
        logger.info("Using rule-based search (no AI features enabled or API key missing)")
        return self._process_rule_based(query, progress_callback)
    
    def _process_rule_based(self, query, progress_callback=None):
        """
        Rule-based query processing - works without any AI
        """
        self._progress(progress_callback, "Searching careers...")
        query_lower = query.lower().strip()

        # Extract intent and criteria
        criteria = {
            'keywords': [],
            'skills': [],
            'interests': [],
            'salary_range': None,
            'education_level': None,
            'professions': [],
            'clusters': []
        }
        
        # Extract meaningful keywords (filter out common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'what', 'show', 'me', 'careers', 'career', 'for', 'jobs', 'job'}
        words = re.findall(r'\b\w+\b', query_lower)
        criteria['keywords'] = [w for w in words if len(w) > 2 and w not in stop_words]
        
        # Pattern matching for common intents
        creative_keywords = ['creative', 'art', 'design', 'music', 'writing', 'artist', 'painter', 'writer', 'musician']
        if any(word in query_lower for word in creative_keywords):
            criteria['interests'].append('creative')
        
        tech_keywords = ['tech', 'technology', 'software', 'programming', 'coding', 'developer', 'engineer', 'computer', 'it', 'information']
        if any(word in query_lower for word in tech_keywords):
            criteria['interests'].append('technology')
        
        medical_keywords = ['medical', 'doctor', 'nurse', 'health', 'healthcare', 'medicine', 'hospital']
        if any(word in query_lower for word in medical_keywords):
            criteria['interests'].append('medical')
        
        business_keywords = ['business', 'management', 'marketing', 'sales', 'finance', 'accounting', 'entrepreneur']
        if any(word in query_lower for word in business_keywords):
            criteria['interests'].append('business')
        
        # Salary intent
        if any(word in query_lower for word in ['high', 'paying', 'salary', 'income', 'earn', 'money', 'lucrative']):
            criteria['salary_range'] = 'high'
        elif any(word in query_lower for word in ['low', 'entry', 'starting']):
            criteria['salary_range'] = 'low'
        
        # Education level
        if any(word in query_lower for word in ['degree', 'bachelor', 'master', 'phd', 'doctorate', 'graduate']):
            criteria['education_level'] = 'higher'
        elif any(word in query_lower for word in ['diploma', 'certificate', 'vocational']):
            criteria['education_level'] = 'vocational'
        
        # Match against database
        # Note: career_cluster is ManyToManyField, so use prefetch_related, not select_related
        # profession is a reverse ForeignKey (one-to-many), so also use prefetch_related
        careers = Career.objects.filter(publish_status=1).prefetch_related(
            'skills', 'career_cluster', 'profession', 'prospective_employment_areas', 'courses'
        )
        
        # Build Q objects for matching
        q_objects = Q()
        
        # Keyword matching across multiple fields
        if criteria['keywords']:
            for keyword in criteria['keywords']:
                q_objects |= Q(name__icontains=keyword)
                q_objects |= Q(summary__icontains=keyword)
                q_objects |= Q(skills__name__icontains=keyword)
                q_objects |= Q(profession__name__icontains=keyword)
                q_objects |= Q(career_cluster__name__icontains=keyword)
        
        # Interest-based matching via clusters
        if 'creative' in criteria['interests']:
            creative_clusters = CareerCluster.objects.filter(
                Q(name__icontains='art') | Q(name__icontains='design') | Q(name__icontains='creative')
            ).values_list('id', flat=True)
            if creative_clusters:
                q_objects |= Q(career_cluster__id__in=creative_clusters)
        
        if 'technology' in criteria['interests']:
            tech_clusters = CareerCluster.objects.filter(
                Q(name__icontains='technology') | Q(name__icontains='computer') | Q(name__icontains='engineering')
            ).values_list('id', flat=True)
            if tech_clusters:
                q_objects |= Q(career_cluster__id__in=tech_clusters)
        
        if 'medical' in criteria['interests']:
            medical_clusters = CareerCluster.objects.filter(
                Q(name__icontains='health') | Q(name__icontains='medical')
            ).values_list('id', flat=True)
            if medical_clusters:
                q_objects |= Q(career_cluster__id__in=medical_clusters)
        
        if 'business' in criteria['interests']:
            business_clusters = CareerCluster.objects.filter(
                Q(name__icontains='business') | Q(name__icontains='commerce') | Q(name__icontains='management')
            ).values_list('id', flat=True)
            if business_clusters:
                q_objects |= Q(career_cluster__id__in=business_clusters)
        
        # Apply filters
        if q_objects:
            careers = careers.filter(q_objects).distinct()
        
        # Salary filtering - salary is stored in Profession model, not Career
        # For high-paying careers, we'll boost their score in the relevance scoring instead
        # This avoids the need to filter by a non-existent field
        
        # Score and rank by relevance
        scored_careers = self._score_careers_by_relevance(list(careers), criteria, query_lower)
        
        # Return top 5 most relevant
        return {
            'criteria': criteria,
            'careers': scored_careers[:5],
            'method': 'rule_based'
        }
    
    def _process_with_ai(self, query, progress_callback=None):
        """
        AI-enhanced processing using OpenAI or Gemini
        Falls back to rule-based if AI fails
        """
        try:
            self._progress(progress_callback, "Retrieving from AI...")
            # Use AI to extract search criteria from natural language query
            system_prompt = """You are a career search assistant. Extract search criteria from user queries about careers.
Return a JSON object with these fields:
- keywords: list of important keywords from the query
- interests: list of interest areas (e.g., 'creative', 'technology', 'medical', 'business')
- salary_range: 'high', 'low', or null
- education_level: 'higher', 'vocational', or null
- clusters: list of career cluster names mentioned (e.g., 'Arts', 'Engineering', 'Healthcare')

Only return valid JSON, no other text."""

            user_prompt = f"Extract search criteria from this career query: {query}"
            
            if self.ai_provider == 'openai':
                response = self.ai_client.chat.completions.create(
                    model=getattr(settings, 'AI_MODEL', 'gpt-3.5-turbo'),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                ai_response = response.choices[0].message.content.strip()
                
            elif self.ai_provider == 'gemini':
                model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
                model = self.ai_client.GenerativeModel(model_name)
                response = model.generate_content(
                    f"{system_prompt}\n\n{user_prompt}",
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 200,
                    }
                )
                ai_response = response.text.strip()
            else:
                return self._process_rule_based(query)
            
            # Parse AI response
            # Remove markdown code blocks if present
            if ai_response.startswith('```'):
                ai_response = ai_response.split('```')[1]
                if ai_response.startswith('json'):
                    ai_response = ai_response[4:]
                ai_response = ai_response.strip()

            criteria = json.loads(ai_response)
            self._progress(progress_callback, "Searching careers...")

            # Build query using AI-extracted criteria
            careers = Career.objects.filter(publish_status=1).prefetch_related(
                'skills', 'career_cluster', 'profession', 'prospective_employment_areas', 'courses'
            )
            q_objects = Q()
            
            # Keyword matching
            if criteria.get('keywords'):
                for keyword in criteria['keywords']:
                    q_objects |= Q(name__icontains=keyword)
                    q_objects |= Q(summary__icontains=keyword)
                    q_objects |= Q(skills__name__icontains=keyword)
                    q_objects |= Q(profession__name__icontains=keyword)
                    q_objects |= Q(career_cluster__name__icontains=keyword)
            
            # Interest-based matching via clusters
            if criteria.get('interests'):
                cluster_filters = Q()
                for interest in criteria['interests']:
                    if interest == 'creative':
                        cluster_filters |= Q(career_cluster__name__icontains='art') | Q(career_cluster__name__icontains='design') | Q(career_cluster__name__icontains='creative')
                    elif interest == 'technology':
                        cluster_filters |= Q(career_cluster__name__icontains='technology') | Q(career_cluster__name__icontains='computer') | Q(career_cluster__name__icontains='engineering')
                    elif interest == 'medical':
                        cluster_filters |= Q(career_cluster__name__icontains='health') | Q(career_cluster__name__icontains='medical')
                    elif interest == 'business':
                        cluster_filters |= Q(career_cluster__name__icontains='business') | Q(career_cluster__name__icontains='commerce') | Q(career_cluster__name__icontains='management')
                if cluster_filters:
                    q_objects |= cluster_filters
            
            # Cluster name matching
            if criteria.get('clusters'):
                cluster_names = criteria['clusters']
                cluster_ids = CareerCluster.objects.filter(
                    name__in=cluster_names
                ).values_list('id', flat=True)
                if cluster_ids:
                    q_objects |= Q(career_cluster__id__in=cluster_ids)
            
            # Apply filters
            if q_objects:
                careers = careers.filter(q_objects).distinct()
            
            # Score and rank by relevance
            query_lower = query.lower()
            scored_careers = self._score_careers_by_relevance(list(careers), criteria, query_lower)
            
            # Return top 5 most relevant
            return {
                'criteria': criteria,
                'careers': scored_careers[:5],
                'method': 'ai'
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}, falling back to rule-based")
            return self._process_rule_based(query, progress_callback)
        except Exception as e:
            logger.error(f"AI processing error: {e}, falling back to rule-based")
            return self._process_rule_based(query, progress_callback)
    
    def _process_with_semantic_search(self, query, progress_callback=None):
        """
        Semantic search using stored embeddings: one query for (career_id, embedding),
        compute similarity, load only top-K careers for hybrid scoring and response.
        """
        from .models import CareerEmbedding
        try:
            self._progress(progress_callback, "Loading from memory...")
            try:
                query_embedding = self._get_embedding(query, is_query=True)
            except ValueError as e:
                logger.warning(f"Cannot generate query embedding: {e}")
                return self._process_with_cached_embeddings_only(query, progress_callback)

            self._progress(progress_callback, "Searching careers...")
            # Single query: all (career_id, embedding) for this provider/model
            provider = self.ai_provider or 'openai'
            model_name = self.embedding_model or 'text-embedding-3-small'
            rows = list(
                CareerEmbedding.objects.filter(
                    provider=provider,
                    model_name=model_name
                ).values_list('career_id', 'embedding')
            )
            if not rows:
                logger.warning("No career embeddings in DB. Run 'python manage.py generate_career_embeddings'")
                return self._process_rule_based(query, progress_callback)

            query_lower = query.lower()
            query_vec = np.array(query_embedding)
            # Score by similarity only first; keep top 20 for hybrid re-score
            scored_ids = []
            for career_id, emb in rows:
                try:
                    sim = self._cosine_similarity(query_vec, np.array(emb))
                    scored_ids.append((sim, career_id))
                except Exception:
                    continue
            scored_ids.sort(key=lambda x: x[0], reverse=True)
            top_k = 20
            top_ids_ordered = [cid for _, cid in scored_ids[:top_k]]
            if not top_ids_ordered:
                return self._process_rule_based(query, progress_callback)

            # Load only top-K careers (not all) for keyword score and response
            careers_by_id = {
                c.id: c for c in Career.objects.filter(
                    id__in=top_ids_ordered,
                    publish_status=1
                ).prefetch_related(
                    'skills', 'career_cluster', 'profession',
                    'prospective_employment_areas', 'courses'
                )
            }
            criteria = self._extract_basic_criteria(query_lower)
            scored_careers = []
            for sim, career_id in scored_ids[:top_k]:
                career = careers_by_id.get(career_id)
                if not career:
                    continue
                keyword_score = self._calculate_keyword_score(career, criteria, query_lower)
                combined = (sim * 100 * 0.7) + (keyword_score * 0.3)
                scored_careers.append((combined, career))
            scored_careers.sort(key=lambda x: x[0], reverse=True)

            return {
                'criteria': {'method': 'semantic_search'},
                'careers': [career for _, career in scored_careers[:5]],
                'method': 'semantic'
            }
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            raise
    
    def _get_embedding(self, text, is_query=False):
        """Get embedding with caching - supports OpenAI and Gemini"""
        # Clean and prepare text
        text = strip_tags(str(text)) if text else ""
        text = text.strip()
        
        # Create cache key
        text_hash = hashlib.md5(text.encode()).hexdigest()
        cache_key = f"embedding_{self.ai_provider}_{self.embedding_model}_{text_hash}"
        cache_ttl = self.query_cache_ttl if is_query else self.embedding_cache_ttl
        
        # Try cache first (if enabled) - works even without API client
        if self.enable_embedding_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for embedding: {cache_key[:50]}...")
                return np.array(cached)
        
        # If no API client, raise error (can't generate new embeddings)
        if not self.ai_client:
            raise ValueError("AI client not initialized and embedding not in cache. Pre-generate embeddings or add API key.")
        
        # Generate embedding based on provider
        if self.ai_provider == 'openai':
            response = self.ai_client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000]
            )
            embedding = response.data[0].embedding
            
        elif self.ai_provider == 'gemini':
            # Gemini uses different API structure
            import google.generativeai as genai
            result = genai.embed_content(
                model=self.embedding_model,
                content=text[:8000],
                task_type="RETRIEVAL_DOCUMENT" if not is_query else "RETRIEVAL_QUERY"
            )
            embedding = result['embedding']
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")
        
        # Cache the embedding
        if self.enable_embedding_cache:
            cache.set(cache_key, embedding, cache_ttl)
            logger.debug(f"Cached embedding: {cache_key[:50]}...")
        
        return np.array(embedding)
    
    def _get_career_embedding(self, career):
        """Get cached career embedding from database or generate and cache it"""
        from .models import CareerEmbedding
        
        # Build career text
        career_text = self._build_career_text(career)
        text_hash = self._get_text_hash(career_text)
        
        # Try to get from database cache first (works even without API client)
        try:
            embedding_cache = CareerEmbedding.objects.get(career=career)
            # Check if cache is still valid (text hasn't changed)
            if embedding_cache.embedding_text_hash == text_hash:
                # If provider/model match OR if no API client (use whatever is cached)
                if (self.ai_provider and embedding_cache.provider == self.ai_provider and
                    self.embedding_model and embedding_cache.model_name == self.embedding_model):
                    logger.debug(f"Database cache hit for career: {career.name}")
                    return embedding_cache.embedding_array
                elif not self.ai_client:
                    # No API client but have cached embedding - use it anyway
                    logger.debug(f"Using cached embedding for {career.name} (no API client)")
                    return embedding_cache.embedding_array
                else:
                    # Provider/model changed, regenerate
                    logger.debug(f"Cache invalid for career: {career.name}, regenerating...")
                    embedding_cache.delete()
            else:
                # Career text changed, regenerate
                logger.debug(f"Career text changed for {career.name}, regenerating...")
                embedding_cache.delete()
        except CareerEmbedding.DoesNotExist:
            pass
        
        # If no API client and no cache, raise error
        if not self.ai_client:
            raise ValueError(f"Career embedding not found in database for {career.name}. Run 'python manage.py generate_career_embeddings' first.")
        
        # Generate new embedding
        logger.debug(f"Generating embedding for career: {career.name}")
        embedding = self._get_embedding(career_text, is_query=False)
        
        # Cache in database (update_or_create avoids duplicate key when row exists or race after delete)
        try:
            CareerEmbedding.objects.update_or_create(
                career=career,
                defaults={
                    'embedding': list(embedding),  # Convert numpy array to list for JSON
                    'embedding_text_hash': text_hash,
                    'provider': self.ai_provider or 'unknown',
                    'model_name': self.embedding_model or 'unknown',
                }
            )
        except IntegrityError:
            # Race: another request created the row; use existing embedding
            embedding_cache = CareerEmbedding.objects.get(career=career)
            return embedding_cache.embedding_array
        
        return embedding
    
    def _build_career_text(self, career):
        """Build comprehensive text representation of a career for embedding"""
        parts = [
            career.name,
            career.get_display_summary(),
            career.description[:500] if career.description else '',
        ]
        
        # Add related model names
        parts.extend([s.name for s in career.skills.all()[:10]])
        parts.extend([c.name for c in career.career_cluster.all()])
        parts.extend([p.name for p in career.profession.all()[:5]])
        
        # Filter out None or empty strings and join
        return " ".join(filter(None, parts))
    
    def _get_text_hash(self, text):
        """Get SHA256 hash of text"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def has_cached_embeddings(self):
        """Check if any career embeddings exist in database"""
        from .models import CareerEmbedding
        return CareerEmbedding.objects.exists()
    
    def _process_with_cached_embeddings_only(self, query, progress_callback=None):
        """
        Fallback: Use keyword matching with cached career embeddings
        Works when query embedding can't be generated but career embeddings exist
        """
        self._progress(progress_callback, "Searching careers...")
        query_lower = query.lower()
        criteria = self._extract_basic_criteria(query_lower)
        
        careers = Career.objects.filter(publish_status=1).prefetch_related(
            'skills', 'career_cluster', 'profession', 'embedding_cache',
            'prospective_employment_areas', 'courses'
        )
        
        scored_careers = []
        
        for career in careers:
            try:
                # Check if embedding exists (don't generate)
                embedding_cache = career.embedding_cache
                if embedding_cache:
                    # Use keyword score only (no semantic similarity)
                    keyword_score = self._calculate_keyword_score(career, criteria, query_lower)
                    scored_careers.append((keyword_score, career, {
                        'keyword_score': keyword_score,
                        'method': 'keyword_only'
                    }))
            except Exception:
                continue
        
        scored_careers.sort(key=lambda x: x[0], reverse=True)
        
        return {
            'criteria': criteria,
            'careers': [career for score, career, breakdown in scored_careers[:5]],
            'method': 'keyword_with_cached_embeddings'
        }
    
    def _cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _extract_basic_criteria(self, query_lower):
        """Extract basic criteria for keyword scoring"""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'what', 'show', 'me', 'careers', 'career', 'for', 'jobs', 'job'}
        words = re.findall(r'\b\w+\b', query_lower)
        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        
        interests = []
        if any(word in query_lower for word in ['creative', 'art', 'design']):
            interests.append('creative')
        if any(word in query_lower for word in ['tech', 'technology', 'software', 'programming']):
            interests.append('technology')
        
        return {'keywords': keywords, 'interests': interests}
    
    def _calculate_keyword_score(self, career, criteria, query_lower):
        """Calculate keyword-based score for hybrid approach"""
        score = 0
        keywords = criteria.get('keywords', [])
        
        career_name_lower = (career.name or '').lower()
        for keyword in keywords:
            if keyword in career_name_lower:
                score += 30
            if career.get_display_summary() and keyword in career.get_display_summary().lower():
                score += 20
        
        return min(score, 100)  # Cap at 100
    
    def _score_careers_by_relevance(self, careers, criteria, query_lower, show_breakdown=True):
        """
        Score careers by relevance to the query
        Returns sorted list of careers (most relevant first)
        
        Args:
            show_breakdown: If False, suppresses console output (used when semantic search is active)
        """
        scored = []
        keywords = criteria.get('keywords', [])
        interests = criteria.get('interests', [])
        
        for career in careers:
            score = 0
            score_breakdown = {
                'name_match': 0,
                'summary_match': 0,
                'cluster_match': 0,
                'skill_match': 0,
                'profession_match': 0,
                'query_word_boost': 0,
                'salary_boost': 0
            }
            
            # Name matching (highest priority)
            career_name_lower = (career.name or '').lower()
            for keyword in keywords:
                if keyword in career_name_lower:
                    # Exact match in name gets highest score
                    if keyword == career_name_lower:
                        name_score = 100
                    elif career_name_lower.startswith(keyword):
                        name_score = 50
                    else:
                        name_score = 30
                    score += name_score
                    score_breakdown['name_match'] += name_score
            
            # Summary matching
            career_summary_lower = (career.get_display_summary() or '').lower()
            for keyword in keywords:
                if keyword in career_summary_lower:
                    summary_score = 20
                    score += summary_score
                    score_breakdown['summary_match'] += summary_score
            
            # Cluster matching (high relevance for interest-based queries)
            if interests:
                cluster_names = [c.name.lower() for c in career.career_cluster.all() if c.name]
                for interest in interests:
                    cluster_score = 0
                    if interest == 'creative':
                        if any('art' in cn or 'design' in cn or 'creative' in cn for cn in cluster_names):
                            cluster_score = 40
                    elif interest == 'technology':
                        if any('tech' in cn or 'computer' in cn or 'engineering' in cn for cn in cluster_names):
                            cluster_score = 40
                    elif interest == 'medical':
                        if any('health' in cn or 'medical' in cn for cn in cluster_names):
                            cluster_score = 40
                    elif interest == 'business':
                        if any('business' in cn or 'commerce' in cn or 'management' in cn for cn in cluster_names):
                            cluster_score = 40
                    if cluster_score > 0:
                        score += cluster_score
                        score_breakdown['cluster_match'] += cluster_score
            
            # Skill matching
            skill_names = [s.name.lower() for s in career.skills.all() if s.name]
            for keyword in keywords:
                if any(keyword in skill_name for skill_name in skill_names):
                    skill_score = 15
                    score += skill_score
                    score_breakdown['skill_match'] += skill_score
            
            # Profession matching
            profession_names = [p.name.lower() for p in career.profession.all() if p.name]
            for keyword in keywords:
                if any(keyword in prof_name for prof_name in profession_names):
                    prof_score = 10
                    score += prof_score
                    score_breakdown['profession_match'] += prof_score
            
            # Boost score if query words appear in name
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in career_name_lower:
                    boost_score = 25
                    score += boost_score
                    score_breakdown['query_word_boost'] += boost_score
            
            scored.append((score, career, score_breakdown))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Return careers only
        return [career for score, career, breakdown in scored]
    
    def generate_summary(self, careers, query_context=None):
        """
        Generate summary - template-based by default, AI-enhanced if enabled
        """
        if self.use_ai_summaries and self.ai_client:
            try:
                return self._generate_ai_summary(careers, query_context)
            except Exception as e:
                logger.error(f"AI summary generation failed: {e}, using template")
                return self._generate_template_summary(careers, query_context)
        else:
            return self._generate_template_summary(careers, query_context)
    
    def _generate_template_summary(self, careers, query_context):
        """
        Template-based summary - works without AI
        """
        count = len(careers)
        
        if count == 0:
            return "I couldn't find any careers matching your criteria. Try rephrasing your query or exploring different interests."
        
        if count == 1:
            career = careers[0]
            summary_text = (career.get_display_summary() or '')[:150] or 'Explore this career to learn more.'
            return f"I found 1 career matching your query: **{career.name}**. {summary_text}"
        
        # Get top categories
        clusters = {}
        for career in careers[:10]:
            if hasattr(career, 'career_cluster') and career.career_cluster.exists():
                cluster_name = career.career_cluster.first().name
                clusters[cluster_name] = clusters.get(cluster_name, 0) + 1
        
        top_cluster = max(clusters.items(), key=lambda x: x[1])[0] if clusters else None
        
        summary = f"I found **{count} careers** matching your query."
        if top_cluster:
            summary += f" Most are in **{top_cluster}**."
        
        # Add diversity note if many categories
        if len(clusters) > 3:
            summary += " These careers span multiple fields."
        
        return summary
    
    def _generate_ai_summary(self, careers, query_context):
        """AI-generated summary (optional)"""
        # Implementation with AI
        # Fallback to template if fails
        return self._generate_template_summary(careers, query_context)
    
    def get_suggested_questions(self, query, results):
        """
        Get follow-up questions based ONLY on the careers shown - only relevant to displayed careers
        Returns empty list - frontend will generate suggestions from career data
        """
        # Return empty - let frontend generate from actual career data
        return []
        
        if has_eligibility:
            suggestions.append("What are the eligibility requirements for these careers?")
        
        if has_pros_cons:
            suggestions.append("What are the pros and cons of these careers?")
        
        if has_mindmap:
            suggestions.append("Show me career mindmaps for these careers")
        
        # If we have career names, suggest exploring specific aspects
        if career_names:
            if len(career_names) == 1:
                suggestions.append(f"Tell me more about {career_names[0]}")
            else:
                suggestions.append("Show me similar careers")
        
        # If we have clusters, suggest exploring the cluster
        if clusters and len(clusters) > 0:
            cluster_list = list(clusters)[:2]  # Limit to 2 clusters
            if len(cluster_list) == 1:
                suggestions.append(f"Show me more careers in {cluster_list[0]}")
            else:
                suggestions.append(f"Show me more careers in {cluster_list[0]} or {cluster_list[1]}")
        
        # If we have multiple careers, suggest comparison
        if len(results) > 1:
            suggestions.append("Compare these careers")
        
        # Always suggest exploring roles and responsibilities if we have careers
        if len(results) > 0:
            suggestions.append("What are the roles and responsibilities in these careers?")
        
        return suggestions[:5]  # Limit to 5 most relevant
    
    def get_similar_or_alternative_careers(self, career_id, exclude_ids=None, limit=6):
        """
        Get similar or alternative careers based on a reference career.
        Used when user asks for "another career" or "similar career".
        """
        try:
            from .models import Career
            reference_career = Career.objects.filter(id=career_id, publish_status=1).first()
            
            if not reference_career:
                return []
            
            exclude_ids = exclude_ids or []
            exclude_ids.append(career_id)  # Always exclude the reference career
            
            # Build query for similar careers
            similar_careers = []
            
            # 1. Same cluster (highest priority)
            if reference_career.career_cluster.exists():
                cluster_ids = list(reference_career.career_cluster.values_list('id', flat=True))
                cluster_careers = Career.objects.filter(
                    career_cluster__id__in=cluster_ids,
                    publish_status=1
                ).exclude(id__in=exclude_ids).distinct()[:limit]
                similar_careers.extend(cluster_careers)
            
            # 2. Similar skills (if we need more)
            if len(similar_careers) < limit:
                reference_skills = list(reference_career.skills.filter(object_status=1).values_list('id', flat=True))
                if reference_skills:
                    skill_careers = Career.objects.filter(
                        skills__id__in=reference_skills,
                        publish_status=1
                    ).exclude(id__in=exclude_ids).distinct()
                    
                    # Add to list if not already present
                    existing_ids = {c.id for c in similar_careers}
                    for career in skill_careers:
                        if career.id not in existing_ids and len(similar_careers) < limit:
                            similar_careers.append(career)
            
            # 3. Same profession (if we need more)
            if len(similar_careers) < limit and hasattr(reference_career, 'profession') and reference_career.profession:
                profession_careers = Career.objects.filter(
                    profession=reference_career.profession,
                    publish_status=1
                ).exclude(id__in=exclude_ids).distinct()
                
                existing_ids = {c.id for c in similar_careers}
                for career in profession_careers:
                    if career.id not in existing_ids and len(similar_careers) < limit:
                        similar_careers.append(career)
            
            # 4. Random careers from same category (fallback)
            if len(similar_careers) < limit:
                random_careers = Career.objects.filter(
                    publish_status=1
                ).exclude(id__in=exclude_ids).order_by('?')[:limit - len(similar_careers)]
                similar_careers.extend(random_careers)
            
            return similar_careers[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar careers: {e}")
            return []
    
    def get_similar_careers(self, career_id, limit=3):
        """
        Get similar careers based on cluster, skills, and profession.
        Used to enhance query results with related careers.
        """
        try:
            from .models import Career
            reference_career = Career.objects.filter(id=career_id, publish_status=1).first()
            
            if not reference_career:
                return []
            
            similar_careers = []
            
            # Same cluster
            if reference_career.career_cluster.exists():
                cluster_ids = list(reference_career.career_cluster.values_list('id', flat=True))
                cluster_careers = Career.objects.filter(
                    career_cluster__id__in=cluster_ids,
                    publish_status=1
                ).exclude(id=career_id).distinct()[:limit]
                similar_careers.extend(cluster_careers)
            
            return similar_careers[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar careers: {e}")
            return []

