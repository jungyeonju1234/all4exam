"""Find HTML template issues that would cause Vue compilation to fail."""
import re

with open('app/templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the #app div content (between line 97 and 977 roughly)
app_start = content.find('<div id="app"')
app_end_marker = '    </div>\n\n    <!-- Vue App Script -->'
app_end = content.find(app_end_marker)
if app_end == -1:
    app_end_marker = '</div>\n\n    <!-- Vue App Script -->'
    app_end = content.find(app_end_marker)

template_html = content[app_start:app_end + 6]  # include closing </div>
print(f"Template HTML length: {len(template_html)}")

# Check 1: Look for unescaped < in text content (not tags)
# Check 2: Look for problematic Vue directives
# Check 3: Count open/close tags

# Simple tag balance check
tag_pattern = re.compile(r'<(/?)(\w+)[\s>]')
tag_stack = []
void_tags = {'br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr'}

lines = template_html.split('\n')
for line_num, line in enumerate(lines, 1):
    # Skip comment lines
    if '<!--' in line and '-->' in line:
        continue
    
    # Find all tags in this line
    for m in tag_pattern.finditer(line):
        is_close = m.group(1) == '/'
        tag_name = m.group(2).lower()
        
        if tag_name in void_tags:
            continue
        # Skip self-closing (check if /> before next <)
        tag_end_pos = m.end()
        remaining = line[tag_end_pos:]
        
        if not is_close:
            # Check if self-closing
            close_bracket = line.find('>', m.start())
            if close_bracket > 0 and line[close_bracket-1] == '/':
                continue
            tag_stack.append((tag_name, line_num))
        else:
            if tag_stack and tag_stack[-1][0] == tag_name:
                tag_stack.pop()
            else:
                if tag_stack:
                    print(f"  Tag mismatch at line {line_num}: closing </{tag_name}> but expected </{tag_stack[-1][0]}> (opened at line {tag_stack[-1][1]})")
                else:
                    print(f"  Extra closing tag </{tag_name}> at line {line_num}")

if tag_stack:
    print(f"\nUnclosed tags remaining: {[(t,l) for t,l in tag_stack]}")
else:
    print("\nAll tags balanced!")

# Check 3: Look for <보기> which could break HTML parsing
bogie_count = 0
for i, line in enumerate(lines, 1):
    # Look for bare < not followed by valid tag or /
    stripped = line.strip()
    # Look for <보기> pattern which is common in Korean exam templates
    if '<보기>' in stripped:
        bogie_count += 1
        print(f"  WARNING: Raw '<보기>' at template line {i}: {stripped[:80]}")
    # Look for any < followed by non-tag chars (excluding Vue directives, HTML tags)
    for m2 in re.finditer(r'<([^/!\w\s])', stripped):
        if m2.group(1) not in ('!', '?'):
            print(f"  Suspicious '<' at template line {i}: ...{stripped[max(0,m2.start()-20):m2.end()+20]}...")

print(f"\n<보기> occurrences: {bogie_count}")
