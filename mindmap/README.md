# Career Paths Mindmap

This directory contains mindmap visualizations of career paths based on the career data from `career_html_output`.

## Files

### 1. `career_mindmap.html`
An interactive HTML mindmap visualization using D3.js. Features:
- **Interactive radial tree layout** showing all career categories and sample careers
- **Zoom and pan** functionality
- **Expand/collapse** nodes
- **Hover tooltips** for detailed information
- **Color-coded nodes**: 
  - Purple: Root (Career Paths)
  - Blue: Categories
  - Gold: Individual Careers

**How to use:**
- Open `career_mindmap.html` in a web browser
- Click on nodes to expand/collapse branches
- Use mouse wheel to zoom in/out
- Drag to pan around the mindmap
- Hover over nodes to see tooltips

### 2. `career_mindmap.json`
JSON format mindmap data that can be imported into various mindmap tools:
- **MindMeister**
- **XMind**
- **FreeMind**
- **MindMup**
- **Custom applications**

**Structure:**
- Root node: "Career Paths"
- 17 main categories
- Each category contains sample careers with descriptions

### 3. `career_mindmap.txt`
Simple text-based mindmap for quick reference or documentation.

## Career Categories

1. Agriculture, Natural Resources & Allied Sciences
2. Architecture, Construction & Planning
3. Arts, Humanities, Education & Training
4. Business Management & Marketing
5. Commerce, Economics & Finance
6. Computer Applications
7. Design & Fine Arts
8. Engineering & Technology
9. Government & Administrative Services
10. Health Sciences
11. Hospitality & Tourism
12. Law & Public Safety
13. Mass Communications & Media
14. Pure Sciences & Research
15. Sports, Fitness & Physical Education
16. Veterinary Sciences
17. Vocational

## Usage

### Viewing the HTML Mindmap
```bash
# Open in browser
firefox career_mindmap.html
# or
google-chrome career_mindmap.html
```

### Using the JSON Format
The JSON file can be imported into:
- Online mindmap tools (MindMeister, XMind Online)
- Desktop applications (FreeMind, XMind)
- Custom visualization tools

### Extending the Mindmap
To add more careers or categories:
1. Edit the JSON file to add new entries
2. Update the HTML file's `careerData` object
3. Regenerate the visualization

## Notes

- The mindmap includes sample careers from each category
- The actual `career_html_output` directory contains many more careers
- This is a representative sample for visualization purposes
- All career data is sourced from the `career_html_output` directory

## Technologies Used

- **D3.js v7**: For interactive visualization
- **HTML5/CSS3**: For structure and styling
- **JSON**: For data structure

