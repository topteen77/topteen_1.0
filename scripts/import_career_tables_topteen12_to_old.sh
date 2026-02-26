#!/usr/bin/env bash
# Import all career tables from topteen12 (source) to topteen12-old (target).
# Uses only columns that exist in both DBs. Run from project root.
# Usage: bash scripts/import_career_tables_topteen12_to_old.sh
# Dry run: bash scripts/import_career_tables_topteen12_to_old.sh --dry-run

set -e
cd "$(dirname "$0")/.."
python manage.py import_career_tables_topteen12_to_old "$@"
