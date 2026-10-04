# Architecture

## Overview

Book2Skill is built as a Python core library with a lightweight CLI entrypoint. The product is intentionally separated into:

- ingestion layer for source files
- extraction layer for structured knowledge
- validation layer for artifact quality
- compiler layer for markdown and JSON exports

## Flow

Document -> ingestion -> title + knowledge extraction -> validation -> `SKILL.md` + metadata

## Current status

This repository implements the first vertical slice for a real working compiler, not a full SaaS stack.
