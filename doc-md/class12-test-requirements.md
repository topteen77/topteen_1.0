# Class 12 Test Requirements

## Overview
All Class 12 psychometric test pages must include the same features as Class 10 tests for consistency and user experience.

## Required Features

### 1. Internet Speed Meter Widget
- **Location**: Header/top bar (both desktop and mobile versions)
- **Functionality**:
  - Shows download and upload speed in Mbps
  - Updates every 5 seconds
  - Displays status: "Internet Stable" (green) or "Internet Unstable" (red)
  - Unstable if speed < 1 Mbps
  - Should not overlay the test area
- **Implementation**:
  - Include script: `{{ static('topteenfrontend/assets/js/internet-speed-meter.js') }}`
  - Desktop version: `d-none d-lg-flex` classes
  - Mobile version: `d-lg-none` classes
  - CSS classes: `.internet-speed-meter`, `.speed-status-badge`, `.speed-status-indicator`, `.speed-values`

### 2. Answer Quality Widget
- **Location**: Sidebar (desktop) and header (mobile)
- **Functionality**:
  - Tracks time spent per question
  - Shows average time per question
  - Displays status:
    - "Answering Carefully" (yellow/green) - if average time >= 3 seconds per question
    - "Not Carefully Attempted" (red/orange) - if average time < 3 seconds per question
  - Updates in real-time as user answers questions
- **Implementation**:
  - Track `questionStartTimes` for each question
  - Track `answerTimes` array
  - `MIN_TIME_PER_QUESTION = 3` seconds
  - Update widget after each answer selection
  - CSS classes: `.answer-quality-widget`, `.careful`, `.warning`
  - Desktop container: `.answer-quality-widget-desktop-container`
  - Mobile: `d-lg-none` class

### 3. Auto-Advance to Next Question
- **Functionality**:
  - When user selects an answer option (radio button or checkbox), automatically advance to the next question
  - Delay: 300ms after selection (to show the selection before advancing)
  - Only advance if there are more questions remaining
  - Works for both single-choice (radio) and multiple-choice (checkbox) questions
- **Implementation**:
  ```javascript
  // For radio buttons (single choice)
  $(document).on('change', 'input[type="radio"]', function () {
    const questionNum = $(this).closest('.question').attr('id').replace('question', '');
    const radioName = 'question_' + questionNum;
    const isChecked = $('input[name="' + radioName + '"]:checked').length > 0;
    
    // Record time spent
    if (questionStartTimes[currentQuestion]) {
      const timeSpent = (Date.now() - questionStartTimes[currentQuestion]) / 1000;
      answerTimes.push(timeSpent);
      updateAnswerQualityWidget();
    }
    
    if (isChecked && currentQuestion < totalQuestions) {
      setTimeout(function () {
        currentQuestion++;
        showQuestion(currentQuestion);
        $('#error-message').hide();
      }, 300); // 300ms delay
    }
  });

  // For checkboxes (multiple choice) - similar logic but check if at least one is selected
  $(document).on('change', 'input[type="checkbox"]', function () {
    // Similar implementation but for checkboxes
    // May need to adjust based on test requirements
  });
  ```

## Files to Reference
- **Class 10 Test Templates** (for reference):
  - `template20/psychometric/test1_view.html` - Personality Assessment
  - `template20/psychometric/test2_view.html` - Career Interest Assessment
  - `template20/psychometric/test3_*.html` - Aptitude Assessment subtests
- **JavaScript File**:
  - `static/topteenfrontend/assets/js/internet-speed-meter.js`

## Testing Checklist
When implementing Class 12 test pages, verify:
- [ ] Internet speed meter displays on both desktop and mobile
- [ ] Speed updates every 5 seconds
- [ ] Status changes correctly based on speed (< 1 Mbps = unstable)
- [ ] Answer quality widget tracks time per question
- [ ] Widget updates after each answer
- [ ] Widget shows correct status (careful vs not careful)
- [ ] Auto-advance works when selecting radio button
- [ ] Auto-advance works when selecting checkbox (if applicable)
- [ ] 300ms delay before advancing
- [ ] All widgets are visible and don't overlay test content

## Notes
- All features should be implemented consistently across all Class 12 test pages
- Mobile and desktop versions should have separate widgets but same functionality
- Widgets should not interfere with test-taking experience
- Performance should be optimized (speed meter updates every 5 seconds, not continuously)

