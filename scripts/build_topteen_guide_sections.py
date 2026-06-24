# -*- coding: utf-8 -*-
"""Generate full TopTeen guide section HTML from docx extract."""
import re
from pathlib import Path

EXTRACT = Path(r'e:\shanti sir\topteen_1.0\docx_extract.txt')
OUT = Path(r'e:\shanti sir\topteen_1.0\templates\template20\_guide_sections_full.html')

def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))

def p(text):
    return f'                <p>{esc(text)}</p>\n'

def p_html(text):
    return f'                <p>{text}</p>\n'

def raw_html(html):
    return html

def h4(text):
    return f'                <h4 class="tt-subheading">{esc(text)}</h4>\n'

def defn_list(pairs):
    """Doc-style title + description listing with strong labels."""
    lines = ['                <ul class="tt-defn-list">\n']
    for title, desc in pairs:
        lines.append(f'                  <li><strong>{esc(title)}</strong> {esc(desc)}</li>\n')
    lines.append('                </ul>\n')
    return ''.join(lines)

def exam_block(title, examples, follow_label=None, follow_items=None, closing=None):
    block = h4(title) + p('Examples:') + ul(examples)
    if follow_label and follow_items:
        block += p(follow_label) + ul(follow_items)
    if closing:
        block += p(closing)
    return block

def ai_domain_block(title, examples, closing):
    inner = h4(title) + p('Examples:') + ul(examples) + p(closing)
    return f'                <div class="tt-ai-domain">\n{inner}                </div>\n'

def tip_callout(text):
    return callout('tip', 'Tip for Students', text)

def important_callout(text):
    return callout('important', 'Important', text)

def important_callout_rich(inner):
    return callout_rich('important', 'Important', inner)

def important_students_callout_rich(inner):
    return callout_rich('important', 'Important for Students', inner)

def ul(items):
    lines = ['                <ul class="tt-milestones">\n']
    for item in items:
        lines.append(f'                  <li>{esc(item)}</li>\n')
    lines.append('                </ul>\n')
    return ''.join(lines)

def ol(items):
    lines = ['                <ol class="tt-steps">\n']
    for item in items:
        lines.append(f'                  <li>{item}</li>\n')
    lines.append('                </ol>\n')
    return ''.join(lines)

def data_grid(rows, headers=('Area', 'What It Means for You')):
    h1, h2 = headers
    lines = ['                <div class="tt-data-grid">\n']
    lines.append(f'                  <div class="tt-data-row header"><div class="col-label">{esc(h1)}</div><div class="col-value">{esc(h2)}</div></div>\n')
    for a, b in rows:
        lines.append(f'                  <div class="tt-data-row"><div class="col-label">{esc(a)}</div><div class="col-value">{b}</div></div>\n')
    lines.append('                </div>\n')
    return ''.join(lines)

def data_grid_3(rows, headers=('#', 'Element', 'What It Does')):
    lines = ['                <div class="tt-data-grid">\n']
    lines.append(f'                  <div class="tt-data-row tt-data-row-3 header"><div class="col-num">{headers[0]}</div><div class="col-label">{headers[1]}</div><div class="col-value">{headers[2]}</div></div>\n')
    for i, (a, b, c) in enumerate(rows, 1):
        lines.append(f'                  <div class="tt-data-row tt-data-row-3"><div class="col-num">{i}</div><div class="col-label">{esc(a)}</div><div class="col-value">{esc(c) if len(rows[0])==3 else esc(b)}</div></div>\n')
    return ''.join(lines)

def feature_grid(cards):
    lines = ['                <div class="tt-feature-grid">\n']
    icons = ['bi-compass', 'bi-signpost-split', 'bi-briefcase', 'bi-calendar3', 'bi-building', 'bi-robot', 'bi-people', 'bi-award', 'bi-flag', 'bi-layers', 'bi-diagram-3', 'bi-clipboard2-check', 'bi-mortarboard', 'bi-person-badge']
    for i, (title, text) in enumerate(cards):
        icon = icons[i % len(icons)]
        lines.append(f'                  <div class="tt-feature-card"><div class="tt-feature-icon"><i class="bi {icon}"></i></div><h5>{esc(title)}</h5><p>{esc(text)}</p></div>\n')
    lines.append('                </div>\n')
    return ''.join(lines)

def callout(kind, title, text):
    icons = {'tip': 'bi-lightbulb-fill', 'note': 'bi-info-circle-fill', 'important': 'bi-exclamation-triangle-fill'}
    cls = f'tt-callout tt-callout-{kind}'
    return f'''                <div class="{cls} mt-3">
                  <i class="bi {icons.get(kind, "bi-info-circle-fill")}"></i>
                  <div><strong>{esc(title)}</strong> {esc(text)}</div>
                </div>
'''

def callout_rich(kind, title, inner_html):
    icons = {'tip': 'bi-lightbulb-fill', 'note': 'bi-info-circle-fill', 'important': 'bi-exclamation-triangle-fill'}
    cls = f'tt-callout tt-callout-{kind}'
    return f'''                <div class="{cls} mt-3">
                  <i class="bi {icons.get(kind, "bi-info-circle-fill")}"></i>
                  <div><strong>{esc(title)}</strong>{inner_html}</div>
                </div>
'''

STREAM_CHOICES_HTML = raw_html('''                <h4 class="tt-subheading">Understanding Stream Choices</h4>
                <p>The Career Planning Hub explains common stream combinations and their implications.</p>
                <div class="tt-stream-block">
                  <h4 class="tt-subheading">Science Stream</h4>
                  <p>Common subject combinations:</p>
                  <ul class="tt-milestones">
                    <li>Physics + Chemistry + Mathematics (PCM)</li>
                    <li>Physics + Chemistry + Biology (PCB)</li>
                    <li>Physics + Chemistry + Mathematics + Biology (PCMB)</li>
                  </ul>
                  <p>Possible pathways include:</p>
                  <ul class="tt-milestones">
                    <li>Engineering</li>
                    <li>Medicine</li>
                    <li>Research</li>
                    <li>Architecture</li>
                    <li>AI &amp; Robotics</li>
                    <li>Biotechnology</li>
                    <li>Data Science</li>
                  </ul>
                </div>
                <div class="tt-stream-block">
                  <h4 class="tt-subheading">Commerce Stream</h4>
                  <p>Common combinations:</p>
                  <ul class="tt-milestones">
                    <li>Commerce with Mathematics</li>
                    <li>Commerce without Mathematics</li>
                  </ul>
                  <p>Possible pathways include:</p>
                  <ul class="tt-milestones">
                    <li>Chartered Accountancy</li>
                    <li>Finance</li>
                    <li>Economics</li>
                    <li>Banking</li>
                    <li>Business Management</li>
                    <li>Entrepreneurship</li>
                    <li>Investment Analysis</li>
                  </ul>
                </div>
                <div class="tt-stream-block">
                  <h4 class="tt-subheading">Humanities Stream</h4>
                  <p>Common subjects include:</p>
                  <ul class="tt-milestones">
                    <li>Psychology</li>
                    <li>Political Science</li>
                    <li>Sociology</li>
                    <li>Economics</li>
                    <li>History</li>
                    <li>Geography</li>
                    <li>Literature</li>
                  </ul>
                  <p>Possible pathways include:</p>
                  <ul class="tt-milestones">
                    <li>Law</li>
                    <li>Civil Services</li>
                    <li>Psychology</li>
                    <li>Media</li>
                    <li>Design</li>
                    <li>Education</li>
                    <li>Public Policy</li>
                  </ul>
                </div>
''')

