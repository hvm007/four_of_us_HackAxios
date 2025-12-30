#!/usr/bin/env python3
"""
Migration script to add risk_category column to existing risk_assessments table.
This is a one-time migration for the hackathon to update existing databases.
"""

import logging
import sqlite3
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.utils.database import get_database_url, create_database_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_sqlite_database(db_path: str):
    """Migrate SQLite database to add risk_category column."""
    if not os.path.exists(db_path):
        logger.info(f"Database {db_path} does not exist, skipping migration")
        return
    
    logger.info(f"Migrating database: {db_path}")
    
    try:
        # Connect directly to SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if risk_category column already exists
        cursor.execute("PRAGMA table_info(risk_assessments)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'risk_category' in columns:
            logger.info("risk_category column already exists, skipping migration")
            conn.close()
            return
        
        # Add the risk_category column
        logger.info("Adding risk_category column...")
        cursor.execute("""
            ALTER TABLE risk_assessments 
            ADD COLUMN risk_category TEXT NOT NULL DEFAULT 'LOW'
        """)
        
        # Update existing records based on risk_score
        logger.info("Updating existing records with risk categories...")
        cursor.execute("""
            UPDATE risk_assessments 
            SET risk_category = CASE 
                WHEN risk_score >= 65 THEN 'HIGH'
                WHEN risk_score >= 45 THEN 'MODERATE'
                ELSE 'LOW'
            END
        """)
        
        # Also update based on risk_flag for safety
        cursor.execute("""
            UPDATE risk_assessments 
            SET risk_category = 'HIGH'
            WHERE risk_flag = 1
        """)
        
        conn.commit()
        
        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM risk_assessments")
        total_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT risk_category, COUNT(*) FROM risk_assessments GROUP BY risk_category")
        category_counts = cursor.fetchall()
        
        logger.info(f"Migration completed successfully!")
        logger.info(f"Total records: {total_records}")
        for category, count in category_counts:
            logger.info(f"  {category}: {count} records")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise


def main():
    """Run the migration on all database files."""
    logger.info("Starting risk_category column migration...")
    
    # List of database files to migrate
    db_files = [
        "patient_risk_dev.db",
        "patient_risk_test.db",
        "test_vitals.db"
    ]
    
    backend_dir = Path(__file__).parent
    
    for db_file in db_files:
        db_path = backend_dir / db_file
        if db_path.exists():
            migrate_sqlite_database(str(db_path))
        else:
            logger.info(f"Database {db_file} not found, skipping")
    
    logger.info("Migration completed!")


if __name__ == "__main__":
    main()