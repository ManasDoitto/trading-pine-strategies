import textwrap
import re

for i in range(3, 8):
    vtt_file = f"video{i}.en.vtt"
    try:
        with open(vtt_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(vtt_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    
    # Remove WEBVTT header and timestamps
    lines = content.split('\n')
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:') or '-->' in line:
            continue
        
        # Remove tags like <c> or <00:00:00.000>
        line = re.sub(r'<[^>]+>', '', line)
        if line and (not clean_lines or clean_lines[-1] != line):
            clean_lines.append(line)
            
    text = " ".join(clean_lines)
    wrapped = "\n".join(textwrap.wrap(text, 80))
    
    with open(f"clean{i}_wrapped.txt", "w", encoding="utf-8") as f:
        f.write(wrapped)
    print(f"Processed video {i}")
