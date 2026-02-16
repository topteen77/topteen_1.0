// Game Constants

// Career clusters with their associated streams
export const CAREER_CLUSTERS = {
  'Architecture': [
    'Architect',
    'Construction Manager',
    'Economic developmental planner',
    'Interior Designer',
    'Spatial Designer',
    'Urban Planner'
  ],
  'Arts/Humanities': [
    'Counselling',
    'Economist',
    'Writer',
    'Historian',
    'Political Science',
    'Human rights',
    'Language Specialist',
    'Education and training',
    'Philosophy',
    'Mass media and communication'
  ],
  'Buisness management and marketing': [
    'Event management',
    'Digital marketing',
    'Social media manager',
    'Real estate',
    'Human resource manager',
    'IT manager',
    'Sales management',
    'Entrepreneurship',
    'Research analyst',
    'PR manager'
  ],
  'Commerce and fianance': [
    'Accounts',
    'Stock market analysis',
    'Finanace analyst',
    'Fintech',
    'Inevetsment manger',
    'Insurance and trade',
    'Banking',
    'Tax analyst',
    'Ecommerce',
    'Buisness analyst'
  ],
  'Computer and IT': [
    'AI',
    'ML',
    'Cloud Computing',
    'Big Data',
    'Cybersecurity',
    'Software Engineering',
    'Data Science',
    'Data Analysis',
    'Data Engineering',
    'UI/UX Designer',
    'Web Developer',
    'Mobile Developer',
  ],
  'Engineering and technology': [
    'Mechanical Engineering',
    'Civil Engineering',
    'Electrical Engineering',
    'Computer Engineering',
    'Aerospace Engineering',
    'Biotech Engineering',
    'Chemical Engineering',
    'Environmental Engineering',
    'Mining Engineering',
    'Petroleum Engineering',
    'Electronics and Communication Engineering',
    'Naval Engineering'
  ],
  'Government and administrative services': [
    'Defence services',
    'IPS (Indian Police Service)',
    'IAS (Indian Administrative Service)',
    'IRS (Indian Railway Service)',
    'IFS (Indian Foreign Service)',
    'IPS (Indian Postal Service)',
    'Public health sector',
    'Education administartion',
    'Judicial services'
  ],
  'Medicine':[
    'Doctor/Physician',
    'Surgeon',
    'Paramedical services',
    'Physiotherapist',
    'Dentist',
    'Ayurvedic sector',
    'Therapist',
    'Nursing',
    'Veterinary science',
    'Pharmacy',
    'Psychiatric services'
  ],
  'Hospitality':[
    'Cabin Crew',
    'Chef',
    'Hotel management',
    'Wedding planner',
    'Event planner',
    'Adventure and tourism'
  ],
  'Sports and fitness':[
    'Nutritionist',
    'Dietician',
    'Yoga teacher',
    'Sports analyst',
    'Fitness trainer',
    'Athlete'
  ]
};

// Get all streams from all clusters (for backward compatibility)
export const STREAMS = Object.values(CAREER_CLUSTERS).flat();

// Education background options
export const EDUCATION_BACKGROUNDS = {
  '12th': {
    streams: ['Medical', 'Non-Medical', 'Arts', 'Commerce'],
    specificAreas: {
      'Medical': [
          'Pure Medical (PCB)',
          'Medical with Maths (PCMB)',
          'Medical with Psychology',
          'Medical with Biotechnology',
          'Medical with Computer Science',
          'Medical with Physical Education',
          'Medical with Informatics Practices (IP)'
      ],
      'Non-Medical': [
            'Pure Non-Medical (PCM)',
            'Non-Medical with Biology (PCMB)',
            'Non-Medical with Computer Science',
            'Non-Medical with Informatics Practices (IP)',
            'Non-Medical with Physical Education',
            'Non-Medical with Engineering Graphics'
        ],
      'Arts': [
            'Pure Arts / Humanities Core',
            'Arts with Maths',
            'Arts with Economics',
            'Arts with Psychology',
            'Arts with Sociology',
            'Arts with Geography',
            'Arts with Political Science',
            'Arts with History',
            'Arts with Fine Arts',
            'Arts with Music / Performing Arts',
            'Arts with Physical Education',
            'Arts with Home Science',
            'Arts with Computer Applications / Informatics Practices (IP)',
            'Arts with Legal Studies',
            'Arts with Entrepreneurship',
            'Arts with Mass Media / Mass Communication',
            'Arts with Fashion Studies'
        ],
      'Commerce': [
          'Pure Commerce (Without Maths)',
          'Commerce with Maths',
          'Commerce with Applied Maths',
          'Commerce with Informatics Practices (IP)',
          'Commerce with Computer Applications',
          'Commerce with Entrepreneurship',
          'Commerce with Statistics',
          'Commerce with Finance & Marketing Focus',
          'Commerce with Economics + Maths',
          'Commerce with Physical Education',
          'Commerce with Fine Arts',
          'Commerce with Psychology',
          'Commerce with Legal Studies',
          'Commerce with Mass Media / Mass Communication',
          'Commerce with Fashion Studies',
          'Commerce with Tourism'
      ]
    }
  }
  // Future: Can add more education backgrounds like 'Graduate', 'Post-Graduate', etc.
};

// Comparison parameters
export const PARAMETERS = [
  {
    id: 'job_placement',
    label: 'Job Placement Rate',
    description: 'Percentage of graduates finding employment'
  },
  {
    id: 'job_security',
    label: 'Job Security',
    description: 'Stability and long-term career prospects'
  },
  {
    id: 'fees_cost',
    label: 'Fees Cost',
    description: 'Educational expenses and affordability'
  },
  {
    id: 'location',
    label: 'Location Availability',
    description: 'Geographic availability of programs and jobs'
  },
  {
    id: 'career_growth',
    label: 'Career Growth Potential',
    description: 'Opportunities for advancement and salary growth'
  },
  {
    id: 'industry_demand',
    label: 'Industry Demand',
    description: 'Current and future market demand'
  }
];

// Game states
export const GAME_STATES = {
  SELECT_CAREER_CLUSTER: 'SELECT_CAREER_CLUSTER',
  SELECT_STREAMS: 'SELECT_STREAMS',
  SELECT_PARAMETERS: 'SELECT_PARAMETERS',
  FIGHTING: 'FIGHTING',
  RESULT: 'RESULT',
  COURSE_ELIGIBILITY: 'COURSE_ELIGIBILITY',
  COURSE_RESULTS: 'COURSE_RESULTS'
};

// Maximum selections
export const MAX_STREAM_SELECTION = 2;
export const MIN_PARAMETER_SELECTION = 1;

