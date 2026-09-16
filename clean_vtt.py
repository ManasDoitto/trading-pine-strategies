import sys
import re

def clean_vtt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
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
            
    print(" ".join(clean_lines))

if __name__ == "__main__":
    clean_vtt(sys.argv[1])
