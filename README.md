# Gene's ESL RAG Pipeline

This repository contains the source code, metadata, and templates for a Retrieval-Augmented Generation (RAG) system used to generate weekly ESL lessons.

## Structure

- `sourcecode/` — Python scripts for ingestion, lesson generation, and utilities
- `source_docs/` — PDFs, templates, and lesson outputs
- `metadata/` — page_map.json and other ingestion metadata
- `chroma/` — ChromaDB persistent store (ignored by Git)
- `Modelfile` — Ollama model configuration

## Notes

- Virtual environments are intentionally excluded.
- ChromaDB is excluded via `.gitignore`.

