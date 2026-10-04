# Book2Skill master context

This repository focuses on building a production-oriented knowledge compiler that turns books and documents into validated, reusable AI-ready skill packages.

## Product identity

Book2Skill converts source knowledge into structured artifacts for downstream systems such as:

- skill packs
- RAG indexing
- training preparation
- context packages
- knowledge graphs

The compiler is the primary product. AI providers are secondary infrastructure.

## Core pipeline

Document -> parse -> normalize -> extract -> validate -> compile -> output package

## Current implementation goal

The minimum viable production path is:

1. repository foundation
2. document ingestion
3. extraction of title, concepts, principles, and methods
4. validation of extracted knowledge
5. SKILL.md generation
6. CLI execution
7. automated test coverage

## Non-negotiables

- no fake product features
- no fake progress states
- no fake AI provider integrations
- no hardcoded download claims
- document provenance must be preserved
- outputs must be schema-validated
- source data must remain traceable

## Phase status

The current working phase is FOUNDATION + CORE COMPILER MVP.
