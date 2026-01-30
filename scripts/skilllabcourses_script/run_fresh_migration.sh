#!/bin/bash
# Script to run fresh migration for skilllab app after manual table deletion

set -e  # Exit on error

echo "=========================================="
echo "Skill Lab Fresh Migration Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get project directory
PROJECT_DIR="/home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/topteen_1.0"
cd "$PROJECT_DIR" || {
    echo -e "${RED}✗ Project directory not found: $PROJECT_DIR${NC}"
    exit 1
}

echo -e "${YELLOW}Step 1: Checking migration file...${NC}"
MIGRATION_FILE="skilllab/migrations/0001_initial_fresh.py"
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}✗ Migration file not found: $MIGRATION_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Migration file found${NC}"

echo ""
echo -e "${YELLOW}Step 2: Checking if tables exist...${NC}"
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SHOW TABLES LIKE 'skilllab_%'\")
tables = cursor.fetchall()
if tables:
    print('⚠️  Found existing skilllab tables:')
    for table in tables:
        print(f'  - {table[0]}')
    print('')
    print('If you want to proceed, make sure you have manually dropped all skilllab tables.')
    print('Expected SQL:')
    print('DROP TABLE IF EXISTS skilllab_skilllabcourse, skilllab_skilllabcourseactivity,')
    print('  skilllab_skilllabcoursechapter, skilllab_skilllabcourseenrollment,')
    print('  skilllab_skilllabmcq, skilllab_skilllabmcqanswer,')
    print('  skilllab_skilllabmcqquestion, skilllab_skilllabmcqresult,')
    print('  skilllab_skilllabcourseprogress, skilllab_skilllabcoursesection,')
    print('  skilllab_skilllabcoursepayment;')
else:
    print('✓ No existing skilllab tables found (good for fresh migration)')
" 2>&1

echo ""
echo -e "${YELLOW}Step 3: Running migration...${NC}"
if python manage.py migrate skilllab; then
    echo ""
    echo -e "${GREEN}✓ Migration completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}✗ Migration failed!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Make sure all skilllab tables are dropped"
    echo "2. Check for any foreign key constraints"
    echo "3. Verify database connection"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 4: Verifying tables created...${NC}"
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SHOW TABLES LIKE 'skilllab_%'\")
tables = cursor.fetchall()
print(f'✓ Created {len(tables)} tables:')
for table in sorted(tables):
    print(f'  - {table[0]}')
" 2>&1

echo ""
echo "=========================================="
echo -e "${GREEN}Fresh Migration Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Upload courses from JSON:"
echo "   python scripts/skilllabcourses_script/upload_from_json.py --all"
echo ""
echo "2. Or test with a single course:"
echo "   python scripts/skilllabcourses_script/upload_from_json.py --json-file <course_name>.json"
echo ""