STREAM_PARENT_NOTE = callout_rich('note', 'Parent Guidance Note',
    p('Parents should avoid choosing streams based only on:') +
    ul(['Marks', 'Social prestige', 'Family expectations', 'Peer comparison']) +
    p('The right stream depends on the student\'s:') +
    ul(['Aptitude', 'Interests', 'Personality', 'Career goals', 'Learning preferences'])
)

def class_pills(items):
    lines = ['                <div class="tt-class-pills">\n']
    for tag, text in items:
        lines.append(f'                  <div class="tt-class-pill"><span class="class-tag">{esc(tag)}</span><p>{esc(text)}</p></div>\n')
    lines.append('                </div>\n')
    return ''.join(lines)

def journey_stage(title, focus_items, goal):
    return (
        h4(title) +
        p('Primary focus:') +
        ul(focus_items) +
        p(f'Goal:{goal}')
    )

def section_shell(num, theme, icon, title, intro, body, step=None):
    step = step or f'{num:02d}'
    return f'''
        <!-- SECTION {num}: {title.upper()} -->
        <section class="tt-section theme-{theme}" id="section-{num}">
          <div class="tt-section-shell">
            <div class="tt-infographic-banner" data-step="{step}">
              <div class="tt-banner-icon-wrap"><i class="bi {icon}"></i></div>
              <div class="tt-banner-body">
                <span class="tt-banner-tag"><i class="bi bi-signpost-fill"></i> Tour Stop {num}</span>
                <h2>{esc(title)}</h2>
                {intro}
              </div>
            </div>
            <div class="tt-section-body">
          <div class="tt-timeline">
{body}
          </div>
                    </div>
          </div>
        </section>
'''

def timeline_item(dot, title, content):
    return f'''            <div class="tt-timeline-item">
              <div class="tt-timeline-dot">{dot}</div>
              <div class="tt-timeline-card">
                <h3>{esc(title)}</h3>
{content}              </div>
            </div>
'''

def banner_intro(*paragraphs):
    return '\n'.join(f'                <p class="tt-banner-intro">{p}</p>' for p in paragraphs)

# SECTION 1 — Overview intro (exact doc paragraphs 83–105)
s1_intro = raw_html('''                <p class="tt-banner-intro">Choosing a career today is significantly more complex than it was a decade ago.</p>
                <p class="tt-banner-intro">Earlier, students typically considered a limited number of traditional professions such as engineering, medicine, law, or government services. Today, rapid technological advancement and industry transformation have created thousands of new opportunities across emerging sectors such as:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Artificial Intelligence</li>
                  <li>Data Science</li>
                  <li>Climate Technology</li>
                  <li>Digital Media</li>
                  <li>Robotics</li>
                  <li>Behavioral Science</li>
                  <li>Product Design</li>
                  <li>Cybersecurity</li>
                  <li>Biotechnology</li>
                </ul>
                <p class="tt-banner-intro">This expansion of opportunities is exciting—but it also creates confusion.</p>
                <p class="tt-banner-intro">Students often struggle with questions such as:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Which stream should I choose after Class 10?</li>
                  <li>Which careers will remain relevant in the future?</li>
                  <li>Should I choose passion or practicality?</li>
                  <li>What skills will matter most in the next decade?</li>
                  <li>Which college and degree align with my goals?</li>
                </ul>
                <p class="tt-banner-intro">Without structured guidance, such decisions can become overwhelming.</p>
                <p class="tt-banner-intro">This is where TopTeen helps.</p>
                <p class="tt-banner-intro">TopTeen is a comprehensive career readiness platform designed specifically for students from Classes 9–12. It combines self-discovery, structured career exploration, psychometric science, skill development, exam preparation, and AI-enabled guidance into a single integrated ecosystem.</p>
                <p class="tt-banner-intro">Instead of relying on assumptions, peer pressure, or incomplete awareness, TopTeen helps students make data-informed, evidence-based career decisions.</p>
''')

# Build sections
sections = []

# SECTION 1
s1_body = ''
s1_body += timeline_item('1.1', 'What is TopTeen?',
    p('TopTeen is a digital career guidance ecosystem built to help students understand themselves and make better academic and career decisions.') +
    p('It supports students in:') +
    ul(['Understanding strengths and natural abilities', 'Discovering career opportunities', 'Selecting the right stream', 'Building future-ready skills', 'Preparing for competitive exams', 'Planning college pathways', 'Receiving personalized guidance']) +
    p('TopTeen acts as a long-term career companion—from early exploration in Class 9 to critical decision-making after Class 12.')
)

s1_body += timeline_item('1.2', 'What TopTeen Helps You Do',
    data_grid([
        ('Self Discovery', 'Understand your aptitude, interests, personality, and strengths'),
        ('Stream Selection (Class 10)', 'Take the Stream Sorter Test to identify suitable academic streams'),
        ('Career Direction (Class 12)', 'Use the Career Direction Test for long-term career clarity'),
        ('Career Exploration', 'Explore 17 major career clusters and hundreds of career pathways'),
        ('Skill Development', 'Build communication, leadership, and future-ready skills'),
        ('Test Preparation', 'Prepare for entrance exams and global assessments'),
        ('College Planning', 'Explore higher education and admission pathways'),
        ('AI Guidance', 'Receive instant support from the AI Career Counsellor'),
    ], ('Area', 'What It Means for You'))
)

s1_body += timeline_item('1.3', 'Who Should Use This Guide?',
    p('This handbook is intended for:') +
    defn_list([
        ('Students', 'Especially students in Classes 9–12 who are actively exploring academic and career options.'),
        ('Parents', 'Parents who wish to support their children with informed and balanced guidance.'),
        ('Schools', 'Educational institutions using TopTeen for structured career readiness programs.'),
        ('Career Counsellors', 'Professionals helping students navigate educational and career decisions.'),
    ])
)

