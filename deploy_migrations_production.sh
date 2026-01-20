#!/bin/bash
# Production Migration Deployment Script
# Run this script on your production server to safely deploy and run migrations

set -e  # Exit on error

echo "=========================================="
echo "Production Migration Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - UPDATE THESE FOR YOUR SERVER
PROJECT_DIR="/path/to/your/project"  # UPDATE THIS
DB_NAME="your_database_name"  # UPDATE THIS
DB_USER="your_db_user"  # UPDATE THIS
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Step 1: Backup Database
echo -e "${YELLOW}Step 1: Creating database backup...${NC}"
mkdir -p $BACKUP_DIR
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql"
echo "Backup file: $BACKUP_FILE"

read -p "Enter database password: " -s DB_PASS
echo ""

mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup created successfully (Size: $BACKUP_SIZE)${NC}"
else
    echo -e "${RED}✗ Backup failed! Aborting migration.${NC}"
    exit 1
fi

# Step 2: Navigate to project directory
echo ""
echo -e "${YELLOW}Step 2: Navigating to project directory...${NC}"
cd "$PROJECT_DIR" || {
    echo -e "${RED}✗ Project directory not found: $PROJECT_DIR${NC}"
    exit 1
}
echo -e "${GREEN}✓ In project directory: $(pwd)${NC}"

# Step 3: Activate virtual environment (if exists)
echo ""
echo -e "${YELLOW}Step 3: Activating virtual environment...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
elif [ -f "env/bin/activate" ]; then
    source env/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}⚠ No virtual environment found, using system Python${NC}"
fi

# Step 4: Check current migration status
echo ""
echo -e "${YELLOW}Step 4: Checking current migration status...${NC}"
python manage.py showmigrations | grep "\[ \]" | head -10
PENDING_COUNT=$(python manage.py showmigrations | grep -c "\[ \]" || true)
echo "Pending migrations: $PENDING_COUNT"

# Step 5: Confirm before proceeding
echo ""
echo -e "${YELLOW}Step 5: Confirmation${NC}"
echo "Backup file: $BACKUP_FILE"
echo "Pending migrations: $PENDING_COUNT"
echo ""
read -p "Do you want to proceed with migrations? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Migration cancelled by user${NC}"
    exit 0
fi

# Step 6: Run migrations
echo ""
echo -e "${YELLOW}Step 6: Running migrations...${NC}"
echo "This may take a few minutes..."
echo ""

# Try with skip-checks first (in case of import errors)
if python manage.py migrate --skip-checks --verbosity 2; then
    echo ""
    echo -e "${GREEN}✓ Migrations completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}✗ Migration failed!${NC}"
    echo ""
    echo "Options:"
    echo "1. Check the error message above"
    echo "2. Restore backup: mysql -u $DB_USER -p $DB_NAME < $BACKUP_FILE"
    echo "3. Review PRODUCTION_MIGRATION_DEPLOYMENT.md for troubleshooting"
    exit 1
fi

# Step 7: Verify migrations
echo ""
echo -e "${YELLOW}Step 7: Verifying migrations...${NC}"
REMAINING=$(python manage.py showmigrations | grep -c "\[ \]" || true)
if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✓ All migrations applied successfully!${NC}"
else
    echo -e "${YELLOW}⚠ $REMAINING migrations still pending${NC}"
    echo "Run: python manage.py showmigrations to see details"
fi

# Step 8: Final status
echo ""
echo "=========================================="
echo -e "${GREEN}Migration Deployment Complete!${NC}"
echo "=========================================="
echo "Backup location: $BACKUP_FILE"
echo "Next steps:"
echo "1. Test your application"
echo "2. Check application logs"
echo "3. Monitor for any issues"
echo ""
