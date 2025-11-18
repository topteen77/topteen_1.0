#!/usr/bin/env python3
"""
Environment switcher script for TopTeens project.
Usage: python switch_env.py [local|production]
"""

import os
import sys
import shutil

def switch_environment(env):
    """Switch between local and production environments"""
    
    if env not in ['local', 'production']:
        print("❌ Invalid environment. Use 'local' or 'production'")
        return False
    
    # Source and destination files
    source_file = f"env.{env}"
    dest_file = ".env"
    
    if not os.path.exists(source_file):
        print(f"❌ Environment file {source_file} not found!")
        return False
    
    try:
        # Copy environment file
        shutil.copy2(source_file, dest_file)
        print(f"✅ Switched to {env} environment")
        print(f"📁 Copied {source_file} → {dest_file}")
        
        # Show current configuration
        with open(dest_file, 'r') as f:
            content = f.read()
            if 'ENABLE_ELASTICSEARCH=True' in content:
                print("🔍 Elasticsearch: ENABLED")
            else:
                print("🔍 Elasticsearch: DISABLED")
        
        return True
        
    except Exception as e:
        print(f"❌ Error switching environment: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python switch_env.py [local|production]")
        print("\nAvailable environments:")
        print("  local      - Development environment (Elasticsearch disabled)")
        print("  production - Production environment (Elasticsearch enabled)")
        return
    
    env = sys.argv[1].lower()
    switch_environment(env)

if __name__ == "__main__":
    main()