s1_body += timeline_item('1.4', 'How TopTeen is Different',
    p('Most education platforms focus on only one component:') +
    ul(['Career assessments', 'College search', 'Courses', 'Test preparation']) +
    p('TopTeen integrates all of these into a unified platform.') +
    h4('TopTeen\'s Key Differentiators') +
    defn_list([
        ('Scientific Assessments', 'Career decisions are supported by psychometric data and structured analysis.'),
        ('17 Career Clusters', 'Students gain exposure to both traditional and emerging careers.'),
        ('AI + Human Guidance', 'Technology enhances—not replaces—expert counselling.'),
        ('Complete Career Ecosystem', 'TopTeen supports students from discovery to decision.'),
        ('Student-Centric Design', 'Built specifically around the needs of Classes 9–12.'),
    ])
)

sections.append(section_shell(1, 1, 'bi-stars', 'Overview', s1_intro, s1_body))

# SECTION 2
s2_intro = raw_html('''                <p class="tt-banner-intro">TopTeen is accessible across multiple devices and is designed to provide a seamless user experience.</p>
                <p class="tt-banner-intro">Supported devices include:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Desktop</li>
                  <li>Laptop</li>
                  <li>Tablet</li>
                  <li>Mobile Browser</li>
                </ul>
                <p class="tt-banner-intro">No application installation is required.</p>
''')

s2_body = timeline_item('2.1', 'Platform Address',
    p('Visit:') +
    p_html('<strong>www.topteen.in</strong>') +
    p('Students may also receive:') +
    ul(['School-specific login links', 'QR codes', 'Shared access credentials'])
) + timeline_item('2.2', 'Creating Your Account',
    p('First-time users can register using the following steps:') +
    ol(['Visit TopTeen', 'Click <strong>Sign Up / Login</strong>', 'Enter email or mobile number', 'Verify using OTP', 'Create a password']) +
    p('Complete profile information:') +
    ul(['Full Name', 'Date of Birth', 'Class', 'School', 'City', 'Academic Stream (if applicable)']) +
    p('A complete profile improves recommendation accuracy.')
) + timeline_item('2.3', 'Logging In',
    p('Returning users can log in easily.') +
    p('Steps:') +
    ol(['Visit the homepage', 'Click <strong>Login</strong>', 'Enter credentials', 'Access the Student Dashboard'])
) + timeline_item('2.4', 'Password / OTP Issues',
    p('Common solutions include:') +
    h4('OTP Not Received') +
    ul(['Wait 60 seconds', 'Use Resend OTP', 'Check spam folder']) +
    h4('Forgotten Password') +
    p('Use Forgot Password to reset credentials.') +
    h4('Technical Issue') +
    p('Contact support:') +
    p_html('<a href="mailto:info@topteen.in">info@topteen.in</a>')
)

sections.append(section_shell(2, 2, 'bi-box-arrow-in-right', 'Accessing TopTeen', s2_intro, s2_body))

# SECTION 3
nav_rows = [
    ('TopTeen Logo', 'Return to homepage'),
    ('About Us', 'Learn about TopTeen'),
    ('Discover', 'Explore opportunities'),
    ('Resources', 'Access learning content'),
    ('Assessments', 'Take psychometric tests'),
    ('Learning', 'Skill development courses'),
    ('TestPrep', 'Entrance exam preparation'),
    ('Search', 'Find content quickly'),
    ('Notifications', 'Platform alerts and updates'),
    ('Profile/Login', 'Account access'),
    ('Language Selector', 'Switch supported languages'),
]
nav_grid = '                <div class="tt-data-grid">\n'
nav_grid += '                  <div class="tt-data-row tt-data-row-3 header"><div class="col-num">#</div><div class="col-label">Navigation Item</div><div class="col-value">Purpose</div></div>\n'
for i, (a, b) in enumerate(nav_rows, 1):
    nav_grid += f'                  <div class="tt-data-row tt-data-row-3"><div class="col-num">{i}</div><div class="col-label">{esc(a)}</div><div class="col-value">{esc(b)}</div></div>\n'
nav_grid += '                </div>\n'

s3_body = timeline_item('3.1', 'The Top Navigation Bar',
    p('The homepage navigation provides access to all major platform sections.') + nav_grid
) + timeline_item('3.2', 'Homepage Sections',
    p('The homepage highlights major offerings through structured sections.') +
    p('Key sections include:') +
    ul(['Hero Banner', 'Discover', 'Resources', 'Assessments', 'Learning', 'TestPrep', 'Success Stories', 'Platform Highlights']) +
    p('Each section acts as an entry point into deeper exploration.')
) + timeline_item('3.3', 'Menus, Cards & Quick Actions',
    p('TopTeen uses a modern card-based interface for easy navigation.') +
    p('Common quick actions include:') +
    ul(['Start Assessment', 'Explore Careers', 'Save Resource', 'View Details', 'Continue Learning', 'Bookmark Content']) +
    p('This design ensures students can move efficiently between sections without confusion.')
)

sections.append(section_shell(3, 3, 'bi-compass-fill', 'Navigating the Platform',
    banner_intro(
        'TopTeen is designed for intuitive navigation and a smooth user experience.',
        'Whether using mobile or desktop, the structure remains simple and user-friendly.',
    ), s3_body))

# SECTION 4 - Discover (full)
s4_intro = raw_html('''                <p class="tt-banner-intro">The Discover section is designed to broaden a student's awareness beyond conventional academic pathways. While many students are familiar with only a limited number of professions—such as engineering, medicine, law, or chartered accountancy—the modern world offers thousands of career possibilities across both traditional and emerging sectors.</p>
                <p class="tt-banner-intro">Discover helps students explore these opportunities in a structured way.</p>
                <p class="tt-banner-intro">This section enables students to understand:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Opportunities beyond academics</li>
                  <li>Skill-building experiences</li>
                  <li>Career planning pathways</li>
                  <li>College admission processes</li>
                </ul>
                <p class="tt-banner-intro">The Discover section includes four major components:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Extracurricular Activities</li>
                  <li>Vocational Courses</li>
                  <li>Career Planning Hub</li>
                  <li>College Admissions Guidance</li>
                </ul>
                <p class="tt-banner-intro">Together, these help students develop a wider perspective on education and career success.</p>
''')

