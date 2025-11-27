# Test Student Results Generation Plan

## Overview
Create comprehensive test data for Class 10 and Class 12 students under institute "testshanti" to test all possible result combinations, stream selections, and report generation. Include verification checklist system for manual testing.

## Key Components

### Class 10 Structure
- **3 Main Tests**: test1 (Personality/RIASEC), test2 (Interest), test3 (Aptitude/Intelligence)
- **Test 3 Subtests**: numerical, verbal, logical, emotional, machanical, language, spatial (7 subtests)
- **Models**: `app.models.Results`, `app.models.TestCompletion`, `app.models.Question`, `app.models.Answer`
- **RIASEC Combinations**: 120 possible 3-letter codes (6P3 = 6×5×4)
- **RIASEC Order**: R, I, A, S, E, C (for tie-breaking)
- **Result Storage**: Results model with test_paper, scores (JSON), results (JSON), selected_answers (JSON)
- **Stream Selection**: Based on personality, interest, and aptitude combinations

### Class 12 Structure
- **4 Main Tests**: Personality Assessment (HEXACO), Motivation Assessment, Career Interest Inventory (RIASEC), Aptitude Assessment
- **HEXACO Order**: H, E, X, A, C, O (for tie-breaking, 2-letter codes)
- **RIASEC Order**: R, I, A, S, E, C (for tie-breaking, 3-letter codes)
- **Aptitude Sections**: Logical Reasoning, Spatial Reasoning, Abstract Reasoning, Numerical Reasoning, Mechanical Reasoning, Clerical speed & Accuracy, Language & Verbal Reasoning
- **Aptitude Categorization**: 
  - Above Average: accuracy >= 70%
  - Average: accuracy >= 40% and < 70%
  - Below Average: accuracy < 40%
- **Models**: 
  - `app_post_matric.models.TestSession` - Main test session
  - `app_post_matric.models.SectionSession` - Individual section sessions for aptitude test (tracks start_time, end_time, is_completed per section)
  - `app_post_matric.models.UserResponse` - Answers (can link to section_session for aptitude sections)
  - `app_post_matric.models.TestResult` - Calculated results
  - `app_post_matric.models.TestTopCategories` - Category rankings
- **Result Storage**: 
  - TestSession for each test
  - SectionSession for each aptitude test section (one per section per test session)
  - UserResponse linked to TestSession (and optionally to SectionSession for aptitude)
  - TestResult linked to TestSession
- **Stream Selection**: Based on test results and category counts

## Key Logic Requirements Identified

### Class 12 HEXACO (Personality Assessment)
- **Two-letter code generation** from top 2 dimensions
- **HEXACO Order**: H, E, X, A, C, O (must be respected when scores tie)
- **Tie-breaking logic needed**:
  - When scores are different: Use top 2 by score
  - When 2 scores match: Use HEXACO order to break tie
  - When 3+ scores match: Use HEXACO order to select top 2
- **Lowest score**: Also needs tie-breaking using HEXACO order (reverse)
- **Current implementation**: `_process_personality_test` in `app_post_matric/views.py` line 2929 gets top 2, but doesn't handle ties with HEXACO order

### Class 10 RIASEC (test1)
- **Three-letter code generation** from top 3 dimensions  
- **RIASEC Order**: R, I, A, S, E, C (must be respected when scores tie)
- **Tie-breaking logic needed**:
  - When scores are different: Use top 3 by score
  - When 2 scores match: Use RIASEC order to break tie
  - When 3+ scores match: Use RIASEC order to select top 3
- **Current implementation**: `app/views.py` line 86-96 sorts and takes top 3, but doesn't handle ties with RIASEC order
- **Question mapping**: Questions mapped to categories via `variable_indices` (R: [1,7,13...], I: [2,8,14...], etc.)

## Implementation Steps

### 1. Create Management Command: create_test_students.py
- Get or create institute "testshanti" with sufficient credits
- Create ClassAndSection entries for "10-A", "12-A" (and variations if needed)
- **Student Naming Convention**:
  - **Class 10**: `st{num}-{riasec_code}-{stream}` (e.g., "st1-ria-pcm", "st2-ris-pcb", "st3-rie-commerce")
  - **Class 12**: `st{num}-{hexaco_code}-{category}` or `st{num}-{riasec_code}-{category}` (e.g., "st1-he-medical", "st2-ces-business", "st3-ria-engineering")
  - **Partial completion**: Descriptive names (e.g., "st3-test1only", "st4-personality-motivation", "st5-notstarted")
- **Institute Restriction**: All students created under "testshanti" institute only

### 2. Class 10 Test Student Creation
- Generate students covering:
  - **All RIASEC combinations** (120 codes: RIA, RIS, RIE, RIC, RAS, RAE, etc.)
  - **Different stream combinations** (PCM, PCB, Commerce, Arts, Humanities, Science)
  - **Test completion states**:
    - Not Started: No tests taken
    - Partial: Only test1, only test2, test1+test2, test3 partial
    - Complete: All 3 tests + all 7 test3 subtests
  - **Tied score scenarios**:
    - 2 scores match (e.g., R=10, I=10, A=8, S=7, E=6, C=5 → should use RI order)
    - 3 scores match (e.g., R=10, I=10, A=10, S=7, E=6, C=5 → should use RIA order)
