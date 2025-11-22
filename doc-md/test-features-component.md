# Test Features Component Documentation

## Overview

The Test Features Component is a centralized, reusable component that provides three key features for test pages:
1. **Internet Speed Meter** - Monitors download/upload speed and connection stability
2. **Answer Quality Widget** - Tracks time per question and indicates answer quality
3. **Auto-Advance Feature** - Automatically advances to next question after answer selection

## Features

### 1. Internet Speed Meter

- **Location**: Header/top bar (mobile) and sidebar (desktop)
- **Features**:
  - Shows download and upload speed in Mbps
  - Indicates stability (Stable/Unstable)
  - Updates every 5 seconds
  - Unstable if speed < 1 Mbps
  - Displays "Internet Stable" or "Internet Unstable"

### 2. Answer Quality Widget

- **Location**: Header/top bar (mobile) and sidebar (desktop)
- **Features**:
  - Tracks time per question
  - Calculates average time
  - Shows "Answering Carefully" or "Rushing Through" status
  - Updates dynamically based on answer speed
  - Minimum time threshold: 3 seconds per question

### 3. Auto-Advance Feature

- **Feature**: Automatically advances to next question 300ms after option selection
- **Implementation**: JavaScript event handlers for radio buttons and checkboxes
- **Delay**: 300ms after selection

## Usage

### Basic Usage

Include the component in your test template:

```jinja2
{# In your test template's additionalhead block #}
{% include 'template20/includes/test_features.html' 
   with enable_internet_speed_meter=true 
        enable_answer_quality_widget=true 
        enable_auto_advance=true %}

{# In your test template's additionaljs block #}
{% include 'template20/includes/test_features_js.html' 
   with enable_internet_speed_meter=true 
        enable_answer_quality_widget=true 
        enable_auto_advance=true %}
```

### Configuration Flags

All features can be individually enabled/disabled:

- `enable_internet_speed_meter` (default: `true`) - Show/hide Internet Speed Meter
- `enable_answer_quality_widget` (default: `true`) - Show/hide Answer Quality Widget
- `enable_auto_advance` (default: `true`) - Enable/disable auto-advance feature

### Example: Disable Specific Features

```jinja2
{# Disable Internet Speed Meter only #}
{% include 'template20/includes/test_features.html' 
   with enable_internet_speed_meter=false 
        enable_answer_quality_widget=true 
        enable_auto_advance=true %}
```

### Example: Enable Only Auto-Advance

```jinja2
{% include 'template20/includes/test_features.html' 
   with enable_internet_speed_meter=false 
        enable_answer_quality_widget=false 
        enable_auto_advance=true %}
```

## Required JavaScript Variables

The component expects these variables to exist in your test template's JavaScript:

### Required Variables

- `questions` - Array of question objects
- `currentQuestionIndex` - Current question index (number)
- `questionStartTimes` - Object tracking start times: `{index: timestamp}`
- `answerTimes` - Array of answer times in seconds: `[1.5, 2.3, 4.1, ...]`
- `MIN_TIME_PER_QUESTION` - Minimum time constant (default: 3 seconds)

### Required Functions

- `saveCurrentAnswer()` - Function to save the current answer
- `renderCurrentQuestion()` - Function to render the current question
- `updateProgress()` - Function to update progress indicators

### Example JavaScript Setup

```javascript
$(document).ready(function() {
  // Required variables
  let questions = [];
  let currentQuestionIndex = 0;
  let questionStartTimes = {};
  let answerTimes = [];
  const MIN_TIME_PER_QUESTION = 3;
  
  // Required functions
  function saveCurrentAnswer() {
    // Your save logic here
  }
  
  function renderCurrentQuestion() {
    // Your render logic here
    // Set questionStartTimes[currentQuestionIndex] = Date.now();
  }
  
  function updateProgress() {
    // Your progress update logic here
  }
  
  // Load questions and initialize
  // ...
});
```

## Placement in Template

### HTML Component Placement

Place the HTML component in your template where you want the widgets to appear:

**For Desktop Sidebar:**
```jinja2
<div class="col-lg-4">
  <!-- Sidebar content -->
  
  {# Internet Speed Meter and Answer Quality Widget for Desktop #}
  {% include 'template20/includes/test_features.html' 
     with enable_internet_speed_meter=true 
          enable_answer_quality_widget=true 
          enable_auto_advance=true %}
</div>
```

**For Mobile Header:**
```jinja2
<div class="d-lg-none">
  {# Internet Speed Meter and Answer Quality Widget for Mobile #}
  {% include 'template20/includes/test_features.html' 
     with enable_internet_speed_meter=true 
          enable_answer_quality_widget=true 
          enable_auto_advance=true %}
</div>
```

