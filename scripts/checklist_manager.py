"""
Shared checklist manager for creating and managing verification checklist.
Used by both create_test_students.py and remove_test_students.py
"""

import os
import csv
from datetime import datetime


class ChecklistManager:
    """Manage verification checklist CSV file"""
    
    def __init__(self, checklist_file=None):
        if checklist_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            checklist_file = os.path.join(script_dir, 'verification_checklist.csv')
        self.checklist_file = checklist_file
        self.checklist_items = []
        self.base_url = "http://localhost:8000"
    
    def load_checklist(self):
        """Load existing checklist from CSV"""
        self.checklist_items = []
        if not os.path.exists(self.checklist_file):
            return
        
        try:
            with open(self.checklist_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.checklist_items = list(reader)
            
            # Migrate old fields and add new ones if needed
            for item in self.checklist_items:
                # Migrate old 'Status' field to 'Verification Status' if needed
                if 'Status' in item and 'Verification Status' not in item:
                    item['Verification Status'] = item.pop('Status', 'Pending')
                elif 'Verification Status' not in item:
                    item['Verification Status'] = 'Pending'
                
                # Add 'Test Verification' field if missing
                if 'Test Verification' not in item:
                    item['Test Verification'] = ''
        except Exception as e:
            print(f'Warning: Could not load checklist: {e}')
            self.checklist_items = []
    
    def get_student_ids_from_checklist(self):
        """Extract unique student IDs from checklist"""
        student_ids = set()
        for item in self.checklist_items:
            student_id = item.get('Student ID', '')
            if student_id:
                try:
                    student_ids.add(int(student_id))
                except ValueError:
                    pass
        return list(student_ids)
    
    def get_student_names_from_checklist(self):
        """Extract unique student names from checklist"""
        student_names = set()
        for item in self.checklist_items:
            student_name = item.get('Student Name', '')
            if student_name:
                student_names.add(student_name)
        return list(student_names)
    
    def add_checklist_item(self, student_id, student_name, test_case, test_category, 
                          specific_check, expected_result, verification_steps, report_url):
        """Add a checklist item"""
        self.checklist_items.append({
            'Student ID': str(student_id),
            'Student Name': student_name,
            'Test Case Description': test_case,
            'Test Category': test_category,
            'Specific Check': specific_check,
            'Expected Result': expected_result,
            'Manual Verification Steps': verification_steps,
            'Verification Status': 'Pending',  # Passed/Failed/Pending
            'Test Verification': '',  # 'fail' or '' (empty for pass)
            'Failure Reason': '',
            'Report URL': report_url
        })
    
    def write_checklist(self):
        """Write checklist to CSV file"""
        fieldnames = [
            'Student ID', 'Student Name', 'Test Case Description', 'Test Category', 'Specific Check',
            'Expected Result', 'Manual Verification Steps', 'Verification Status', 'Test Verification', 'Failure Reason', 'Report URL'
        ]
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.checklist_file), exist_ok=True)
        
        # Ensure all items have required fields (migrate old fields and add new ones)
        for item in self.checklist_items:
            # Migrate old 'Status' to 'Verification Status'
            if 'Status' in item and 'Verification Status' not in item:
                item['Verification Status'] = item.pop('Status', 'Pending')
            elif 'Verification Status' not in item:
                item['Verification Status'] = 'Pending'
            
            # Add 'Test Verification' field if missing
            if 'Test Verification' not in item:
                item['Test Verification'] = ''
        
        with open(self.checklist_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.checklist_items)
    
    def append_to_checklist(self, new_items):
        """Append new items to existing checklist"""
        self.load_checklist()
        # Get existing student IDs to avoid duplicates
        existing_ids = {item.get('Student ID', '') for item in self.checklist_items}
        
        for item in new_items:
            if item.get('Student ID', '') not in existing_ids:
                self.checklist_items.append(item)
        
        self.write_checklist()

