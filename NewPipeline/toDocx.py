#!/usr/bin/env python3
"""
toDocx.py

Step 4 of the weekly workflow: convert the CORRECTED lesson Markdown files
to .docx. The generating pipelines (pipeline.py / supportPipeline.py) write
only Markdown; run this after both lessons have been cleaned.

Usage:
    python3 toDocx.py <identifier> [main_file.md] [five_file.md]

Example:
    python3 toDocx.py 39

With only the identifier it converts, from the lessons output directory:
    39_MAIN_corrected.md   -> 39_MAIN_corrected.docx
    39_FIVEMIN_corrected.md -> 39_FIVEMIN_corrected.docx

Same Pandoc settings as commonFunctions.convert_markdown_to_docx(): input
format "markdown+hard_line_breaks", --standalone, and the shared
reference.docx for heading styles when it exists. An existing .docx with
the same name is overwritten (it is derived from the .md).
"""

import os
import subprocess
import sys

sys.path.insert(0, "/Users/gene/Documents/RAG/sourcecode")
import commonFunctions as common  # noqa: E402


def convert(md_path, docx_path):
    if not os.path.exists(md_path):
        print(f"ERROR: not found: {md_path}")
        return False

    markdown_text = common.read_file(md_path)
    extra_args = ["--standalone"]
    if os.path.exists(common.reference_doc_path):
        extra_args.append(f"--reference-doc={common.reference_doc_path}")
    else:
        print(f"NOTE: no reference-doc found at {common.reference_doc_path} - using Pandoc's default docx styling")

    try:
        import pypandoc
        pypandoc.convert_text(
            markdown_text,
            to="docx",
            format="markdown+hard_line_breaks",
            outputfile=docx_path,
            extra_args=extra_args,
        )
    except ImportError:
        subprocess.run(
            ["pandoc", "-f", "markdown+hard_line_breaks", "-t", "docx", "-o", docx_path] + extra_args,
            input=markdown_text.encode("utf-8"),
            check=True,
        )
    print(f"Saved: {docx_path}")
    return True


def main():
    if len(sys.argv) not in (2, 3, 4):
        print("Usage: python3 toDocx.py <identifier> [main_file.md] [five_file.md]")
        sys.exit(1)

    identifier = sys.argv[1]
    main_file = sys.argv[2] if len(sys.argv) >= 3 else f"{identifier}_MAIN_corrected.md"
    five_file = sys.argv[3] if len(sys.argv) == 4 else f"{identifier}_FIVEMIN_corrected.md"

    ok = True
    for name in (main_file, five_file):
        md_path = os.path.join(common.lesson_dir, name)
        docx_path = os.path.splitext(md_path)[0] + ".docx"
        ok = convert(md_path, docx_path) and ok

    if not ok:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