- Generate Results records with proper JSON structure:
  - `scores`: `{'sum_R': X, 'sum_I': Y, ...}`
  - `results`: `{'Realistic': X%, 'Investigative': Y%, ...}`
  - `selected_answers`: `{'submitted_answers': {'Question_1': ans, ...}}`
- Create TestCompletion records matching completion states

### 3. Class 12 Test Student Creation
- Generate students covering:
  - **HEXACO 2-letter codes** (with tie-breaking scenarios):
    - Normal case: Different scores (e.g., H=45, E=40 → HE)
    - 2 scores match: Use HEXACO order (e.g., H=45, E=45, X=30 → HE)
    - 3+ scores match: Use HEXACO order (e.g., H=45, E=45, X=45 → HE)
  - **RIASEC 3-letter codes** (Career Interest test, with tie-breaking):
    - Normal case: Different scores
    - 2 scores match: Use RIASEC order
    - 3+ scores match: Use RIASEC order
  - **Aptitude categorization combinations**:
    - All Above Average (all sections >= 70%)
    - All Average (all sections 40-69%)
    - All Below Average (all sections < 40%)
    - Only Above Average (Average and Below Average empty)
    - Only Average (Above Average and Below Average empty)
    - Only Below Average (Above Average and Average empty)
    - Mixed: Various combinations with 1-2 categories empty
  - **Test completion states**:
    - Not Started: No tests taken
    - Partial: 1-3 tests complete
    - Complete: All 4 tests + all aptitude sections
- Generate TestSession records with proper start_time/end_time
- **For Aptitude Test**: Create SectionSession records for each section:
  - Set start_time and end_time for each section
  - Mark sections as completed (is_completed=True) when generating full results
  - Create partial completion scenarios (some sections complete, some not)
- Create UserResponse records:
  - Link to TestSession
  - For aptitude: Link to specific SectionSession via session_section field
  - Store answers in format: `{'sections': {'Section Name': {'submitted_answers': {...}}}}`
- Generate TestResult records with category_counts
- Create TestTopCategories with high_category JSON:
  ```json
  {
    "Above Average": ["Section1", "Section2"],
    "Average": ["Section3"],
    "Below Average": ["Section4"]
  }
  ```

### 4. Verification Checklist Generator: generate_verification_checklist.py
- **Output Format**: CSV/Excel with columns:
  - Student Name/ID
  - Test Case Description
  - Test Category (Class 10/Class 12)
  - Specific Check (RIASEC Code, HEXACO Code, Time Display, Aptitude Categorization, Spider Map, Performance Graph, Tabular Form, Tie-breaking)
  - Expected Result
  - Manual Verification Steps
  - Status (Passed/Failed/Pending)
  - Failure Reason (if failed, specify which test/check failed)
  - Report URL/Link (for quick access to student report)
- **Checklist Categories**:
  1. **Time Display Verification**:
     - All times in same unit (minutes preferred)
     - Class 10: Time calculation accuracy
     - Class 12: TestSession timing accuracy
     - Class 12: SectionSession timing accuracy
  2. **RIASEC Code Verification** (Class 10 & 12):
     - 3-letter code matches top 3 scores
     - Code uses RIASEC order when scores tie
     - All 6 scores displayed correctly on spider map/radar chart
  3. **HEXACO Code Verification** (Class 12):
     - 2-letter code matches top 2 scores
     - Code uses HEXACO order when scores tie
     - Lowest score uses reverse HEXACO order
  4. **Spider Map/Radar Chart Verification**:
     - All 6 RIASEC dimensions (R, I, A, S, E, C) displayed
     - Scores match stored values
     - Chart displays correctly
  5. **Aptitude Categorization**:
     - Above Average (>=70%) categorization correct
     - Average (40-69%) categorization correct
     - Below Average (<40%) categorization correct
  6. **Empty Category Handling**:
     - Graph displays correctly when categories are empty
     - Tabular form handles empty categories gracefully
     - No errors when one/two categories are empty
  7. **Performance Graph Display**:
     - All sections visible (Logical, Spatial, Abstract, Numerical, Mechanical, Clerical, Language)
     - Scores out of 15 (max per section)
     - Graph renders correctly
  8. **Tabular Form Display**:
     - Table shows below performance graph
     - Columns: Section Name, Score (out of 15), Total Questions, Correct Answers, Accuracy %
     - Data accuracy verified
  9. **Tie-breaking Logic**:
     - HEXACO order respected (H, E, X, A, C, O)
     - RIASEC order respected (R, I, A, S, E, C)

### 5. Institute Restriction
- All students created under "testshanti" institute only
- Filter views to show only testshanti students
- Reports accessible only through testshanti institute dashboard
- Verification checklist includes institute filter instructions

## Verification Requirements

