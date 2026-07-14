import os

base_dir = "test_projects/github_benchmarks/java"
for root, dirs, files in os.walk(base_dir):
    if root == base_dir:
        continue
    print(f"Directory: {root}")
    for f in sorted(files):
        print(f"  {f}")