s4_body = timeline_item('4.1', 'Extracurricular Activities',
    p('Academic excellence is important, but success in higher education and professional life increasingly depends on being a well-rounded individual.') +
    p('Top universities and employers value students who demonstrate initiative, leadership, creativity, teamwork, and discipline—qualities often developed through extracurricular participation.') +
    p('Examples of extracurricular activities include:') +
    ul(['Sports and Athletics', 'Music and Performing Arts', 'Debate and Public Speaking', 'Coding Clubs and Robotics', 'Creative Writing', 'Theatre and Drama', 'Social Service and Volunteering', 'Entrepreneurship Competitions', 'Leadership Programs', 'Community Projects']) +
    h4('Why Extracurricular Activities Matter') +
    p('Extracurricular participation helps students build essential life skills.') +
    defn_list([
        ('Confidence Building', 'Students become more comfortable expressing themselves and engaging with others.'),
        ('Leadership Development', 'Managing teams, events, and responsibilities strengthens leadership capabilities.'),
        ('Teamwork & Collaboration', 'Students learn to work effectively with diverse groups of people.'),
        ('Discipline & Consistency', 'Regular participation builds commitment, routine, and resilience.'),
        ('Stronger College Profile', 'Achievements beyond academics significantly strengthen college applications.'),
    ]) +
    tip_callout('Do not join activities only to "build your profile." Choose activities that genuinely interest you and contribute to long-term growth.')
) + timeline_item('4.2', 'Vocational Courses',
    p('Vocational education focuses on practical, skill-based learning that directly improves employability and industry readiness.') +
    p('Unlike purely theoretical education, vocational courses emphasize:') +
    ul(['Hands-on learning', 'Practical application', 'Technical competence', 'Real-world problem solving', 'Industry exposure']) +
    p('Examples of vocational learning areas include:') +
    ul(['Graphic Design', 'Animation', 'Video Editing', 'Digital Marketing', 'Web Development', 'Photography', 'Fashion Design', 'Culinary Arts', 'Beauty & Wellness', 'Hospitality Services', 'Electronics Repair', 'Automotive Skills']) +
    h4('Who Benefits Most?') +
    p('Vocational learning is especially valuable for students who:') +
    ul(['Prefer practical learning over theoretical learning', 'Enjoy creating, building, or hands-on work', 'Want employable skills early', 'Aspire toward entrepreneurship', 'Prefer alternative career pathways']) +
    important_callout('Vocational education is not a secondary or inferior option. It is a powerful pathway to highly skilled professions, entrepreneurship, and industry specialization.')
) + timeline_item('4.3', 'Career Planning Hub',
    p('The Career Planning Hub is one of TopTeen\'s most valuable long-term planning tools.') +
    p('It provides a structured four-year roadmap (Class 9–12) that helps students understand how academic choices influence future career possibilities.') +
    p('Many students make critical decisions too late—often after Class 10 or even after Class 12—without fully understanding long-term consequences. The Career Planning Hub addresses this by helping students plan progressively.') +
    p('It enables students to understand:') +
    ul(['What subjects they will study each year', 'How subject combinations affect career options', 'Which streams open specific pathways', 'What milestones matter at each academic stage', 'How to prepare systematically for future success']) +
    p('Student Journey Map (Class 9–12):') +
    class_pills([
        ('Class 9', 'Self-discovery, career awareness, academic foundation'),
        ('Class 10', 'Stream selection, aptitude clarity, board preparation'),
        ('Class 11', 'Subject specialization, career narrowing, exam awareness'),
        ('Class 12', 'Career direction, admissions planning, higher education decisions'),
    ]) +
    STREAM_CHOICES_HTML +
    STREAM_PARENT_NOTE
) + timeline_item('4.4', 'College Admissions Guidance',
    p('College admissions today can feel complex due to:') +
    ul(['Multiple entrance exams', 'Different eligibility criteria', 'Varying admission timelines', 'Diverse application processes', 'Growing global opportunities']) +
    p('TopTeen simplifies this process. Students gain awareness of:') +
    ul(['Admission pathways', 'Eligibility requirements', 'Application deadlines', 'Required documentation', 'Course selection', 'College comparisons']) +
    p('This helps students and parents prepare strategically rather than react at the last minute.')
)

sections.append(section_shell(4, 4, 'bi-binoculars-fill', 'Discover', s4_intro, s4_body))

# SECTION 5 - Resources (full)
clusters = [
    'Agriculture, Natural Resources & Allied Sciences',
    'Architecture, Construction & Planning',
    'Arts, Humanities, Education & Training',
    'Business Management & Marketing',
    'Commerce, Economics & Finance',
    'Computer Applications',
    'Design, Fine Arts & Performing Arts',
    'Engineering & Technology',
    'Hospitality & Tourism',
    'Law & Public Safety',
    'Mass Communication & Media',
    'Health Sciences (Medicine, Paramedical & Rehabilitation)',
    'Pure Sciences & Research',
    'Sports & Physical Education',
    'Veterinary Sciences',
    'Government & Administrative Services',
    'Vocational Studies',
]

s5_intro = raw_html('''                <p class="tt-banner-intro">The Resources section provides curated educational content designed for both students and parents.</p>
                <p class="tt-banner-intro">This section transforms complex education and career information into structured, practical, easy-to-understand resources.</p>
                <p class="tt-banner-intro">TopTeen Resources include:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Blogs</li>
                  <li>E-books</li>
                  <li>Career Library</li>
                  <li>Video Library</li>
                </ul>
                <p class="tt-banner-intro">These resources support continuous learning and informed decision-making.</p>
''')

s5_body = timeline_item('5.1', 'Blogs',
    p('TopTeen\'s blog section offers regularly updated articles, insights, and guidance for both students and parents.') +
    p('Key topics include:') +
    ul(['Career awareness', 'Stream selection', 'Parenting for career success', 'Future career trends', 'Study strategies', 'College admissions', 'Skill development', 'Student motivation']) +
    h4('Benefits for Students') +
    p('Blogs help students:') +
    ul(['Learn about modern careers', 'Improve decision-making', 'Develop productivity habits', 'Stay informed about trends']) +
    h4('Benefits for Parents') +
    p('Blogs help parents:') +
    ul(['Understand emerging careers', 'Gain awareness of evolving education systems', 'Support children with informed guidance'])
) + timeline_item('5.2', 'E-books',
    p('The E-books section contains structured career-cluster guides based on curated information aligned with CBSE career awareness frameworks.') +
    p('Each e-book focuses on one major career cluster. These guides help students understand:') +
    ul(['Career opportunities', 'Required skills', 'Subject requirements', 'Degree pathways', 'Future scope']) +
    p('Examples include:') +
    ul(['Engineering & Technology', 'Health Sciences', 'Computer Applications', 'Commerce & Finance', 'Design & Fine Arts']) +
    p('These serve as mini career handbooks for deeper exploration.')
) + timeline_item('5.3', 'Career Library',
    p('The Career Library is one of TopTeen\'s core strengths. It provides structured information across 17 major career clusters.') +
    p('TopTeen Career Clusters:') +
    ul(clusters) +
    p('Each career profile explains:') +
    ul(['What the career involves', 'Required skills', 'Education pathway', 'Work environment', 'Career growth potential', 'Related professions']) +
    tip_callout('Do not limit exploration to only popular careers. Many high-growth emerging careers may align better with your strengths.')
) + timeline_item('5.4', 'Video Library',
    p('The Video Library contains career explainer videos designed for visual learning.') +
    p('Each video typically covers:') +
    ul(['Career overview', 'Nature of work', 'Required skills', 'Subject requirements', 'Educational pathway', 'Career scope', 'Growth opportunities']) +
    p('Videos help students understand careers faster and more intuitively.')
)

