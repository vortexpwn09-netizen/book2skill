# Architecture decisions

## Decision 1: keep the compiler independent from SaaS UI

The core compiler is implemented as a reusable Python package. The CLI and future APIs will consume the same internal model.

## Decision 2: prioritize real functionality over broad feature breadth

The current effort focuses on the vertical slice:

source document -> parsed content -> structured knowledge -> validated package -> SKILL.md output.

## Decision 3: validate before export

Extracted material is checked for emptiness and consistency before being written to output files.
