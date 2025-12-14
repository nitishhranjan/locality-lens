# Locality Lens 🏘️

AI-powered locality analysis using LangGraph, OpenStreetMap, and LLM integration.

## 🌟 Overview

Locality Lens is an intelligent location analysis tool that provides data-driven insights about any neighborhood. It combines geospatial data from OpenStreetMap with AI-powered analysis to generate personalized summaries, helping users understand what an area is actually like to live in.

## ✨ Features

- **📍 Real-time Location Analysis**: Get instant insights about any location worldwide
- **🤖 AI-Generated Summaries**: Personalized locality summaries using Groq LLM (Llama 3.1)
- **🗺️ Comprehensive POI Data**: Schools, hospitals, restaurants, parks, transportation, and more
- **📊 Key Statistics**: Essential amenities, connectivity metrics, and density analysis
- **🗺️ Interactive Maps**: Visualize location with interactive Folium maps
- **⚡ Smart Workflow**: Built with LangGraph for stateful, intelligent processing
- **📈 Real-time Progress**: Live updates during analysis with detailed progress tracking
- **🎯 User Profiles**: Personalized insights based on user profile (Bachelor, Family, Student, etc.)

## 🏗️ Architecture

Built with a modular, production-ready architecture using LangGraph:

```
User Input (Location + Profile)
    ↓
┌─────────────────────────────────────┐
│  LangGraph Workflow                 │
│  ┌───────────────────────────────┐  │
│  │ 1. Validate Input             │  │
│  │ 2. Geocode Location           │  │
│  │ 3. Fetch OSM Data             │  │
│  │ 4. Calculate Statistics       │  │
│  │ 5. Generate AI Summary        │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
    ↓
Results (Summary + Statistics + Map)
```

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Workflow** | LangGraph | Stateful workflow orchestration |
| **LLM** | LangChain + Groq (Llama 3.1) | AI-powered summary generation |
| **Data Source** | OpenStreetMap (OSM) | Free, comprehensive geospatial data |
| **Data Fetching** | OSMnx | Python library for OSM data |
| **Spatial Analysis** | GeoPandas, Shapely | Geospatial operations and calculations |
| **Geocoding** | Geopy (Nominatim) | Address to coordinates conversion |
| **Frontend** | Streamlit | Interactive web interface |
| **Visualization** | Folium | Interactive map visualization |
| **Language** | Python 3.9+ | Core development language |

## 📊 Key Metrics Analyzed

The system calculates and analyzes:

- **Essential Amenities**
  - Schools (count within 2km)
  - Hospitals & Clinics (count within 2km)
  - Parks & Gardens (area in km²)

- **Food & Dining**
  - Restaurants, Cafes, Fast Food (count within 1km)

- **Transportation**
  - Metro Stations (count + nearest distance)
  - Bus Stops (count within 500m)

- **Connectivity & Density**
  - POI Density (POIs per km²)
  - Road Network Analysis

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Groq API key (for LLM features)
- Internet connection (for OSM data fetching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd locality-lens
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   # On macOS/Linux:
   source .venv/bin/activate
   # On Windows:
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Create .env file in project root
   echo "GROQ_API_KEY=your_groq_api_key_here" > .env
   ```
   
   Get your Groq API key from: https://console.groq.com/

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

   The app will open in your browser at `http://localhost:8501`

## 📖 Usage

### Basic Usage

1. **Enter Location**: Type an address (e.g., "Indiranagar, Bangalore") or coordinates (e.g., "12.9784, 77.6408")
2. **Select Profile** (Optional): Choose your profile type for personalized insights
3. **Click "Analyze Location"**: The system will:
   - Geocode your location
   - Fetch POI data from OpenStreetMap
   - Calculate statistics
   - Generate an AI-powered summary
4. **View Results**: See summary, statistics, and interactive map

### Example Locations

- `Indiranagar, Bangalore`
- `Connaught Place, Delhi`
- `Mumbai, Maharashtra`
- `12.9784, 77.6408` (coordinates)

## 📁 Project Structure

```
locality-lens/
├── src/
│   ├── graph/              # LangGraph workflow
│   │   ├── state.py        # State schema definition
│   │   ├── nodes.py        # Graph nodes (validate, geocode, fetch, etc.)
│   │   └── graph.py        # Graph construction and routing
│   ├── data/               # Data acquisition
│   │   ├── geocoder.py     # Geocoding utilities
│   │   └── osm_fetcher.py  # OSM data fetching
│   ├── analysis/           # Statistical processing
│   │   └── stats_calculator.py
│   ├── llm/                # LLM integration
│   │   ├── summary_generator.py
│   │   └── prompts.py
│   └── utils/              # Shared utilities
├── config/
│   └── config.py           # Configuration and API keys
├── notebook/               # Jupyter notebooks for experimentation
├── tests/                  # Test files
├── app.py                  # Streamlit application entry point
├── test_app.py             # Automated testing script
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 📈 Performance

- **Data Fetching**: Optimized single-query approach (83% faster than sequential queries)
- **Real-time Progress**: Live updates during analysis
- **Caching**: Intelligent caching for OSM data (reduces API calls)
- **Response Time**: Typically 5-10 seconds for complete analysis

## 🎯 Use Cases

- **Real Estate**: Evaluate neighborhoods before moving or investing
- **Relocation**: Understand locality characteristics before relocating
- **Urban Planning**: Analyze area amenities and infrastructure
- **Research**: Geospatial data analysis and insights
- **Personal Decision Making**: Get data-driven insights about living in an area

## 🔮 Future Enhancements

- [ ] **AQI Integration**: Air Quality Index data for environmental insights
- [ ] **LLM-Driven Metric Selection**: Intelligent metric selection based on user profile
- [ ] **Comparison Mode**: Compare multiple locations side-by-side
- [ ] **Export Results**: Download analysis as JSON or PDF
- [ ] **Historical Trends**: Track changes over time (if data available)
- [ ] **Advanced Filtering**: Filter POIs by specific criteria
- [ ] **Custom Profiles**: User-defined profile types with custom priorities

## 🧪 Testing

Run the automated test suite:

```bash
python test_app.py
```

This tests:
- Multiple locations (Bangalore, Delhi, Mumbai)
- Different input formats (addresses, coordinates)
- Various user profiles
- Edge cases (invalid inputs, empty inputs)

## 🐛 Known Limitations

- **OSM Data Quality**: Results depend on OpenStreetMap data completeness
- **Geocoding Accuracy**: Some locations may not geocode correctly
- **API Rate Limits**: OSM and Nominatim have rate limits (caching helps)
- **Network Dependency**: Requires internet connection for data fetching