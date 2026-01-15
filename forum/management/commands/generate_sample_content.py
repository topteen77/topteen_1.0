"""
Management command to generate sample queries and responses for all categories
Run: python manage.py generate_sample_content
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from forum.models import Category, Query, Response, Country
from forum.services.ai_service import generate_ai_response
from django.conf import settings
import time


class Command(BaseCommand):
    help = 'Generate sample queries and responses for all forum categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--use-ai',
            action='store_true',
            help='Use OpenAI API to generate responses (requires OPENAI_API_KEY)',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip categories that already have sample queries',
        )

    def handle(self, *args, **options):
        use_ai = options.get('use_ai', False)
        skip_existing = options.get('skip_existing', False)
        
        self.stdout.write('Generating sample content for all categories...')
        
        # Check if OpenAI is available
        has_openai = bool(getattr(settings, 'OPENAI_API_KEY', None))
        if use_ai and not has_openai:
            self.stdout.write(self.style.WARNING(
                '⚠️  OpenAI API key not found. Using pre-written sample responses instead.'
            ))
            use_ai = False
        
        # Sample queries and responses for each category
        sample_content = {
            'admission': {
                'queries': [
                    {
                        'question': 'What are the admission requirements for engineering colleges in India?',
                        'country': None,
                        'response': self._get_admission_response_1()
                    },
                    {
                        'question': 'How to apply for B.Tech in top IITs? What is the process?',
                        'country': None,
                        'response': self._get_admission_response_2()
                    }
                ]
            },
            'visa': {
                'queries': [
                    {
                        'question': 'What documents are needed for student visa to USA?',
                        'country': 'United States',
                        'response': self._get_visa_response_1()
                    },
                    {
                        'question': 'How long does it take to get a study permit for Canada?',
                        'country': 'Canada',
                        'response': self._get_visa_response_2()
                    }
                ]
            },
            'finance': {
                'queries': [
                    {
                        'question': 'What are the best scholarships available for Indian students studying abroad?',
                        'country': None,
                        'response': self._get_finance_response_1()
                    },
                    {
                        'question': 'How much does it cost to study engineering in USA?',
                        'country': 'United States',
                        'response': self._get_finance_response_2()
                    }
                ]
            },
            'accommodation': {
                'queries': [
                    {
                        'question': 'What are the accommodation options for students in UK universities?',
                        'country': 'United Kingdom',
                        'response': self._get_accommodation_response_1()
                    },
                    {
                        'question': 'How to find affordable housing near university campus?',
                        'country': None,
                        'response': self._get_accommodation_response_2()
                    }
                ]
            },
            'work': {
                'queries': [
                    {
                        'question': 'Can I work part-time while studying in Australia?',
                        'country': 'Australia',
                        'response': self._get_work_response_1()
                    },
                    {
                        'question': 'What are the best part-time job options for high school students?',
                        'country': None,
                        'response': self._get_work_response_2()
                    }
                ]
            },
            'predeparture': {
                'queries': [
                    {
                        'question': 'What should I pack when going to study abroad?',
                        'country': None,
                        'response': self._get_predeparture_response_1()
                    },
                    {
                        'question': 'What are the important things to do before leaving for university?',
                        'country': None,
                        'response': self._get_predeparture_response_2()
                    }
                ]
            },
            'country': {
                'queries': [
                    {
                        'question': 'Which country is best for engineering students after 12th?',
                        'country': None,
                        'response': self._get_country_response_1()
                    },
                    {
                        'question': 'Compare study abroad options: USA vs UK vs Canada',
                        'country': None,
                        'response': self._get_country_response_2()
                    }
                ]
            },
            'stem': {
                'queries': [
                    {
                        'question': 'What are the best career options in Science stream after 12th?',
                        'country': None,
                        'response': self._get_stem_response_1()
                    },
                    {
                        'question': 'Should I choose Engineering or Medicine? How to decide?',
                        'country': None,
                        'response': self._get_stem_response_2()
                    }
                ]
            },
            'commerce': {
                'queries': [
                    {
                        'question': 'What are the career options after Commerce stream in 12th?',
                        'country': None,
                        'response': self._get_commerce_response_1()
                    },
                    {
                        'question': 'How to become a Chartered Accountant (CA)? What is the process?',
                        'country': None,
                        'response': self._get_commerce_response_2()
                    }
                ]
            },
            'arts': {
                'queries': [
                    {
                        'question': 'What career options are available in Arts stream?',
                        'country': None,
                        'response': self._get_arts_response_1()
                    },
                    {
                        'question': 'How to get into design colleges like NID or NIFT?',
                        'country': None,
                        'response': self._get_arts_response_2()
                    }
                ]
            },
            'vocational': {
                'queries': [
                    {
                        'question': 'What are vocational courses available after 10th?',
                        'country': None,
                        'response': self._get_vocational_response_1()
                    },
                    {
                        'question': 'Are ITI courses good for career? What are the job opportunities?',
                        'country': None,
                        'response': self._get_vocational_response_2()
                    }
                ]
            },
            'emerging': {
                'queries': [
                    {
                        'question': 'What are the emerging careers in AI and Machine Learning?',
                        'country': None,
                        'response': self._get_emerging_response_1()
                    },
                    {
                        'question': 'Is Data Science a good career choice for future?',
                        'country': None,
                        'response': self._get_emerging_response_2()
                    }
                ]
            },
            'studyabroad': {
                'queries': [
                    {
                        'question': 'What are the requirements to study abroad after 12th?',
                        'country': None,
                        'response': self._get_studyabroad_response_1()
                    },
                    {
                        'question': 'When should I start preparing for SAT and IELTS?',
                        'country': None,
                        'response': self._get_studyabroad_response_2()
                    }
                ]
            }
        }
        
        total_created = 0
        total_skipped = 0
        
        # Get all categories
        categories = Category.objects.all()
        
        for category in categories:
            slug = category.slug
            if slug not in sample_content:
                self.stdout.write(self.style.WARNING(f'⚠️  No sample content defined for category: {category.name}'))
                continue
            
            # Check if category already has queries
            if skip_existing and Query.objects.filter(category=category, status='completed').exists():
                self.stdout.write(f'⏭️  Skipping {category.name} (already has queries)')
                total_skipped += 1
                continue
            
            self.stdout.write(f'\n📝 Processing category: {category.name}')
            
            content = sample_content[slug]
            queries_data = content['queries']
            
            for query_data in queries_data:
                question = query_data['question']
                country_name = query_data.get('country')
                country_obj = None
                
                if country_name:
                    try:
                        country_obj = Country.objects.get(name=country_name)
                    except Country.DoesNotExist:
                        pass
                
                # Check if query already exists
                if Query.objects.filter(question_text=question, category=category).exists():
                    self.stdout.write(f'  ⏭️  Skipping: "{question[:50]}..." (already exists)')
                    continue
                
                # Create query
                query = Query.objects.create(
                    question_text=question,
                    category=category,
                    country_context=country_name,
                    status='pending',
                    source='ai' if use_ai else 'database'
                )
                
                # Generate or use sample response
                if use_ai:
                    self.stdout.write(f'  🤖 Generating AI response for: "{question[:50]}..."')
                    try:
                        start_time = time.time()
                        response_text, cost = generate_ai_response(question, country_obj, category)
                        response_time_ms = int((time.time() - start_time) * 1000)
                        
                        # Add query to response if not present
                        if not response_text.startswith('<h4>📝 Query:</h4>'):
                            response_text = f'<h4>📝 Query:</h4>\n<p><strong>{question}</strong></p>\n\n{response_text}'
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ❌ Error generating AI response: {str(e)}'))
                        response_text = query_data['response']
                        response_time_ms = 1000
                        cost = 0.0
                else:
                    response_text = query_data['response']
                    response_time_ms = 500
                    cost = 0.0
                
                # Create response
                Response.objects.create(
                    query=query,
                    response_text=response_text,
                    confidence_score=0.95,
                    sources=[]
                )
                
                # Mark query as completed
                query.status = 'completed'
                query.processed_at = timezone.now()
                query.response_time_ms = response_time_ms
                query.save()
                
                total_created += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: "{question[:50]}..."'))
                
                # Small delay to avoid rate limiting
                if use_ai:
                    time.sleep(1)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'\n✓ Sample content generation completed!'))
        self.stdout.write(f'  • Created: {total_created} queries with responses')
        if total_skipped > 0:
            self.stdout.write(f'  • Skipped: {total_skipped} categories (already had content)')
        self.stdout.write('='*80 + '\n')
    
    # Sample response templates for each category
    def _get_admission_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the admission requirements for engineering colleges in India?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Admission Requirements<br>
Category: Engineering Colleges<br>
Focus: Indian Engineering Admission Process</p>

<h4>📋 COMPLETE REQUIREMENTS</h4>
<ul>
<li><strong>Academic Qualification:</strong> 10+2 (or equivalent) with Physics, Chemistry, and Mathematics (PCM)</li>
<li><strong>Minimum Percentage:</strong> Usually 45-50% aggregate (varies by college)</li>
<li><strong>Entrance Exams:</strong> JEE Main (mandatory for most), JEE Advanced (for IITs), State-level exams</li>
<li><strong>Age Limit:</strong> Generally 17-25 years</li>
<li><strong>Nationality:</strong> Indian nationals or specified categories</li>
</ul>

<h4>🎯 ENTRANCE EXAM OPTIONS</h4>
<ul>
<li><strong>JEE Main:</strong> For NITs, IIITs, and many private colleges</li>
<li><strong>JEE Advanced:</strong> For IITs (only top 2.5 lakh JEE Main qualifiers)</li>
<li><strong>State Exams:</strong> MHT-CET, WBJEE, KCET, etc. for state colleges</li>
<li><strong>BITSAT:</strong> For BITS Pilani campuses</li>
<li><strong>VITEEE:</strong> For VIT universities</li>
</ul>

<h4>📊 ADMISSION PROCESS</h4>
<ol>
<li>Register for JEE Main (usually in December)</li>
<li>Appear for JEE Main (January/April)</li>
<li>Check results and qualify for JEE Advanced (if targeting IITs)</li>
<li>Participate in JoSAA/CSAB counseling</li>
<li>Choose colleges and branches based on rank</li>
<li>Complete admission formalities</li>
</ol>

<h4>💰 COST CONSIDERATIONS</h4>
<ul>
<li><strong>Government Colleges (IITs/NITs):</strong> ₹2-3 lakhs per year</li>
<li><strong>Private Colleges:</strong> ₹3-15 lakhs per year</li>
<li><strong>Scholarships:</strong> Merit-based, need-based, and government schemes available</li>
</ul>

<h4>✅ TIPS FOR SUCCESS</h4>
<ul>
<li>Start preparation early (ideally from Class 11)</li>
<li>Focus on NCERT books for JEE Main</li>
<li>Practice previous year papers regularly</li>
<li>Take mock tests to improve speed and accuracy</li>
<li>Maintain good academic record (some colleges consider 12th marks)</li>
</ul>

<p>I hope this helps you understand the admission requirements for engineering colleges! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_admission_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How to apply for B.Tech in top IITs? What is the process?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: IIT Admission Process<br>
Category: Top Engineering Colleges<br>
Focus: Step-by-step application guide</p>

<h4>📋 COMPLETE APPLICATION PROCESS</h4>
<ol>
<li><strong>Step 1: Register for JEE Main</strong>
   <ul>
   <li>Registration opens: Usually December</li>
   <li>Website: jeemain.nta.ac.in</li>
   <li>Documents needed: Class 10 & 12 marksheets, photo, signature</li>
   </ul>
</li>
<li><strong>Step 2: Appear for JEE Main</strong>
   <ul>
   <li>Exam dates: January and April (best of two scores considered)</li>
   <li>Subjects: Physics, Chemistry, Mathematics</li>
   <li>Total marks: 300 (100 per subject)</li>
   </ul>
</li>
<li><strong>Step 3: Qualify for JEE Advanced</strong>
   <ul>
   <li>Top 2.5 lakh JEE Main qualifiers eligible</li>
   <li>Register for JEE Advanced (usually in May)</li>
   <li>Website: jeeadv.ac.in</li>
   </ul>
</li>
<li><strong>Step 4: Appear for JEE Advanced</strong>
   <ul>
   <li>Exam date: Usually in June</li>
   <li>Two papers: Paper 1 and Paper 2</li>
   <li>Both papers mandatory</li>
   </ul>
</li>
<li><strong>Step 5: Participate in JoSAA Counseling</strong>
   <ul>
   <li>Registration: After JEE Advanced results</li>
   <li>Website: josaa.nic.in</li>
   <li>Fill choices: Select IITs and branches in order of preference</li>
   <li>Multiple rounds of seat allocation</li>
   </ul>
</li>
<li><strong>Step 6: Accept Seat and Report</strong>
   <ul>
   <li>Accept allocated seat online</li>
   <li>Pay seat acceptance fee</li>
   <li>Report to allocated IIT for document verification</li>
   </ul>
</li>
</ol>

<h4>🎯 ELIGIBILITY CRITERIA</h4>
<ul>
<li>Passed 10+2 with Physics, Chemistry, and Mathematics</li>
<li>Minimum 75% aggregate (65% for SC/ST) OR be in top 20 percentile</li>
<li>Age: Born on or after October 1, 1998 (relaxation for reserved categories)</li>
<li>Maximum 2 attempts at JEE Advanced</li>
</ul>

<h4>📊 IIT RANKING AND BRANCHES</h4>
<ul>
<li><strong>Top IITs:</strong> IIT Bombay, IIT Delhi, IIT Madras, IIT Kanpur, IIT Kharagpur</li>
<li><strong>Popular Branches:</strong> Computer Science, Electrical, Mechanical, Civil</li>
<li><strong>Cutoff Ranks:</strong> Vary by IIT and branch (check JoSAA website for latest)</li>
</ul>

<h4>💰 FEES STRUCTURE</h4>
<ul>
<li><strong>Tuition Fee:</strong> ₹2 lakhs per year (for general category)</li>
<li><strong>Hostel Fee:</strong> ₹50,000-1 lakh per year</li>
<li><strong>Mess Charges:</strong> ₹30,000-50,000 per year</li>
<li><strong>Total:</strong> Approximately ₹3-4 lakhs per year</li>
<li><strong>Scholarships:</strong> Merit-cum-means scholarships available</li>
</ul>

<h4>✅ PREPARATION TIPS</h4>
<ul>
<li>Start early: Begin preparation from Class 11</li>
<li>Focus on concepts: Strong foundation in PCM is crucial</li>
<li>Practice regularly: Solve previous year papers and mock tests</li>
<li>Time management: Learn to solve problems quickly</li>
<li>Stay consistent: Regular study schedule is key</li>
</ul>

<p>I hope this helps you understand the complete process for applying to IITs! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_visa_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What documents are needed for student visa to USA?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Visa Documentation<br>
Country: United States<br>
Category: Student Visa (F-1)</p>

<h4>📋 REQUIRED DOCUMENTS</h4>
<ul>
<li><strong>Form I-20:</strong> Certificate of Eligibility from your US university</li>
<li><strong>DS-160 Form:</strong> Online nonimmigrant visa application (completed and printed)</li>
<li><strong>Valid Passport:</strong> Must be valid for at least 6 months beyond your intended stay</li>
<li><strong>Visa Application Fee Receipt:</strong> SEVIS fee payment confirmation</li>
<li><strong>Photo:</strong> Recent passport-size photo (2x2 inches, white background)</li>
<li><strong>Academic Documents:</strong> 10th, 12th marksheets, degree certificates, transcripts</li>
<li><strong>Standardized Test Scores:</strong> SAT, ACT, GRE, GMAT, IELTS/TOEFL scores</li>
<li><strong>Financial Documents:</strong> Bank statements, scholarship letters, sponsor affidavits</li>
<li><strong>Proof of Ties to Home Country:</strong> Property documents, family ties, job offers</li>
</ul>

<h4>💰 FINANCIAL DOCUMENTS</h4>
<ul>
<li>Bank statements (last 3-6 months)</li>
<li>Fixed deposit certificates</li>
<li>Sponsor's financial affidavit (Form I-134)</li>
<li>Scholarship or financial aid letters</li>
<li>Income tax returns (last 2-3 years)</li>
</ul>

<h4>📅 APPLICATION PROCESS</h4>
<ol>
<li>Receive I-20 from university</li>
<li>Pay SEVIS fee ($350)</li>
<li>Complete DS-160 form online</li>
<li>Pay visa application fee ($185)</li>
<li>Schedule visa interview</li>
<li>Attend interview at US Embassy/Consulate</li>
<li>Receive visa (if approved)</li>
</ul>

<p>I hope this helps you prepare for your US student visa application! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_visa_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How long does it take to get a study permit for Canada?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Visa Processing Time<br>
Country: Canada<br>
Category: Study Permit</p>

<h4>⏱️ PROCESSING TIMES</h4>
<ul>
<li><strong>Online Application:</strong> 4-6 weeks (most common)</li>
<li><strong>Paper Application:</strong> 10-12 weeks</li>
<li><strong>Biometrics:</strong> Additional 1-2 weeks</li>
<li><strong>Peak Season (May-August):</strong> May take 8-12 weeks</li>
</ul>

<h4>📋 APPLICATION STEPS</h4>
<ol>
<li>Get Letter of Acceptance from Canadian institution</li>
<li>Gather required documents</li>
<li>Apply online or via paper</li>
<li>Give biometrics (if required)</li>
<li>Wait for processing</li>
<li>Receive study permit</li>
</ol>

<h4>✅ TIPS TO SPEED UP</h4>
<ul>
<li>Apply early (3-4 months before course starts)</li>
<li>Submit complete documents</li>
<li>Apply online (faster than paper)</li>
<li>Check application status regularly</li>
</ul>

<p>I hope this helps you plan your Canadian study permit application! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_finance_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the best scholarships available for Indian students studying abroad?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Scholarships<br>
Category: Financial Aid<br>
Focus: International Scholarships for Indian Students</p>

<h4>🎯 TOP SCHOLARSHIPS</h4>
<ul>
<li><strong>Fulbright-Nehru Scholarship:</strong> For US studies, covers tuition + living</li>
<li><strong>Chevening Scholarship:</strong> UK government scholarship, fully funded</li>
<li><strong>Commonwealth Scholarship:</strong> For Commonwealth countries</li>
<li><strong>Erasmus Mundus:</strong> European Union scholarship</li>
<li><strong>Inlaks Scholarship:</strong> For top universities worldwide</li>
</ul>

<h4>💰 UNIVERSITY-SPECIFIC</h4>
<ul>
<li>MIT, Stanford, Harvard: Need-based aid available</li>
<li>Oxford, Cambridge: Various merit scholarships</li>
<li>Canadian universities: Entrance scholarships</li>
</ul>

<p>I hope this helps you find scholarship opportunities! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_finance_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How much does it cost to study engineering in USA?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Cost Analysis<br>
Country: United States<br>
Category: Engineering Education</p>

<h4>💰 COST BREAKDOWN</h4>
<ul>
<li><strong>Tuition:</strong> $20,000-$60,000 per year</li>
<li><strong>Living Expenses:</strong> $15,000-$25,000 per year</li>
<li><strong>Total:</strong> $35,000-$85,000 per year</li>
<li><strong>4-Year Total:</strong> $140,000-$340,000</li>
</ul>

<h4>📊 BY UNIVERSITY TYPE</h4>
<ul>
<li><strong>Public Universities:</strong> $25,000-$45,000/year</li>
<li><strong>Private Universities:</strong> $50,000-$85,000/year</li>
<li><strong>Community Colleges:</strong> $10,000-$20,000/year (first 2 years)</li>
</ul>

<p>I hope this helps you plan your finances for US engineering education! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_accommodation_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the accommodation options for students in UK universities?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Accommodation<br>
Country: United Kingdom<br>
Category: Student Housing</p>

<h4>🏠 ACCOMMODATION OPTIONS</h4>
<ul>
<li><strong>University Halls:</strong> On-campus, £4,000-£8,000/year</li>
<li><strong>Private Halls:</strong> Off-campus, £5,000-£10,000/year</li>
<li><strong>Shared Flats:</strong> £3,000-£6,000/year</li>
<li><strong>Homestay:</strong> £4,000-£7,000/year</li>
</ul>

<p>I hope this helps you find accommodation in the UK! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_accommodation_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How to find affordable housing near university campus?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Accommodation Search<br>
Category: Student Housing Tips</p>

<h4>🎯 TIPS FOR FINDING AFFORDABLE HOUSING</h4>
<ul>
<li>Start early: Begin searching 2-3 months before</li>
<li>Check university housing office</li>
<li>Use student housing websites</li>
<li>Consider shared accommodation</li>
<li>Look slightly away from campus (often cheaper)</li>
<li>Check public transport connectivity</li>
</ul>

<p>I hope this helps you find affordable housing! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_work_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>Can I work part-time while studying in Australia?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Work Rights<br>
Country: Australia<br>
Category: Student Employment</p>

<h4>✅ WORK RIGHTS FOR STUDENTS</h4>
<ul>
<li><strong>Part-time Work:</strong> Up to 40 hours per fortnight during study</li>
<li><strong>Full-time Work:</strong> Unlimited during holidays</li>
<li><strong>Minimum Wage:</strong> AUD $20+ per hour</li>
<li><strong>Popular Jobs:</strong> Retail, hospitality, tutoring, admin</li>
</ul>

<h4>📋 REQUIREMENTS</h4>
<ul>
<li>Valid student visa</li>
<li>Tax File Number (TFN)</li>
<li>Bank account</li>
</ul>

<p>I hope this helps you understand work rights in Australia! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_work_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the best part-time job options for high school students?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Part-time Jobs<br>
Category: Student Employment<br>
Focus: High School Students</p>

<h4>💼 BEST PART-TIME JOB OPTIONS</h4>
<ul>
<li><strong>Online Tutoring:</strong> Teach subjects you're good at, flexible hours</li>
<li><strong>Content Writing:</strong> Blog posts, articles, ₹5,000-₹20,000/month</li>
<li><strong>Social Media Management:</strong> Manage business social media accounts</li>
<li><strong>Freelance Design:</strong> Graphic design, logo creation</li>
<li><strong>Data Entry:</strong> Simple online work, ₹3,000-₹10,000/month</li>
<li><strong>Retail/Shop Assistant:</strong> Weekend work at local stores</li>
</ul>

<h4>✅ BENEFITS</h4>
<ul>
<li>Earn while learning</li>
<li>Build work experience</li>
<li>Develop time management skills</li>
<li>Add to resume/CV</li>
</ul>

<p>I hope this helps you find suitable part-time work! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_predeparture_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What should I pack when going to study abroad?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Pre-Departure Preparation<br>
Category: Packing Checklist</p>

<h4>📦 ESSENTIAL ITEMS TO PACK</h4>
<ul>
<li><strong>Documents:</strong> Passport, visa, I-20/offer letter, insurance, transcripts</li>
<li><strong>Clothing:</strong> Weather-appropriate clothes, formal wear, traditional wear</li>
<li><strong>Electronics:</strong> Laptop, phone, adapters, chargers</li>
<li><strong>Medicines:</strong> Prescription medicines, basic first-aid kit</li>
<li><strong>Personal Items:</strong> Photos, small mementos from home</li>
</ul>

<p>I hope this helps you pack for your study abroad journey! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_predeparture_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the important things to do before leaving for university?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Pre-Departure Checklist<br>
Category: Preparation</p>

<h4>✅ PRE-DEPARTURE CHECKLIST</h4>
<ul>
<li>Complete visa process</li>
<li>Book flights early</li>
<li>Arrange accommodation</li>
<li>Get health insurance</li>
<li>Open bank account (if possible)</li>
<li>Pack essentials</li>
<li>Inform bank about travel</li>
<li>Learn about destination culture</li>
</ul>

<p>I hope this helps you prepare for your university journey! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_country_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>Which country is best for engineering students after 12th?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Country Comparison<br>
Category: Study Abroad<br>
Focus: Engineering Education</p>

<h4>🌍 TOP COUNTRIES FOR ENGINEERING</h4>
<ul>
<li><strong>USA:</strong> Top universities (MIT, Stanford), high cost, good job opportunities</li>
<li><strong>Germany:</strong> Low/zero tuition, strong engineering programs, good job market</li>
<li><strong>Canada:</strong> Quality education, PR pathway, moderate cost</li>
<li><strong>UK:</strong> Shorter programs (3 years), high quality, expensive</li>
<li><strong>Australia:</strong> Good work rights, quality education, moderate cost</li>
</ul>

<h4>📊 COMPARISON FACTORS</h4>
<ul>
<li>Cost of education</li>
<li>Quality of universities</li>
<li>Job opportunities</li>
<li>PR pathways</li>
<li>Language requirements</li>
</ul>

<p>I hope this helps you choose the right country for engineering! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_country_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>Compare study abroad options: USA vs UK vs Canada</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Country Comparison<br>
Category: Study Abroad Analysis</p>

<h4>📊 COMPREHENSIVE COMPARISON</h4>
<table>
<tr><th>Factor</th><th>USA</th><th>UK</th><th>Canada</th></tr>
<tr><td>Cost/Year</td><td>$35K-$85K</td><td>£20K-£40K</td><td>CAD $20K-$40K</td></tr>
<tr><td>Duration</td><td>4 years</td><td>3 years</td><td>4 years</td></tr>
<tr><td>Work Rights</td><td>OPT (1-3 years)</td><td>2 years PSW</td><td>3 years PGWP</td></tr>
<tr><td>PR Pathway</td><td>Moderate</td><td>Moderate</td><td>Easier</td></tr>
</table>

<p>I hope this helps you compare your study abroad options! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_stem_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the best career options in Science stream after 12th?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Career Options<br>
Category: Science Stream<br>
Focus: Post-12th Career Paths</p>

<h4>🎯 TOP CAREER OPTIONS</h4>
<ul>
<li><strong>Engineering:</strong> Computer Science, Mechanical, Electrical, Civil</li>
<li><strong>Medicine:</strong> MBBS, BDS, Pharmacy, Nursing</li>
<li><strong>Research:</strong> Physics, Chemistry, Biology, Mathematics</li>
<li><strong>Data Science:</strong> Growing field with high demand</li>
<li><strong>Aviation:</strong> Pilot training, Aerospace engineering</li>
</ul>

<h4>📊 ENTRANCE EXAMS</h4>
<ul>
<li>JEE Main/Advanced (Engineering)</li>
<li>NEET (Medical)</li>
<li>BITSAT, VITEEE (Private colleges)</li>
</ul>

<p>I hope this helps you explore Science stream careers! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_stem_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>Should I choose Engineering or Medicine? How to decide?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Career Decision<br>
Category: Stream Selection<br>
Focus: Engineering vs Medicine</p>

<h4>🤔 FACTORS TO CONSIDER</h4>
<ul>
<li><strong>Interest:</strong> Do you enjoy problem-solving (Engineering) or helping people (Medicine)?</li>
<li><strong>Duration:</strong> Engineering (4 years) vs Medicine (5.5 years + internship)</li>
<li><strong>Cost:</strong> Engineering generally more affordable</li>
<li><strong>Work-Life Balance:</strong> Engineering offers more flexibility</li>
<li><strong>Salary:</strong> Both offer good earning potential</li>
</ul>

<h4>✅ DECISION FRAMEWORK</h4>
<ul>
<li>Take psychometric assessment</li>
<li>Talk to professionals in both fields</li>
<li>Consider your strengths and interests</li>
<li>Research job market trends</li>
</ul>

<p>I hope this helps you make an informed decision! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_commerce_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the career options after Commerce stream in 12th?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Career Options<br>
Category: Commerce Stream</p>

<h4>🎯 CAREER OPTIONS</h4>
<ul>
<li><strong>Chartered Accountancy (CA):</strong> High demand, good salary</li>
<li><strong>Company Secretary (CS):</strong> Corporate law and compliance</li>
<li><strong>Cost & Management Accountant (CMA):</strong> Financial management</li>
<li><strong>B.Com/BBA:</strong> Business administration, finance</li>
<li><strong>MBA:</strong> After graduation, management roles</li>
<li><strong>Banking:</strong> Bank PO, clerical positions</li>
</ul>

<p>I hope this helps you explore Commerce stream careers! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_commerce_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How to become a Chartered Accountant (CA)? What is the process?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Professional Course<br>
Category: CA Process</p>

<h4>📋 CA COURSE STRUCTURE</h4>
<ol>
<li><strong>CA Foundation:</strong> After 12th, 4 papers</li>
<li><strong>CA Intermediate:</strong> After Foundation, 8 papers (2 groups)</li>
<li><strong>Articleship:</strong> 3 years practical training</li>
<li><strong>CA Final:</strong> 8 papers (2 groups)</li>
</ol>

<h4>⏱️ TOTAL DURATION</h4>
<ul>
<li>Minimum: 4.5 years</li>
<li>Average: 5-6 years</li>
</ul>

<h4>💰 COST</h4>
<ul>
<li>Foundation: ₹10,000-₹15,000</li>
<li>Intermediate: ₹20,000-₹30,000</li>
<li>Final: ₹30,000-₹40,000</li>
<li>Total: ₹60,000-₹85,000</li>
</ul>

<p>I hope this helps you understand the CA process! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_arts_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What career options are available in Arts stream?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Career Options<br>
Category: Arts Stream</p>

<h4>🎯 CAREER OPTIONS</h4>
<ul>
<li><strong>Design:</strong> Fashion, Interior, Graphic Design (NID, NIFT)</li>
<li><strong>Law:</strong> LLB, CLAT exam</li>
<li><strong>Journalism:</strong> Mass communication, media</li>
<li><strong>Psychology:</strong> Counseling, clinical psychology</li>
<li><strong>Teaching:</strong> B.Ed, become a teacher</li>
<li><strong>Civil Services:</strong> UPSC, state PSC</li>
</ul>

<p>I hope this helps you explore Arts stream careers! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_arts_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>How to get into design colleges like NID or NIFT?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Design College Admission<br>
Category: Arts/Design</p>

<h4>📋 ADMISSION PROCESS</h4>
<ul>
<li><strong>NID:</strong> NID DAT (Design Aptitude Test)</li>
<li><strong>NIFT:</strong> NIFT Entrance Exam (Creative Ability Test + General Ability Test)</li>
<li><strong>Portfolio:</strong> Showcase your creative work</li>
<li><strong>Interview:</strong> Personal interview round</li>
</ul>

<h4>✅ PREPARATION TIPS</h4>
<ul>
<li>Develop drawing and sketching skills</li>
<li>Build a portfolio of creative work</li>
<li>Practice previous year papers</li>
<li>Take coaching classes if needed</li>
</ul>

<p>I hope this helps you prepare for design college admissions! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_vocational_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are vocational courses available after 10th?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Vocational Education<br>
Category: Skill-Based Courses</p>

<h4>🎯 VOCATIONAL COURSES</h4>
<ul>
<li><strong>ITI:</strong> Industrial Training Institute, 1-2 years</li>
<li><strong>Polytechnic:</strong> Diploma in Engineering, 3 years</li>
<li><strong>Diploma Courses:</strong> Various fields (IT, Hospitality, etc.)</li>
<li><strong>Certificate Courses:</strong> Short-term skill development</li>
</ul>

<h4>✅ BENEFITS</h4>
<ul>
<li>Faster entry into workforce</li>
<li>Practical, hands-on training</li>
<li>Lower cost than degree courses</li>
<li>Good job opportunities</li>
</ul>

<p>I hope this helps you explore vocational courses! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_vocational_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>Are ITI courses good for career? What are the job opportunities?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: ITI Career Prospects<br>
Category: Vocational Education</p>

<h4>✅ ITI COURSE BENEFITS</h4>
<ul>
<li>Short duration (1-2 years)</li>
<li>Low cost (₹5,000-₹20,000)</li>
<li>Practical training</li>
<li>Good job opportunities</li>
</ul>

<h4>💼 JOB OPPORTUNITIES</h4>
<ul>
<li>Government jobs (Railways, PSUs)</li>
<li>Private sector (Manufacturing, IT)</li>
<li>Self-employment options</li>
<li>Further studies (Polytechnic, Engineering)</li>
</ul>

<p>I hope this helps you understand ITI career prospects! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_emerging_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the emerging careers in AI and Machine Learning?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Emerging Careers<br>
Category: AI/ML Careers</p>

<h4>🚀 EMERGING AI/ML CAREERS</h4>
<ul>
<li><strong>AI Engineer:</strong> Develop AI systems, ₹8-25 lakhs/year</li>
<li><strong>Machine Learning Engineer:</strong> Build ML models</li>
<li><strong>Data Scientist:</strong> Analyze data, ₹10-30 lakhs/year</li>
<li><strong>Prompt Engineer:</strong> Design AI prompts, new field</li>
<li><strong>AI Ethics Specialist:</strong> Ensure responsible AI</li>
</ul>

<h4>📚 EDUCATION PATH</h4>
<ul>
<li>B.Tech in Computer Science/AI</li>
<li>M.Tech/M.S. in AI/ML</li>
<li>Online courses and certifications</li>
</ul>

<p>I hope this helps you explore AI/ML careers! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_emerging_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>Is Data Science a good career choice for future?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Career Guidance<br>
Category: Data Science</p>

<h4>✅ DATA SCIENCE PROSPECTS</h4>
<ul>
<li><strong>High Demand:</strong> Growing field with many opportunities</li>
<li><strong>Good Salary:</strong> ₹8-30 lakhs/year (varies by experience)</li>
<li><strong>Future-Proof:</strong> Data is growing exponentially</li>
<li><strong>Diverse Roles:</strong> Analyst, Scientist, Engineer</li>
</ul>

<h4>📚 SKILLS NEEDED</h4>
<ul>
<li>Programming (Python, R)</li>
<li>Statistics and Mathematics</li>
<li>Machine Learning</li>
<li>Data Visualization</li>
</ul>

<p>I hope this helps you evaluate Data Science as a career! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_studyabroad_response_1(self):
        return """<h4>📝 Query:</h4>
