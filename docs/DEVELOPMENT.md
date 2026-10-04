# Development guide

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run tests

```bash
pytest -q
```

## Run the compiler

```bash
python -m book2skill --input samples\sample-book.md --output output
```