sections.append(section_shell(5, 5, 'bi-journal-richtext', 'Resources', s5_intro, s5_body))

# SECTION 6 - Assessments (full)
s6_intro = raw_html('''                <p class="tt-banner-intro">Assessments form the scientific foundation of personalized guidance in TopTeen.</p>
                <p class="tt-banner-intro">Career decisions become more accurate when based on structured understanding of a student's:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Aptitude</li>
                  <li>Interests</li>
                  <li>Personality</li>
                  <li>Learning style</li>
                  <li>Emotional intelligence</li>
                </ul>
                <p class="tt-banner-intro">TopTeen assessments are designed to provide this clarity.</p>
''')

s6_body = timeline_item('6.1', 'Assessment Overview',
    p('TopTeen offers multiple scientifically designed assessments:') +
    ul(['Stream Sorter Test', 'Career Direction Test', 'Four Pillars of Learning', 'Multiple Intelligence Test', 'EQ Test']) +
    important_callout_rich(
        p('There are no "right" or "wrong" answers in psychometric assessments.') +
        p('The goal is honest self-discovery, not scoring marks.') +
        p('Students should answer naturally rather than trying to guess ideal responses.')
    )
) + timeline_item('6.2', 'Stream Sorter Test (Class 10)',
    p('The Stream Sorter Test is designed specifically for Class 10 students. Its purpose is to help students choose the most suitable academic stream after board examinations.') +
    p('The assessment evaluates:') +
    ul(['Aptitude strengths', 'Subject preferences', 'Interest patterns', 'Learning styles', 'Career orientation']) +
    p('Possible recommendations include:') +
    ul(['Science', 'Commerce with Mathematics', 'Commerce without Mathematics', 'Humanities']) +
    h4('Common Mistake') +
    p('Students often choose streams based only on:') +
    ul(['Marks', 'Peer influence', 'Social prestige', 'External pressure']) +
    p('The Stream Sorter helps reduce such biases.')
) + timeline_item('6.3', 'Career Direction Test (Class 12)',
    p('This assessment is designed for Class 12 students. It helps answer critical questions such as:') +
    ul(['Which career cluster suits me best?', 'Which degree should I pursue?', 'Which college pathways fit my profile?', 'Which professions align with my strengths?']) +
    p('This assessment is particularly useful during final decision-making before higher education.')
) + timeline_item('6.4', 'Four Pillars of Learning',
    p('This assessment helps students understand how they learn most effectively. It improves awareness regarding:') +
    ul(['Learning efficiency', 'Concentration', 'Retention', 'Study habits', 'Academic confidence']) +
    p('Understanding learning preferences allows students to optimize study strategies.')
) + timeline_item('6.5', 'Multiple Intelligence Test',
    p('Based on Howard Gardner\'s theory, this assessment identifies dominant intelligence areas beyond conventional academics.') +
    p('Common intelligence areas include:') +
    ul(['Logical Intelligence', 'Linguistic Intelligence', 'Spatial Intelligence', 'Musical Intelligence', 'Interpersonal Intelligence', 'Intrapersonal Intelligence', 'Naturalistic Intelligence', 'Bodily-Kinesthetic Intelligence']) +
    p('This broadens the student\'s understanding of personal strengths.')
) + timeline_item('6.6', 'EQ Test',
    p('EQ stands for Emotional Quotient or Emotional Intelligence. This assessment evaluates:') +
    ul(['Self-awareness', 'Emotional regulation', 'Motivation', 'Empathy', 'Social skills', 'Relationship management']) +
    p('High emotional intelligence strongly supports leadership and long-term success.')
) + timeline_item('6.7', 'Understanding Assessment Reports',
    p('Assessment reports typically include:') +
    ul(['Score summaries', 'Strength analysis', 'Development areas', 'Stream suggestions', 'Career recommendations', 'Cluster matches', 'Improvement strategies']) +
    p('Best Practices for Taking Assessments:') +
    ul(['Answer honestly', 'Avoid overthinking', 'Choose natural responses', 'Take tests in a distraction-free environment', 'Avoid rushing through questions'])
)

sections.append(section_shell(6, 6, 'bi-clipboard2-check-fill', 'Assessments', s6_intro, s6_body))

# SECTION 7 - Learning (full)
s7_intro = raw_html('''                <p class="tt-banner-intro">In today's rapidly evolving world, academic excellence alone is no longer sufficient for long-term success. Students must also develop the practical, professional, and interpersonal skills required to thrive in higher education, workplaces, and entrepreneurial environments.</p>
                <p class="tt-banner-intro">The Learning section of TopTeen focuses on building these future-ready competencies.</p>
                <p class="tt-banner-intro">TopTeen's learning ecosystem is designed to help students develop:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Career readiness</li>
                  <li>College readiness</li>
                  <li>Professional readiness</li>
                  <li>Future skills</li>
                </ul>
                <p class="tt-banner-intro">The Learning section includes:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Career &amp; College Readiness Courses</li>
                  <li>Skill Development Courses</li>
                  <li>Career Counsellor Course</li>
                </ul>
                <p class="tt-banner-intro">These learning pathways help bridge the gap between traditional education and real-world expectations.</p>
''')

