#!/usr/bin/env python3
"""
Master script to process and upload all Skill Lab Courses.
This script runs all processing steps in order:
1. Process DOCX files (extract MCQs, mark headings, generate HTML/PDF)
2. Upload processed content to database
"""

import os
import sys
import subprocess
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROCESS_SCRIPT = SCRIPT_DIR / "process_skilllab_courses.py"
UPLOAD_SCRIPT = SCRIPT_DIR / "upload_skilllab_courses.py"


def run_script(script_path: Path, args: list = None):
    """
    Run a Python script and return success status.
    """
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"Running: {script_path.name}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(cmd, check=False, capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running script: {e}")
        return False


def main():
    """
    Main function to run all processing steps.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Process and upload Skill Lab Courses')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without making them (upload step only)')
    parser.add_argument('--skip-process', action='store_true',
                       help='Skip DOCX processing step (use existing processed files)')
    parser.add_argument('--skip-upload', action='store_true',
                       help='Skip database upload step')
    parser.add_argument('--course', type=str,
                       help='Process only specific course (by name)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Skill Lab Courses - Complete Processing Pipeline")
    print("=" * 60)
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"Dry run: {args.dry_run}")
    print(f"Skip process: {args.skip_process}")
    print(f"Skip upload: {args.skip_upload}")
    print()
    
    success = True
    
    # Step 1: Process DOCX files
    if not args.skip_process:
        print("\n" + "=" * 60)
        print("STEP 1: Processing DOCX Files")
        print("=" * 60)
        process_args = []
        if args.course:
            # Note: process script doesn't support course filter yet
            print(f"Note: Course filter not supported in process step. Processing all courses.")
        
        if not run_script(PROCESS_SCRIPT, process_args):
            print("\nError: DOCX processing failed!")
            success = False
        else:
            print("\n✓ DOCX processing completed successfully")
    else:
        print("\nSkipping DOCX processing step (using existing files)")
    
    # Step 2: Upload to database
    if not args.skip_upload and success:
        print("\n" + "=" * 60)
        print("STEP 2: Uploading to Database")
        print("=" * 60)
        upload_args = []
        if args.dry_run:
            upload_args.append('--dry-run')
        if args.course:
            upload_args.extend(['--course', args.course])
        
        if not run_script(UPLOAD_SCRIPT, upload_args):
            print("\nError: Database upload failed!")
            success = False
        else:
            print("\n✓ Database upload completed successfully")
    else:
        if args.skip_upload:
            print("\nSkipping database upload step")
        elif not success:
            print("\nSkipping database upload due to previous errors")
    
    # Summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    if success:
        print("✓ All steps completed successfully!")
    else:
        print("✗ Some steps failed. Please check the errors above.")
    print()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
