import pytesseract
from PIL import Image
from pathlib import Path

input_dir = Path("/Users/gene/Documents/Graphics ESL")
output_dir = Path("/Users/gene/Documents/RAG/source_docs/Graphics")
output_dir.mkdir(parents=True, exist_ok=True)

def extract_text(img_path):
    img = Image.open(img_path)
    # Spanish + English OCR
    return pytesseract.image_to_string(img, lang="spa+eng")

def main():
    for img in input_dir.glob("*.png"):
        print(f"Processing: {img.name}")
        text = extract_text(img)

        out_file = output_dir / f"{img.stem}.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"Saved: {out_file}")

if __name__ == "__main__":
    main()

