"""
Study Route & Eligibility Criteria Infographic Generator
Creates an infographic similar to the ACCA study route image
"""
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_study_route_infographic(
    career_name,
    routes_data,
    output_path,
    width=1200,
    height=1600,
    bg_color=(240, 248, 255)  # Light blue background
):
    """
    Create a study route infographic image
    
    Args:
        career_name: Name of the career
        routes_data: List of route dictionaries, each containing:
            - 'name': Route name (e.g., "Route 1: Commerce Focus")
            - 'color': Border color (R, G, B)
            - 'steps': List of step dictionaries with:
                - 'number': Step number
                - 'title': Step title
                - 'description': Step description (optional)
                - 'duration': Duration (optional)
        output_path: Path to save the image
        width: Image width in pixels
        height: Image height in pixels
        bg_color: Background color RGB tuple
    """
    # Create image
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fallback to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        route_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        step_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        desc_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        route_font = ImageFont.load_default()
        step_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
    
    # Title
    title = f"{career_name} Study Route & Eligibility Criteria"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, 40), title, fill=(25, 25, 112), font=title_font)  # Dark blue
    
    # Calculate route dimensions
    num_routes = len(routes_data)
    route_width = (width - 100) // num_routes - 20  # Margin between routes
    route_x_start = 50
    route_y_start = 120
    route_height = height - 300  # Leave space for title and final badge
    
    # Draw routes
    for route_idx, route in enumerate(routes_data):
        route_x = route_x_start + route_idx * (route_width + 20)
        route_color = route['color']
        
        # Draw route box with border
        border_width = 4
        draw.rectangle(
            [(route_x, route_y_start), (route_x + route_width, route_y_start + route_height)],
            outline=route_color,
            width=border_width,
            fill=(255, 255, 255, 200)  # Semi-transparent white
        )
        
        # Route name
        route_name = route['name']
        route_name_bbox = draw.textbbox((0, 0), route_name, font=route_font)
        route_name_width = route_name_bbox[2] - route_name_bbox[0]
        route_name_x = route_x + (route_width - route_name_width) // 2
        draw.text((route_name_x, route_y_start + 20), route_name, fill=route_color, font=route_font)
        
        # Draw steps
        steps = route['steps']
        step_height = (route_height - 80) // len(steps)  # Leave space for route name
        step_y = route_y_start + 60
        
        for step_idx, step in enumerate(steps):
            step_box_y = step_y + step_idx * step_height
            
            # Step number circle
            circle_radius = 20
            circle_x = route_x + 30
            circle_y = step_box_y + 30
            draw.ellipse(
                [(circle_x - circle_radius, circle_y - circle_radius),
                 (circle_x + circle_radius, circle_y + circle_radius)],
                fill=route_color,
                outline=(255, 255, 255),
                width=2
            )
            
            # Step number text
            step_num = str(step.get('number', step_idx + 1))
            num_bbox = draw.textbbox((0, 0), step_num, font=step_font)
            num_width = num_bbox[2] - num_bbox[0]
            num_height = num_bbox[3] - num_bbox[1]
            draw.text(
                (circle_x - num_width // 2, circle_y - num_height // 2),
                step_num,
                fill=(255, 255, 255),
                font=step_font
            )
            
            # Step title
            title_x = circle_x + circle_radius + 15
            title_y = step_box_y + 15
            step_title = step['title']
            draw.text((title_x, title_y), step_title, fill=(0, 0, 0), font=step_font)
            
            # Step description (if provided)
            if 'description' in step and step['description']:
                desc_y = title_y + 25
                # Wrap text if too long
                desc_text = step['description']
                max_width = route_width - (title_x - route_x) - 20
                words = desc_text.split()
                lines = []
                current_line = ""
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    test_bbox = draw.textbbox((0, 0), test_line, font=desc_font)
                    if test_bbox[2] - test_bbox[0] <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                
                for line_idx, line in enumerate(lines[:2]):  # Max 2 lines
                    draw.text((title_x, desc_y + line_idx * 18), line, fill=(100, 100, 100), font=desc_font)
            
            # Duration (if provided)
            if 'duration' in step and step['duration']:
                duration_y = step_box_y + step_height - 25
                duration_text = f"({step['duration']})"
                draw.text((title_x, duration_y), duration_text, fill=(150, 150, 150), font=desc_font)
            
            # Arrow to next step (except last step)
            if step_idx < len(steps) - 1:
                arrow_start_y = step_box_y + step_height - 10
                arrow_end_y = step_box_y + step_height + 10
                arrow_x = circle_x
                # Draw arrow line
                draw.line(
                    [(arrow_x, arrow_start_y), (arrow_x, arrow_end_y)],
                    fill=(34, 139, 34),  # Green
                    width=3
                )
                # Draw arrowhead
                arrow_size = 8
                draw.polygon(
                    [(arrow_x, arrow_end_y),
                     (arrow_x - arrow_size, arrow_end_y - arrow_size),
                     (arrow_x + arrow_size, arrow_end_y - arrow_size)],
                    fill=(34, 139, 34)
                )
    
    # Final outcome badge at bottom
    badge_radius = 80
    badge_x = width // 2
    badge_y = height - 120
    
    # Draw badge circle
    draw.ellipse(
        [(badge_x - badge_radius, badge_y - badge_radius),
         (badge_x + badge_radius, badge_y + badge_radius)],
        fill=(220, 20, 60),  # Red
        outline=(255, 255, 255),
        width=4
    )
    
    # Badge text
    badge_text = f"{career_name}\nProfessional"
    badge_lines = badge_text.split('\n')
    line_height = 25
    start_y = badge_y - (len(badge_lines) * line_height) // 2
    
    for line_idx, line in enumerate(badge_lines):
        line_bbox = draw.textbbox((0, 0), line, font=route_font)
        line_width = line_bbox[2] - line_bbox[0]
        line_x = badge_x - line_width // 2
        draw.text(
            (line_x, start_y + line_idx * line_height),
            line,
            fill=(255, 255, 255),
            font=route_font
        )
    
    # Draw connecting lines from routes to badge
    for route_idx in range(num_routes):
        route_x = route_x_start + route_idx * (route_width + 20) + route_width // 2
        route_bottom = route_y_start + route_height
        
        # Draw line from route bottom to badge
        draw.line(
            [(route_x, route_bottom), (badge_x, badge_y - badge_radius)],
            fill=(150, 150, 150),
            width=2
        )
    
    # Save image
    img.save(output_path, 'PNG', quality=95)
    print(f"Infographic saved to: {output_path}")


# Example usage
if __name__ == "__main__":
    # Example data structure
    example_routes = [
        {
            'name': 'Route 1: Commerce Focus',
            'color': (0, 100, 200),  # Blue
            'steps': [
                {'number': 1, 'title': '10+2 in Commerce Stream', 'description': 'Accountancy & Math Preferred', 'duration': '2 Years'},
                {'number': 2, 'title': "Bachelor's Degree", 'description': 'Commerce/Accounting/Finance', 'duration': '3-4 Years'},
                {'number': 3, 'title': 'Professional Certification', 'description': 'Complete required exams', 'duration': '2-3 Years'},
                {'number': 4, 'title': 'Practical Work Experience', 'description': 'Industry training', 'duration': '3 Years'},
                {'number': 5, 'title': 'Professional Practice', 'description': 'Work as certified professional', 'duration': 'Ongoing'},
            ]
        },
        {
            'name': 'Route 2: Any Stream',
            'color': (34, 139, 34),  # Green
            'steps': [
                {'number': 1, 'title': '10+2 in Any Stream', 'description': 'Min 65% in Math/Accountancy', 'duration': '2 Years'},
                {'number': 2, 'title': 'Foundation Course', 'description': 'Entry level qualification', 'duration': '1 Year'},
                {'number': 3, 'title': 'Professional Qualification', 'description': 'Complete required exams', 'duration': '2-3 Years'},
                {'number': 4, 'title': 'Work Experience', 'description': 'Practical training', 'duration': '3 Years'},
                {'number': 5, 'title': 'Professional Member', 'description': 'Practice as certified member', 'duration': 'Ongoing'},
            ]
        },
        {
            'name': 'Route 3: Higher Education',
            'color': (138, 43, 226),  # Purple
            'steps': [
                {'number': 1, 'title': '10+2 with Mathematics', 'description': 'Commerce or Science stream', 'duration': '2 Years'},
                {'number': 2, 'title': "Bachelor's Degree", 'description': 'Commerce/Related field', 'duration': '3-4 Years'},
                {'number': 3, 'title': "Master's Degree", 'description': 'Accounting/Finance/MBA', 'duration': '1-2 Years'},
                {'number': 4, 'title': 'Professional Program', 'description': 'With exemptions based on prior qualification', 'duration': '1-2 Years'},
                {'number': 5, 'title': 'Professional Practice', 'description': 'Work as consultant or professional', 'duration': 'Ongoing'},
            ]
        },
        {
            'name': 'Route 4: Flexible Entry',
            'color': (255, 140, 0),  # Orange
            'steps': [
                {'number': 1, 'title': '10+2 in Any Stream', 'description': 'Meeting entry requirements', 'duration': '2 Years'},
                {'number': 2, 'title': 'Short-term Certificate', 'description': 'Accounting/Finance', 'duration': '3-8 Months'},
                {'number': 3, 'title': 'Professional Program', 'description': 'Start with foundation if needed', 'duration': '2-3 Years'},
                {'number': 4, 'title': 'Work Experience', 'description': 'Practical training', 'duration': '3 Years'},
                {'number': 5, 'title': 'Professional Member', 'description': 'Practice domestically or internationally', 'duration': 'Ongoing'},
            ]
        }
    ]
    
    output_dir = Path(__file__).parent.parent / 'static' / 'study_routes'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'example_study_route.png'
    
    create_study_route_infographic(
        career_name="Example Career",
        routes_data=example_routes,
        output_path=str(output_path)
    )

