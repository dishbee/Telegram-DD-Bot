import re

# Read the file
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the line after imports and before webhook endpoints
lines = content.split('\n')
start_remove = None
end_remove = None

for i, line in enumerate(lines):
    if 'from upc import *' in line:
        start_remove = i + 1
    elif '--- WEBHOOK ENDPOINTS ---' in line:
        end_remove = i
        break

if start_remove is not None and end_remove is not None:
    # Remove the duplicate functions
    new_content = '\n'.join(lines[:start_remove] + lines[end_remove:])
    
    # Write back
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f'Removed lines {start_remove} to {end_remove-1}')
else:
    print('Could not find the boundaries')