### Time Display
- **Consistency**: All times in same unit (minutes preferred)
- **Class 10**: Time from Results.modified (if available) or calculate from test completion
- **Class 12**: 
  - TestSession: Calculate from start_time to end_time (in minutes)
  - SectionSession: Calculate per-section timing (in minutes)
  - Verify time shown in reports matches calculated time

### Class 12 RIASEC (Career Interest) Verification
- **3-letter code**: Verify code matches top 3 scores (e.g., CES from screenshot)
- **Spider Map/Radar Chart**: Verify all 6 dimensions (R, I, A, S, E, C) display with correct scores
- **Score accuracy**: Verify scores in chart match stored scores
- **Tie-breaking**: When scores match, verify code uses RIASEC order (R, I, A, S, E, C)

### Aptitude Test (4th Test) Verification
- **Categorization Thresholds**:
  - Above Average: accuracy >= 70%
  - Average: accuracy >= 40% and < 70%  
  - Below Average: accuracy < 40%
- **Empty Category Test Cases**:
  - All sections Above Average (Average and Below Average empty)
  - All sections Average (Above Average and Below Average empty)
  - All sections Below Average (Above Average and Average empty)
  - Mixed: Only Above Average empty, Only Average empty, Only Below Average empty
  - Two categories empty (only one category has sections)
- **Performance Graph**: 
  - Verify graph displays all sections even when categories are empty
  - Verify scores are out of 15 (max per section)
  - Sections: Logical Reasoning, Spatial Reasoning, Abstract Reasoning, Numerical Reasoning, Mechanical Reasoning, Clerical speed & Accuracy, Language & Verbal Reasoning
- **Tabular Form**:
  - Verify table displays below performance graph
  - Columns: Section Name, Score (out of 15), Total Questions, Correct Answers, Accuracy %
  - Verify table handles empty categories gracefully (no errors when categories are empty)

## Files to Create/Modify

1. **New File**: `demo-topteens/scripts/create_test_students.py`
   - Management command to create test students and results
   - Calculate and generate all combinations
   - Use existing student creation logic from `institute/views.py`
   - Implement tie-breaking logic for HEXACO and RIASEC
   - Generate realistic test data matching actual formats

2. **New File**: `demo-topteens/scripts/generate_verification_checklist.py`
   - Generate comprehensive verification checklist
   - Output CSV/Excel format for easy manual verification
   - Include student names, test cases, expected results, verification steps
   - Include status tracking (Passed/Failed/Pending)
   - Include report URLs for quick access

3. **Reference Files**:
   - `demo-topteens/institute/views.py` - Student creation logic
   - `demo-topteens/app/views.py` - Class 10 result creation (generate_pdf, submit_clicks)
   - `demo-topteens/app_post_matric/views.py` - Class 12 result creation
   - `demo-topteens/app/models.py` - Class 10 models
   - `demo-topteens/app_post_matric/models.py` - Class 12 models

## Combination Calculation

### Class 10 Combinations
- **RIASEC codes**: 120 combinations (6P3 = 6×5×4)
- **Stream combinations**: PCM, PCB, Commerce, Arts, Humanities, Science
- **Test completion states**: ~10-15 key combinations
- **Tied score scenarios**: ~20-30 test cases
- **Total test cases**: ~150-200 students covering key combinations

### Class 12 Combinations  
- **HEXACO codes**: 30 combinations (6P2 = 6×5) with tie scenarios
- **RIASEC codes**: 120 combinations (6P3 = 6×5×4) with tie scenarios
- **Aptitude categorization**: 
  - 3^7 = 2187 theoretical (but focus on key scenarios)
  - ~20-30 key combinations (all above, all average, all below, mixed, empty categories)
- **Test completion states**: 2^4 = 16 combinations
- **Total test cases**: ~200-250 students covering key combinations

## Execution

1. **Create Test Students**:
```bash
python manage.py create_test_students
```

2. **Generate Verification Checklist**:
```bash
python manage.py generate_verification_checklist
```

3. **Manual Verification Process**:
   - Open generated checklist CSV/Excel
   - Access reports via institute dashboard (filter by "testshanti")
   - Follow manual verification steps for each check
   - Mark status (Passed/Failed) for each item
   - Document failure reasons if any test fails
   - Use student names to quickly identify test cases

## Manual Verification Instructions

### Accessing Test Students
1. Login to institute dashboard
2. Filter by institute: "testshanti"
3. View student list - students named with test case identifiers
4. Click on student to view reports

### Verification Steps
1. **Time Display**: Check all time values use same unit (minutes)
2. **RIASEC Code**: Verify 3-letter code matches top 3 scores
3. **HEXACO Code**: Verify 2-letter code matches top 2 scores
4. **Spider Map**: Verify all 6 dimensions displayed with correct scores
5. **Aptitude Categories**: Verify sections categorized correctly (Above/Average/Below)
6. **Empty Categories**: Verify graph and table handle empty categories
7. **Tie-breaking**: Verify codes use correct order when scores match

## Notes
- All test data visible only in "testshanti" institute
- Student names include test case identifiers for easy identification
- Verification checklist provides step-by-step manual verification instructions
- Status tracking allows progress monitoring during verification process