<p><strong>What are the requirements to study abroad after 12th?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Study Abroad Requirements<br>
Category: International Education</p>

<h4>📋 BASIC REQUIREMENTS</h4>
<ul>
<li><strong>Academic:</strong> 10+2 with good grades (usually 70%+)</li>
<li><strong>English Tests:</strong> IELTS (6.5+) or TOEFL (80+)</li>
<li><strong>Standardized Tests:</strong> SAT (for USA), ACT</li>
<li><strong>Documents:</strong> Transcripts, LORs, SOP, passport</li>
<li><strong>Financial Proof:</strong> Bank statements, sponsor letters</li>
<li><strong>Visa:</strong> Student visa for destination country</li>
</ul>

<h4>⏱️ TIMELINE</h4>
<ul>
<li>Start preparation: Class 11-12</li>
<li>Take tests: 6-12 months before application</li>
<li>Apply: 8-12 months before course starts</li>
<li>Get visa: 2-3 months before departure</li>
</ul>

<p>I hope this helps you understand study abroad requirements! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""

    def _get_studyabroad_response_2(self):
        return """<h4>📝 Query:</h4>
<p><strong>When should I start preparing for SAT and IELTS?</strong></p>

<h4>🤖 AI ANALYSIS</h4>
<p>Query Type: Test Preparation Timeline<br>
Category: Standardized Tests</p>

<h4>⏱️ RECOMMENDED TIMELINE</h4>
<ul>
<li><strong>Class 11:</strong> Start basic preparation, build vocabulary</li>
<li><strong>Class 12 (First Half):</strong> Intensive preparation, take practice tests</li>
<li><strong>Class 12 (Mid-Year):</strong> Take actual SAT/IELTS</li>
<li><strong>Before Application:</strong> Retake if needed to improve scores</li>
</ul>

<h4>📚 PREPARATION TIPS</h4>
<ul>
<li>SAT: Focus on Math and English, practice regularly</li>
<li>IELTS: Practice all 4 sections (Reading, Writing, Listening, Speaking)</li>
<li>Take mock tests to identify weak areas</li>
<li>Consider coaching if needed</li>
</ul>

<p>I hope this helps you plan your test preparation! Feel free to ask me any other questions. Remember, it's okay to explore and change your mind - that's part of finding the right path for you! 🎯</p>"""
