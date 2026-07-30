import re
import json
from pathlib import Path

raw_dir = Path("/Users/gene/Documents/RAG/source_docs/Graphics")
clean_dir = Path("/Users/gene/Documents/RAG/cleaned/Graphics")
clean_dir.mkdir(parents=True, exist_ok=True)

# Regex patterns to detect Spanish and English
spanish_pattern = re.compile(r"\b(el|la|los|las)\s?[a-záéíóúñ]+", re.IGNORECASE)
english_pattern = re.compile(r"\b(the|a)\s[a-z]+", re.IGNORECASE)

def clean_line(line):
    # Normalize parentheses/braces
    line = line.replace("{", "(").replace("}", ")")
    line = line.replace("[", "(").replace("]", ")")

    # Fix missing spaces in Spanish
    line = re.sub(r"(el|la|los|las)([A-Za-záéíóúñ])", r"\1 \2", line, flags=re.IGNORECASE)

    # Remove stray symbols
    line = re.sub(r"[~@°©»«]", "", line)

    return line.strip()

def extract_pairs(text):
    pairs = []
    lines = text.split("\n")

    for line in lines:
        line = clean_line(line)

        # Find Spanish and English in the same line
        spanish = spanish_pattern.findall(line)
        english = english_pattern.findall(line)

        if spanish and english:
            # Use first match from each
            pairs.append((spanish[0], english[0]))

    return pairs

def process_file(path):
    raw_text = path.read_text(encoding="utf-8")

    pairs = extract_pairs(raw_text)

    # Clean text output
    clean_text = "\n".join([f"{s} — {e}" for s, e in pairs])

    # JSON output
    json_output = [
        {
            "spanish": s,
            "english": e,
            "source_file": path.name,
            "category": "graphics"
        }
        for s, e in pairs
    ]

    # ChromaDB-ready documents
    chroma_docs = [
        {
            "id": f"{path.stem}_{s.replace(' ', '_')}",
            "text": f"{s} ({e})",
            "metadata": {
                "source": path.name,
                "category": "graphics"
            }
        }
        for s, e in pairs
    ]

    # Write outputs
    (clean_dir / f"{path.stem}_clean.txt").write_text(clean_text, encoding="utf-8")
    (clean_dir / f"{path.stem}.json").write_text(json.dumps(json_output, indent=2), encoding="utf-8")
    (clean_dir / f"{path.stem}_chroma.json").write_text(json.dumps(chroma_docs, indent=2), encoding="utf-8")

    print(f"Processed {path.name}: {len(pairs)} pairs extracted.")

def main():
    for txt_file in raw_dir.glob("*.txt"):
        process_file(txt_file)

if __name__ == "__main__":
    main()

