#!/usr/bin/env python3
"""
Crawler ZIP Download and Extraction Memory Profiler.
Profiles memory usage during archive streaming, buffer buffering, and zipfile parsing.
"""

import os
import sys
import zipfile
import io
import tracemalloc
import time

def profile_zip_extraction(zip_path: str):
    print(f"--- Profiling extraction memory for: {zip_path} ---")
    if not os.path.exists(zip_path):
        print("Target file not found. Creating a mock zip file for profiling...")
        mock_data = io.BytesIO()
        with zipfile.ZipFile(mock_data, 'w') as zf:
            for i in range(100):
                zf.writestr(f"module_{i}.java", "class Test {\n" + "    public void run() {}\n" * 100 + "}\n")
        zip_data = mock_data.getvalue()
    else:
        with open(zip_path, 'rb') as f:
            zip_data = f.read()

    tracemalloc.start()
    
    # Snapshot 1: Initial state
    snapshot1 = tracemalloc.take_snapshot()
    
    # Process 1: Load byte stream
    stream = io.BytesIO(zip_data)
    snapshot2 = tracemalloc.take_snapshot()
    
    # Process 2: Read zip structure
    with zipfile.ZipFile(stream) as zf:
        file_list = zf.namelist()
        file_contents = {}
        for name in file_list[:20]: # read first 20 files
            if name.endswith('.java'):
                with zf.open(name) as f:
                    file_contents[name] = f.read().decode('utf-8', errors='ignore')
                    
    # Snapshot 3: Peak structure loaded
    snapshot3 = tracemalloc.take_snapshot()
    
    tracemalloc.stop()
    
    # Calculate differences
    stats1_2 = snapshot2.compare_to(snapshot1, 'lineno')
    stats2_3 = snapshot3.compare_to(snapshot2, 'lineno')
    
    print("\n[Memory usage during byte stream loading]:")
    for stat in stats1_2[:3]:
        print(stat)
        
    print("\n[Memory usage during zip structure parsing and decoding]:")
    for stat in stats2_3[:3]:
        print(stat)
        
    print(f"\nTotal ZIP raw data size: {len(zip_data) / 1024:.2f} KB")
    print("Profiling finished successfully.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    profile_zip_extraction(target)