s7_body = timeline_item('Intro', 'Why Learning Beyond Academics Matters',
    p('School education provides foundational subject knowledge, but modern success increasingly depends on additional capabilities such as:') +
    ul(['Communication', 'Collaboration', 'Critical Thinking', 'Problem Solving', 'Emotional Intelligence', 'Leadership', 'Adaptability', 'Digital Literacy']) +
    p('These are commonly referred to as 21st-century skills or future skills. Top colleges, employers, and global institutions increasingly evaluate these competencies. Students who build these skills early gain a strong competitive advantage.')
) + timeline_item('7.1', 'Career & College Readiness Courses',
    p('These courses are designed specifically for students in Classes 9–12 to prepare them for academic, professional, and personal success. The objective is to help students transition smoothly from school to higher education and eventually into careers.') +
    p('Key learning areas include:') +
    ul(['Career Awareness', 'Goal Setting', 'Time Management', 'Productivity', 'Communication Skills', 'Interview Readiness', 'Presentation Skills', 'College Application Preparation', 'Resume Basics', 'Decision Making']) +
    h4('Benefits for Students') +
    p('These courses help students in multiple ways.') +
    defn_list([
        ('Greater Career Clarity', 'Students develop a clearer understanding of goals and pathways.'),
        ('Increased Confidence', 'Structured preparation reduces uncertainty and improves self-belief.'),
        ('Stronger Communication', 'Students improve written, verbal, and interpersonal communication.'),
        ('College Readiness', 'Students understand the expectations of higher education environments.'),
        ('Better Decision-Making', 'Students learn how to make informed academic and career choices.'),
    ]) +
    tip_callout('Begin building career readiness early rather than waiting until Class 12. Small improvements over time create significant long-term advantages.')
) + timeline_item('7.2', 'Skill Development Courses',
    p('Skill development is essential because industries evolve faster than traditional education systems. Many high-value professional skills are not formally taught in school.') +
    p('TopTeen offers courses focused on practical, transferable skills that support success across multiple career domains.') +
    p('Examples include:') +
    ul(['Digital Literacy', 'AI Awareness', 'Public Speaking', 'Creativity & Innovation', 'Personal Branding', 'Networking Skills', 'Collaboration', 'Leadership', 'Emotional Intelligence', 'Professional Etiquette']) +
    p('These skills are valuable regardless of whether a student chooses engineering, medicine, law, business, arts, or entrepreneurship.') +
    h4('Why Skills Matter') +
    p('A student may achieve excellent marks but still struggle in real-world settings if they lack critical soft and professional skills.') +
    p('Common gaps include:') +
    ul(['Poor communication', 'Limited adaptability', 'Weak collaboration', 'Low confidence', 'Poor problem-solving ability']) +
    p('Skill development transforms academic knowledge into practical capability.')
) + timeline_item('7.3', 'Career Counsellor Course',
    p('TopTeen offers a specialized Career Counsellor Course designed for professionals who wish to build expertise in career guidance.') +
    p('This program is particularly relevant for:') +
    ul(['School Counsellors', 'Teachers', 'Education Consultants', 'Career Coaches', 'Psychologists', 'HR Professionals', 'Trainers']) +
    p('The course develops expertise in:') +
    ul(['Career Counselling Frameworks', 'Psychometric Assessments', 'Student Profiling', 'Stream Selection Guidance', 'Career Mapping', 'College Planning', 'Counselling Methodologies', 'Future Career Trends']) +
    p('This program strengthens the quality of career guidance delivered to students.')
)

sections.append(section_shell(7, 7, 'bi-mortarboard-fill', 'Learning', s7_intro, s7_body))

# SECTION 8 - TestPrep (full)
s8_body = timeline_item('8.1', 'TestPrep Overview',
    p('TopTeen\'s TestPrep section covers:') +
    ul(['Class 10 Entrance Exams', 'Class 12 Entrance Exams', 'College-Level Entrance Exams', 'International Language Proficiency Exams']) +
    p('Students can use this section to understand:') +
    ul(['Exam structure', 'Eligibility criteria', 'Syllabus', 'Difficulty level', 'Preparation strategies', 'Application timelines']) +
    p('This enables smarter planning and better preparation.') +
    h4('Why Early Awareness Matters') +
    p('Many students discover important entrance exams too late.') +
    p('Late awareness can lead to:') +
    ul(['Poor preparation', 'Missed deadlines', 'Weak strategy', 'Reduced opportunities']) +
    p('Early awareness improves planning and performance.')
) + timeline_item('8.2', 'Class 10 Entrance Exams',
    p('Students in or after Class 10 may prepare for various competitive opportunities that build foundational aptitude and exam readiness.') +
    p('Examples include:') +
    ul(['Olympiads', 'NTSE-style Scholarship Exams', 'Polytechnic Entrance Exams', 'Foundation Competitive Exams', 'Specialized School Entrance Exams']) +
    p('These exams help students develop:') +
    ul(['Competitive exposure', 'Analytical ability', 'Problem-solving speed', 'Time management', 'Confidence']) +
    p('Class 10 is an ideal stage for developing strong exam discipline.')
) + timeline_item('8.3', 'Class 12 Entrance Exams',
    p('Class 12 is one of the most important academic years because many higher education pathways depend heavily on entrance exam performance.') +
    p('TopTeen helps students understand major exams across streams.') +
    exam_block('Engineering Entrance Exams',
        ['JEE Main', 'JEE Advanced', 'BITSAT', 'State Engineering Entrance Exams'],
        closing='These exams are important for admission into engineering institutes.') +
    exam_block('Medical Entrance Exams',
        ['NEET'],
        'Required for programs such as:',
        ['MBBS', 'BDS', 'AYUSH', 'Allied Medical Programs']) +
    exam_block('Law Entrance Exams',
        ['CLAT', 'AILET', 'SLAT'],
        'Required for:',
        ['Integrated Law Programs', 'National Law Universities', 'Private Law Schools']) +
    exam_block('Commerce & Management Entrance Exams',
        ['CUET', 'IPMAT', 'University-specific Entrance Tests'],
        'These support admissions into:',
        ['Business Management', 'Economics', 'Finance', 'Commerce Programs']) +
    exam_block('Design Entrance Exams',
        ['NID DAT', 'NIFT', 'UCEED'],
        closing='These are required for design and creative disciplines.') +
    exam_block('Architecture Entrance Exams',
        ['NATA', 'JEE Paper 2'],
        closing='These support architecture pathways.') +
    callout_rich('note', 'Parent Guidance Note',
        p('Parents should remember:') +
        p('A student\'s worth is never determined by a single examination.') +
        p('Entrance exams matter—but so do:') +
        ul(['Aptitude', 'Motivation', 'Skills', 'Consistency', 'Long-term fit']) +
        p('Balanced support leads to better outcomes than pressure.')
    )
) + timeline_item('8.4', 'College-Level Entrance Exams',
    p('Students planning postgraduate or advanced education may need additional competitive examinations.') +
    p('Examples include:') +
    ul(['CAT', 'GMAT', 'GRE', 'GATE', 'UPSC (Awareness Stage)', 'Professional Certification Exams']) +
    p('These exams support advanced specialization and leadership pathways.')
) + timeline_item('8.5', 'IELTS / TOEFL / PTE Preparation',
    p('Students planning international education often need English language proficiency tests.') +
    p('TopTeen supports awareness and preparation for:') +
    ul(['IELTS', 'TOEFL', 'PTE']) +
    p('These assessments evaluate:') +
    ul(['Reading', 'Writing', 'Listening', 'Speaking']) +
    p('Strong scores significantly improve global education opportunities.')
)

sections.append(section_shell(8, 8, 'bi-pencil-square', 'TestPrep',
    banner_intro(
        'Competitive examinations often determine access to top colleges, professional programs, scholarships, and global opportunities.',
        'The TestPrep section helps students understand and prepare for these exams in a structured manner. TopTeen provides preparation support across multiple categories of examinations.',
    ), s8_body))

