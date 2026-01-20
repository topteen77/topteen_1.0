#!/bin/bash
# Script to create migrations for forum app only, handling the GA4Session prompt automatically

echo "Creating migrations for forum app..."
echo "When prompted for GA4Session 'created' field default, we'll use timezone.now"

# Use expect or just provide the answer directly
python manage.py makemigrations forum <<EOF
1
timezone.now

EOF

echo ""
echo "Migrations created! Now run: python manage.py migrate forum"