### JavaScript Component Placement

Place the JavaScript component in your template's `additionaljs` block:

```jinja2
{% block additionaljs %}
{{ super() }}
<!-- Your other scripts -->

{# Test Features JavaScript #}
{% include 'template20/includes/test_features_js.html' 
   with enable_internet_speed_meter=true 
        enable_answer_quality_widget=true 
        enable_auto_advance=true %}

<!-- Your test-specific JavaScript -->
<script>
  // Your test code here
</script>
{% endblock %}
```

## Integration with Views

### Passing Configuration from View

You can pass configuration flags from your Django view:

```python
def section_details(request, testId, section_id, session_id):
    context = {
        'section': section,
        'section_id': section_id,
        'session_id': session_id,
        'test_id': testId,
        # Feature flags
        'enable_internet_speed_meter': True,
        'enable_answer_quality_widget': True,
        'enable_auto_advance': True,
    }
    return render(request, 'template20/app_post_matric/section_details.html', context)
```

### Conditional Configuration

You can conditionally enable features based on test type or settings:

```python
def section_details(request, testId, section_id, session_id):
    test = get_object_or_404(Test, id=testId)
    
    context = {
        'section': section,
        'section_id': section_id,
        'session_id': session_id,
        'test_id': testId,
        # Enable features based on test configuration
        'enable_internet_speed_meter': test.enable_speed_meter if hasattr(test, 'enable_speed_meter') else True,
        'enable_answer_quality_widget': test.enable_quality_widget if hasattr(test, 'enable_quality_widget') else True,
        'enable_auto_advance': test.enable_auto_advance if hasattr(test, 'enable_auto_advance') else True,
    }
    return render(request, 'template20/app_post_matric/section_details.html', context)
```

## File Structure

```
templates/template20/
├── includes/
│   ├── test_features.html      # HTML + CSS for widgets
│   └── test_features_js.html    # JavaScript functions
└── app_post_matric/
    └── section_details.html     # Example usage
```

## Troubleshooting

### Widgets Not Showing

1. **Check flags are set correctly**: Ensure `enable_internet_speed_meter` and `enable_answer_quality_widget` are `true`
2. **Check CSS classes**: Ensure parent containers have correct Bootstrap classes (`d-lg-none` for mobile, `d-none d-lg-flex` for desktop)
3. **Check JavaScript variables**: Ensure all required variables are defined before the component loads

### Auto-Advance Not Working

1. **Check flag**: Ensure `enable_auto_advance` is `true`
2. **Check required functions**: Ensure `saveCurrentAnswer()`, `renderCurrentQuestion()`, and `updateProgress()` are defined
3. **Check question structure**: Ensure questions have correct radio/checkbox inputs with proper structure

### Answer Quality Widget Not Updating

1. **Check answerTimes array**: Ensure `answerTimes` is being populated when answers are selected
2. **Check questionStartTimes**: Ensure `questionStartTimes[currentQuestionIndex]` is set when question is rendered
3. **Check updateAnswerQualityWidget**: Ensure function is called after each answer selection

### Internet Speed Meter Not Working

1. **Check script loading**: Ensure `internet-speed-meter.js` is loaded (automatically included if flag is true)
2. **Check network**: Ensure test files are accessible for speed measurement
3. **Check console**: Check browser console for any JavaScript errors

## Examples

### Class 12 Section Tests

All 7 section test pages use this component:

- `/api/web/test/4/section/1/{session_id}/starttest/`
- `/api/web/test/4/section/2/{session_id}/starttest/`
- `/api/web/test/4/section/3/{session_id}/starttest/`
- `/api/web/test/4/section/4/{session_id}/starttest/`
- `/api/web/test/4/section/5/{session_id}/starttest/`
- `/api/web/test/4/section/6/{session_id}/starttest/`
- `/api/web/test/4/section/7/{session_id}/starttest/`

All use the same template: `template20/app_post_matric/section_details.html`

## Best Practices

1. **Always define required variables**: Ensure all required JavaScript variables are defined before including the component
2. **Initialize timing correctly**: Set `questionStartTimes[currentQuestionIndex] = Date.now()` when rendering each question
3. **Update widget after answers**: Call `updateAnswerQualityWidget()` after recording answer time
4. **Test with flags disabled**: Test your template with features disabled to ensure it still works
5. **Keep IDs consistent**: The component uses specific IDs (`answerQualityWidgetMobile`, `answerQualityWidgetDesktop`) - don't change them

## Version History

- **v1.0** (2025-01-21): Initial centralized component implementation
  - Internet Speed Meter
  - Answer Quality Widget
  - Auto-Advance Feature
  - Toggle flags for all features