# SECTION 9 - Dashboard (full)
s9_body = timeline_item('9.1', 'Dashboard Overview',
    p('Key dashboard sections include:') +
    data_grid([
        ('Dashboard', 'Your personalized home screen'),
        ('My Work', 'Track engagement and progress'),
        ('My Resumes', 'Build professional profiles'),
        ('My Scrapbook', 'Save and organize content'),
        ('Quick Links', 'Instant access to key features'),
        ('Psychometric Dashboard', 'View assessment insights and analytics'),
    ], ('Section', 'Purpose')) +
    p('Each section supports a specific aspect of the student journey.')
) + timeline_item('9.2', 'My Work',
    p('The My Work section tracks student engagement across the platform. This may include:') +
    ul(['Completed assessments', 'Learning progress', 'Saved tasks', 'Activity history', 'Pending actions']) +
    p('This helps students monitor consistency and progress.')
) + timeline_item('9.3', 'My Resumes',
    p('This section helps students build and manage professional profiles and resumes.') +
    p('Useful for:') +
    ul(['College applications', 'Internship opportunities', 'Summer programs', 'Competitions', 'Future job applications']) +
    p('Resume building at an early stage improves long-term professional readiness.')
) + timeline_item('9.4', 'My Scrapbook',
    p('The Scrapbook acts as a personalized storage area for saved content. Students can save:') +
    ul(['Career profiles', 'Articles', 'Notes', 'Resources', 'Bookmarked content']) +
    p('This makes revisiting useful information easy and efficient.')
) + timeline_item('9.5', 'Quick Links',
    p('Quick Links provide instant access to important features. Examples include:') +
    ul(['Your Calendar', 'Bookmarks', 'Start Swiping Careers', 'View My Matches', 'Top Recommendations', 'My Profile', 'My Invoices']) +
    p('These shortcuts improve navigation efficiency.')
) + timeline_item('9.6', 'Psychometric Dashboard',
    p('The Psychometric Dashboard is one of TopTeen\'s strongest differentiators. It helps students understand their cognitive, behavioral, and psychological profile through scientifically designed assessments.') +
    p('The dashboard includes:') +
    ul(['Statistics', 'Suggested Streams', 'Psychometric Reports', 'Performance Insights', 'Psychometric Analytics', 'Skill Readiness Index']) +
    p('This transforms raw assessment scores into actionable insights.')
) + timeline_item('9.7', 'Statistics & Analytics',
    p('Students can view performance indicators such as:') +
    ul(['Trophies Unlocked', 'Total Points', 'Daily Streak', 'Current Level']) +
    p('These gamified elements improve engagement, consistency, and motivation.')
) + timeline_item('9.8', 'Suggested Streams',
    p('Based on psychometric performance, TopTeen recommends academic streams aligned with the student\'s profile.') +
    p('Examples include:') +
    ul(['Science', 'Commerce with Mathematics', 'Commerce without Mathematics', 'Humanities']) +
    p('Recommendations are based on:') +
    ul(['Aptitude', 'Interests', 'Personality', 'Cognitive strengths']) +
    p('These suggestions support informed stream selection.')
) + timeline_item('9.9', 'Skill Readiness Index',
    p('The Skill Readiness Index highlights aptitude strengths across major reasoning domains.') +
    p('Common reasoning areas include:') +
    ul(['Mechanical Reasoning', 'Critical Reasoning', 'Language Skills', 'Numerical Reasoning', 'Verbal Reasoning', 'Spatial Reasoning']) +
    p('This helps identify:') +
    defn_list([
        ('Strength Areas', 'Skills where the student naturally performs well.'),
        ('Development Areas', 'Skills that require improvement.'),
        ('Career Alignment', 'Career pathways that best match the student\'s profile.'),
    ]) +
    important_students_callout_rich(
        p('Your psychometric report is a guidance tool—not a permanent label.') +
        p('Its purpose is to:') +
        ul(['Improve self-awareness', 'Strengthen decision-making', 'Expand career exploration', 'Support better planning']) +
        p('Use it to guide choices—not limit possibilities.')
    )
)

s9_intro = raw_html('''                <p class="tt-banner-intro">The Student Dashboard is the personalized workspace students access after logging into TopTeen.</p>
                <p class="tt-banner-intro">It provides a centralized view of:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Progress tracking</li>
                  <li>Saved resources</li>
                  <li>Career recommendations</li>
                  <li>Assessment insights</li>
                  <li>Psychometric analytics</li>
                  <li>Personalized guidance</li>
                </ul>
                <p class="tt-banner-intro">It functions as the student's primary control center within the platform.</p>
''')

sections.append(section_shell(9, 9, 'bi-house-heart-fill', 'Student Dashboard', s9_intro, s9_body))

# SECTION 10 - AI (full)
s10_intro = raw_html('''                <p class="tt-banner-intro">One of TopTeen's most powerful differentiators is the AI Career Counsellor.</p>
                <p class="tt-banner-intro">Students often face questions at different stages of their academic journey, such as:</p>
                <ul class="tt-milestones tt-banner-list">
                  <li>Which stream should I choose after Class 10?</li>
                  <li>What careers match my strengths and interests?</li>
                  <li>Which degree is required for a specific profession?</li>
                  <li>Which colleges should I consider?</li>
                  <li>How should I prepare for future opportunities?</li>
                </ul>
                <p class="tt-banner-intro">Traditionally, students had to wait for scheduled counselling sessions to get answers. However, questions often arise unexpectedly and require immediate clarification.</p>
                <p class="tt-banner-intro">The AI Career Counsellor solves this problem by providing intelligent, instant, and personalized guidance.</p>
                <p class="tt-banner-intro">It acts as a smart assistant available anytime to support students in their decision-making journey.</p>
''')

