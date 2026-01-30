#!/usr/bin/env bash
# Create a copy of topteen12-dev from mysql8 (0innerdb) for TopTeens
# Use when /home/itpc6/Public/0innerdb/dbdata is used by another project
#
# Prerequisites: mysql8 running on host:3306 with topteen12-dev
# Usage: ./scripts/setup-db-copy.sh

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[setup] Dumping topteen12-dev from mysql8 (127.0.0.1:3306)..."
mysqldump -h 127.0.0.1 -P 3306 -u root12 -proot12 \
  --single-transaction --routines --triggers topteen12-dev \
  2>/dev/null > topteen_dump.sql

echo "[setup] Deploy with DB_MODE=local and MYSQL_DATA_PATH=dbdata_topteens"
echo "[setup] After deploy, restore: docker exec -i topteens-mysql-1 mysql -u root12 -proot12 topteen12-dev < topteen_dump.sql"
echo "[setup] Done. Run: ./deploy.sh deploy"
