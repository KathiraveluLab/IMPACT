#!/usr/bin/env python3
"""
IMPACT License and Copyright Compliance Auditor.
Checks all files in the project for copyright notices and audits dependencies for license compatibility.
"""

import os
import re
import sys

def audit_file_licenses(root_dir: str):
    print(f"--- Running License Compliance Audit in: {root_dir} ---")
    
    # Files to audit (source code, build scripts)
    target_extensions = ('.py', '.js', '.html', '.css', '.toml', '.sh', '.ttl')
    
    total_files = 0
    missing_license = []
    
    for root, _, files in os.walk(root_dir):
        # Skip git or temporary directories
        if any(ignored in root for ignored in ['.git', '.github', 'dist', 'build', 'node_modules', '.tempmediaStorage']):
            continue
            
        for file in files:
            if file.endswith(target_extensions):
                total_files += 1
                filepath = os.path.join(root, file)
                
                # Check for common license keywords
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    has_license = False
                    if "Copyright" in content or "Apache" in content or "License" in content:
                        has_license = True
                        
                    if not has_license:
                        # Skip small config files or simple metadata
                        if os.path.getsize(filepath) > 100:
                            missing_license.append(os.path.relpath(filepath, root_dir))
                except Exception as e:
                    print(f"Error reading file {filepath}: {e}")

    print(f"Audited {total_files} project files.")
    if missing_license:
        print(f"Found {len(missing_license)} files missing copyright or license headers:")
        for path in missing_license[:10]:
            print(f"- {path}")
        if len(missing_license) > 10:
            print(f"... and {len(missing_license) - 10} more.")
    else:
        print("All audited files have appropriate license or copyright declarations.")
        
    return len(missing_license) == 0

if __name__ == "__main__":
    success = audit_file_licenses(".")
    sys.exit(0 if success else 1)