s10_body = timeline_item('10.1', 'What You Can Ask',
    p('Students can ask questions across multiple career-related domains.') +
    ai_domain_block('Stream Selection', [
        'Which stream is most suitable for me?',
        'Should I choose PCM or PCB?',
        'Is Commerce with Mathematics the right choice for me?',
        'How do I know if Humanities suits me?',
    ], 'The AI assistant helps students evaluate stream choices based on strengths and goals.') +
    ai_domain_block('Career Exploration', [
        'What does a Data Scientist do?',
        'Is Psychology a good career?',
        'What careers exist in Design?',
        'What is the future scope of AI?',
    ], 'This helps students explore careers with better awareness.') +
    ai_domain_block('College & Degree Planning', [
        'Which degree is needed for Architecture?',
        'What is the difference between B.Tech and B.E.?',
        'Which colleges are best for Law?',
        'Should I study in India or abroad?',
    ], 'These questions help students compare pathways and make informed choices.') +
    ai_domain_block('Preparation Strategy', [
        'How should I prepare for JEE?',
        'What should I do in Class 11 for Medicine?',
        'How can I improve aptitude skills?',
        'What should I focus on this year?',
    ], 'This helps students develop structured action plans.')
) + timeline_item('10.2', 'Starting a Conversation',
    p('Using the AI Career Counsellor is simple.') +
    h4('Step 1 — Open the Assistant') +
    p('Access the AI chat interface from the platform.') +
    h4('Step 2 — Ask Your Question') +
    p('Type your question naturally.') +
    p('Example:') +
    p('I am in Class 10 and confused between Science and Commerce.') +
    p('No special formatting is required.') +
    h4('Step 3 — Receive Guidance') +
    p('The AI generates relevant guidance based on your question.') +
    h4('Step 4 — Ask Follow-Up Questions') +
    p('Students are encouraged to continue the conversation for deeper clarity.') +
    p('Examples:') +
    ul(['Which subjects matter most?', 'Which colleges should I consider?', 'What skills should I develop?']) +
    p('Career clarity often improves through iterative questioning.')
) + timeline_item('10.3', 'Best Practices & Limitations',
    p('To get better responses from the AI Career Counsellor:') +
    h4('Ask Specific Questions') +
    p('Instead of asking:') +
    p('Tell me about careers.') +
    p('Ask:') +
    p('Which careers suit students strong in logical reasoning and problem solving?') +
    p('Specific questions lead to more relevant responses.') +
    h4('Provide Context') +
    p('Mention details such as:') +
    ul(['Class', 'Stream', 'Interests', 'Goals', 'Assessment results (if available)']) +
    p('This improves personalization.') +
    h4('Ask Follow-Up Questions') +
    p('Career planning is rarely solved in one question.') +
    p('The more you explore, the more clarity you gain.') +
    callout_rich('important', 'Important Limitation',
        p('The AI Career Counsellor is a guidance tool, not a replacement for professional counselling in sensitive situations.') +
        p('It should not replace human support for:') +
        ul(['Emotional distress', 'Family conflict', 'Personal crises', 'Mental health concerns', 'Complex psychological concerns']) +
        p('In such cases, students should seek help from:') +
        ul(['Parents', 'School Counsellors', 'Trusted Teachers', 'Qualified Mental Health Professionals'])
    )
)

sections.append(section_shell(10, 10, 'bi-robot', 'AI Career Counsellor', s10_intro, s10_body))

# SECTION 11 - Profile (full)
s11_body = timeline_item('11.1', 'My Profile',
    p('The profile section stores important student information. Students can view and update:') +
    ul(['Personal details', 'Academic information', 'School details', 'Stream information', 'Interests', 'Career goals']) +
    h4('Why this matters') +
    p('Accurate profile data leads to better:') +
    ul(['Career recommendations', 'Stream suggestions', 'Personalized content', 'AI guidance']) +
    p('Students should periodically review and update their profile.')
) + timeline_item('11.2', 'Notifications',
    p('Notifications help students stay informed about important updates. Examples include:') +
    ul(['New resources', 'Assessment reminders', 'Platform announcements', 'Personalized recommendations', 'Important alerts']) +
    p('Regularly checking notifications ensures students do not miss valuable opportunities.')
) + timeline_item('11.3', 'Language Settings',
    p('TopTeen supports language preferences to improve accessibility and user comfort.') +
    p('Students can select preferred languages where available. This is especially useful for users who prefer regional-language support for better understanding.')
) + timeline_item('11.4', 'My Invoices',
    p('This section stores payment and billing records. Students or parents can access:') +
    ul(['Purchase history', 'Subscription details', 'Payment receipts', 'Invoice records']) +
    p('This ensures transparency and easy financial tracking.')
) + timeline_item('11.5', 'Sign Out',
    p('Students should always sign out after using TopTeen on shared or public devices.') +
    p('This helps protect:') +
    ul(['Personal data', 'Assessment reports', 'Saved resources', 'Account security']) +
    p('Good digital habits are important for privacy and safety.')
)

sections.append(section_shell(11, 11, 'bi-person-gear', 'Profile & Settings',
    banner_intro(
        'The Profile & Settings section allows students to manage account information, preferences, and personalization settings.',
        'Maintaining an updated profile improves the quality of recommendations across the platform.',
    ), s11_body))

# SECTION 12 - Troubleshooting + Appendices
s12_body = timeline_item('12.1', 'Common Issues',
    data_grid([
        ('Unable to login', 'Verify credentials or reset password'),
        ('OTP not received', 'Wait 60 seconds and resend'),
        ('Page not loading', 'Refresh browser or check internet'),
        ('Assessment not loading', 'Retry using stable connection'),
        ('Feature missing', 'Check account access permissions'),
        ('Slow platform', 'Clear browser cache and refresh'),
    ], ('Issue', 'Recommended Action')) +
    p('Most issues can be resolved using these simple steps.')
) + timeline_item('12.2', 'Support Contacts',
    p('If issues persist, contact:') +
    p('TopTeen Support') +
    p_html('Email: <a href="mailto:info@topteen.in">info@topteen.in</a>') +
    p('You may also contact:') +
    ul(['Your school coordinator', 'Assigned career counsellor', 'Institutional administrator']) +
    p('Prompt reporting helps resolve issues faster.')
) + timeline_item('12.3', 'Quick Navigation Guide',
    '''                <div class="tt-quick-ref">
                  <div class="tt-data-row"><div class="col-label">I Want To…</div><div class="col-value">Go To…</div></div>
                  <div class="tt-data-row"><div class="col-label">Choose stream after Class 10</div><div class="col-value">Assessments → Stream Sorter</div></div>
                  <div class="tt-data-row"><div class="col-label">Decide career after Class 12</div><div class="col-value">Assessments → Career Direction Test</div></div>
                  <div class="tt-data-row"><div class="col-label">Explore careers</div><div class="col-value">Resources → Career Library</div></div>
                  <div class="tt-data-row"><div class="col-label">Build future skills</div><div class="col-value">Learning</div></div>
                  <div class="tt-data-row"><div class="col-label">Prepare for entrance exams</div><div class="col-value">TestPrep</div></div>
                  <div class="tt-data-row"><div class="col-label">View psychometric report</div><div class="col-value">Student Dashboard</div></div>
                  <div class="tt-data-row"><div class="col-label">Ask career questions</div><div class="col-value">AI Career Counsellor</div></div>
                  <div class="tt-data-row"><div class="col-label">Update profile</div><div class="col-value">My Profile</div></div>
                </div>
''' +
    p('This table provides quick navigation support for common tasks.')
)

sections.append(section_shell(12, 11, 'bi-life-preserver', 'Troubleshooting & Quick Reference',
    banner_intro(
        'Even well-designed digital platforms may occasionally experience technical issues.',
        'This chapter helps students and parents resolve common issues quickly.',
    ), s12_body))

OUT.write_text(''.join(sections), encoding='utf-8')
print(f'Wrote {OUT} ({len(sections)} sections)')
