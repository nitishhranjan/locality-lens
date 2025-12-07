# 📍 Locality Lens

**AI-powered locality analysis using open source data and LLM**

A data-driven, AI-powered locality review engine that tells you what any area is actually like to live in.

## ✨ Features

- 🔍 **Comprehensive Analysis**: Schools, hospitals, parks, connectivity, and more
- 👤 **Personalized Insights**: Tailored summaries based on your profile (bachelor, family, student, etc.)
- 🗺️ **Interactive Maps**: Visualize POIs and amenities
- 📊 **Data-Driven**: Uses OpenStreetMap data for accurate analysis
- 🚀 **Fast & Free**: No API costs for core features

## 🏗️ Project Structure

This project follows a production-ready modular architecture:

```
locality-lens/
├── src/                  # Source code
│   ├── data/            # Data acquisition (OSM, APIs)
│   ├── analysis/        # Statistical processing
│   ├── user_profiling/  # User profile processing
│   ├── llm/            # LLM integration
│   └── utils/           # Shared utilities
├── data/                # Data cache
├── tests/               # Unit and integration tests
├── app.py               # Streamlit entry point
└── requirements.txt     # Dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Groq API key (for LLM summaries)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/nitishhranjan/locality-lens.git
cd locality-lens
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

5. Run the app:
```bash
streamlit run app.py
```

## 🛠️ Tech Stack

- **Data**: OpenStreetMap (OSM), OSMnx
- **Spatial Analysis**: GeoPandas, Shapely
- **LLM**: Groq (Llama 3.1)
- **Frontend**: Streamlit
- **Visualization**: Folium

## 📊 Metrics Analyzed

- **Essential Amenities**: Schools, hospitals, parks, restaurants, shops
- **Connectivity**: Metro access, bus stops, road density
- **Lifestyle**: POI density, walkability, noise levels
- **Personalized Scores**: Match score based on your profile

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- OpenStreetMap contributors
- OSMnx library
- Streamlit community
