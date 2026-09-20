import re
import glob

def clean_file(pattern, output_name):
    vtt_files = glob.glob(pattern)
    if not vtt_files:
        print(f"VTT file not found for pattern {pattern}.")
        return

    vtt_file = vtt_files[0]
    txt_file = f"d:/Trading code-Claude/scratch/{output_name}"

    with open(vtt_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:") or "-->" in line:
            continue
        clean_line = re.sub(r'<[^>]+>', '', line)
        if clean_line and (not clean_lines or clean_lines[-1] != clean_line):
            clean_lines.append(clean_line)

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(clean_lines))

    print(f"Cleaned transcript saved to {txt_file} with {len(clean_lines)} lines.")

clean_file("d:/Trading code-Claude/scratch/transcript_12.*.vtt", "clean_transcript_12.txt")
