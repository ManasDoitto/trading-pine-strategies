import textwrap

for i in [1, 2]:
    with open(f"clean{i}_utf8.txt", "r", encoding="utf-8-sig") as f:
        text = f.read()
    wrapped = "\n".join(textwrap.wrap(text, 80))
    with open(f"clean{i}_wrapped.txt", "w", encoding="utf-8") as f:
        f.write(wrapped)
