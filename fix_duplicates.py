"""
Fix duplicate route definitions in app.py
"""

import re

# Read the file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all route definitions with their positions
route_pattern = r'@app\.route\([^)]+\)[^\n]*\n(?:@[^\n]+\n)*def\s+(\w+)\s*\([^)]*\):'
matches = list(re.finditer(route_pattern, content))

# Track seen function names and their first occurrence
seen = {}
duplicates_to_remove = []

for match in matches:
    func_name = match.group(1)
    if func_name in seen:
        # This is a duplicate
        duplicates_to_remove.append((func_name, match.start()))
        print(f"Found duplicate: {func_name} at position {match.start()}")
    else:
        seen[func_name] = match.start()
        print(f"First occurrence: {func_name} at position {match.start()}")

print(f"\nTotal duplicates found: {len(duplicates_to_remove)}")
print("Duplicates:", [name for name, pos in duplicates_to_remove])
