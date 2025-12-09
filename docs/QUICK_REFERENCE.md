# Locality Lens - Quick Reference

## 🎯 Project Purpose
AI-powered tool that analyzes any location and generates personalized summaries based on user profile (bachelor, family, student, etc.)

## 🔄 System Flow
```
User Input (Lat/Long + Profile) 
  → Geocoding 
  → OSM Data Fetching 
  → Statistics Calculation 
  → User Profile Processing 
  → LLM Summary Generation 
  → Output (Summary + Map)
```

## 📊 Key Metrics
- **Schools**: Count within 2km
- **Hospitals**: Count within 2km  
- **Parks**: Area (km²) within 2km
- **Restaurants**: Count within 1km
- **Metro**: Distance to nearest station
- **Bus Stops**: Count within 500m
- **Road Density**: km/km²
- **POI Density**: POIs/km²

## 🛠️ Tech Stack
- **Data**: OpenStreetMap (OSM) via OSMnx
- **Spatial**: GeoPandas, Shapely
- **LLM**: Groq (Llama 3.1) via LangChain
- **Frontend**: Streamlit
- **Viz**: Folium

## 👤 User Profiles
1. Bachelor/Young Professional
2. Nuclear Family (with kids)
3. Joint Family
4. Student
5. Senior Citizen
6. Working Professional
7. Custom (free text)

## 📁 Key Files
- `src/data/osm_fetcher.py` - OSM data fetching
- `src/analysis/stats_calculator.py` - Statistics computation
- `src/user_profiling/profile_processor.py` - Profile handling
- `src/llm/summary_generator.py` - LLM integration
- `app.py` - Streamlit entry point
- `config/config.py` - Configuration

## 🚀 Current Status
- ✅ Project structure created
- ✅ GitHub repository set up
- 🚧 Implementation pending (Day 1-7)

## 📍 Target Cities
Major Indian metros: Delhi, Mumbai, Bangalore, Hyderabad, Chennai, Pune, Kolkata

## 🔑 OSM Tags
```python
schools = {'amenity': 'school'}
hospitals = {'amenity': ['hospital', 'clinic']}
parks = {'leisure': ['park', 'garden']}
restaurants = {'amenity': ['restaurant', 'cafe', 'fast_food']}
metro = {'railway': 'station', 'station': 'subway'}
bus_stops = {'highway': 'bus_stop'}
```

## ⚙️ Configuration
- `GROQ_API_KEY` - Required for LLM
- `SEARCH_RADIUS` - Default 1000m
- Cache directory: `data/cache/`

---
*See PROJECT_CONTEXT.md for full details*

