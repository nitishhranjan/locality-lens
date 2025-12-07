# locality-lens
AI-powered locality analysis using open source data and LLM

# Locality Lens 🏘️

A data-driven, AI-powered locality review engine.

## Modular Structure
This project follows a production-ready modular architecture:

```
locality-lens/
├── src/                  # Source code
│   ├── data/            # Data acquisition (OSM, APIs)
│   ├── analysis/        # Statistical processing
│   └── utils/           # Shared utilities (logging, helpers)
├── config/              # Configuration (environment, settings)
├── tests/               # Unit and integration tests
├── notebook/            # Jupyter notebooks for experimentation
├── app.py               # Streamlit entry point
└── requirements.txt     # Dependencies
```

## Setup
1. Create virtual env: `uv venv` or `python -m venv .venv`
2. Activate: `source .venv/bin/activate`
3. Install: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`
