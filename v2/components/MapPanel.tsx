"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { CATEGORY_COLORS, DEFAULT_COLOR, type LocationInfo, type Poi } from "./types";

// OpenFreeMap serves vector tiles with no API key, no signup and no request
// cap, so the deploy stays keyless. CARTO's dark raster tiles look similar
// but now watermark anonymous requests with "API KEY REQUIRED".
const STYLE_URL = "https://tiles.openfreemap.org/styles/dark";

export default function MapPanel({ location, pois }: { location: LocationInfo | null; pois: Poi[] }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const pending = useRef<{ data: GeoJSON.FeatureCollection; location: LocationInfo | null } | null>(null);
  // Last payload actually written, so repeated sync calls are no-ops.
  const applied = useRef<GeoJSON.FeatureCollection | null>(null);

  // `null` means no filter - show everything. A Set means show only those.
  const [shown, setShown] = useState<Set<string> | null>(null);

  // Every category present, ranked by frequency. Doubles as the legend and
  // the filter control, so there is one thing to learn instead of two.
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of pois) counts.set(p.c, (counts.get(p.c) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [pois]);

  const isOn = useCallback((c: string) => !shown || shown.has(c), [shown]);

  const toggle = useCallback(
    (category: string) => {
      setShown((prev) => {
        // First click on an unfiltered map isolates that category - the
        // common intent is "just show me restaurants", not "hide restaurants".
        if (!prev) return new Set([category]);

        const next = new Set(prev);
        if (next.has(category)) next.delete(category);
        else next.add(category);

        // Empty or complete selections both mean "no filter".
        if (next.size === 0 || next.size === categories.length) return null;
        return next;
      });
    },
    [categories.length]
  );

  const visibleCount = useMemo(
    () => (shown ? pois.filter((p) => shown.has(p.c)).length : pois.length),
    [pois, shown]
  );

  // A new result set should not inherit the previous one's filter.
  useEffect(() => setShown(null), [pois]);

  const geojson = useMemo<GeoJSON.FeatureCollection>(
    () => ({
      type: "FeatureCollection",
      features: pois.map((p) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: { color: CATEGORY_COLORS[p.c] ?? DEFAULT_COLOR, category: p.c, name: p.n ?? "" },
      })),
    }),
    [pois]
  );

  /**
   * Add our source and layers, then write any parked data.
   *
   * Driven by `styledata` rather than the one-shot `load` event: under React
   * StrictMode the first map is constructed and torn down before it ever
   * finishes loading, so a handler bound to `load` can be dropped entirely
   * and the layers never get added at all. `styledata` fires on every style
   * update, and this whole body is idempotent, so repeat calls are harmless.
   */
  const sync = useCallback(() => {
    const m = map.current;
    if (!m) return;

    // Gate only the *creation* of layers on the style being ready. Do not
    // gate the data write on it: this style keeps `isStyleLoaded()` false
    // indefinitely because of an unresolved sprite image, so guarding
    // setData behind it silently drops every update forever.
    if (!m.getSource("pois")) {
      if (!m.isStyleLoaded()) return; // a later `styledata` will retry
      m.addSource("pois", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "poi-glow",
        type: "circle",
        source: "pois",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 4, 16, 11],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.14,
          "circle-blur": 1,
        },
      });
      m.addLayer({
        id: "poi-dot",
        type: "circle",
        source: "pois",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 1.8, 16, 4.5],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.95,
          "circle-stroke-width": 0.4,
          "circle-stroke-color": "rgba(0,0,0,0.55)",
        },
      });
    }

    const source = m.getSource("pois") as maplibregl.GeoJSONSource | undefined;
    const next = pending.current;
    if (!source || !next) return;

    // Skip if this exact payload is already on the map. Without this guard,
    // running sync on `idle` would loop: setData -> render -> idle -> setData.
    if (next.data !== applied.current) {
      source.setData(next.data);
      applied.current = next.data;
    }
    if (next.location) {
      m.easeTo({ center: [next.location.lon, next.location.lat], zoom: 13.4, duration: 900 });
      next.location = null; // recentre once per result, not on every restyle
    }
  }, []);

  useEffect(() => {
    if (!container.current || map.current) return;

    const instance = new maplibregl.Map({
      container: container.current,
      style: STYLE_URL,
      center: [77.64, 12.97],
      zoom: 11.5,
      attributionControl: false,
    });
    map.current = instance;

    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    // The style ships its own OSM/OpenMapTiles credits; adding ours as well
    // would just print the same attribution twice.
    instance.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    // Three chances to land the data, because there is no single event that
    // reliably fires *after* the style is ready on every load path. In dev,
    // StrictMode's double-mount masked this by giving `styledata` a second
    // run; production mounts once, so a missed `styledata` meant the layers
    // were never added and the map stayed empty. `sync` is idempotent, so
    // over-subscribing is free.
    instance.on("styledata", sync);
    instance.on("load", sync);
    instance.on("idle", sync);

    const popup = new maplibregl.Popup({ closeButton: false, offset: 10 });
    instance.on("mouseenter", "poi-dot", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      instance.getCanvas().style.cursor = "pointer";
      const { name, category } = f.properties as { name: string; category: string };
      const label = category.replace(/_/g, " ");
      // Build with the DOM rather than setHTML: OSM names are third-party
      // data and must never be interpolated into markup.
      const el = document.createElement("div");
      if (name) {
        const strong = document.createElement("span");
        strong.className = "poi-name";
        strong.textContent = name;
        el.appendChild(strong);
      }
      const cat = document.createElement("span");
      cat.className = name ? "poi-cat" : "poi-name";
      cat.textContent = label;
      el.appendChild(cat);

      popup
        .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
        .setDOMContent(el)
        .addTo(instance);
    });
    instance.on("mouseleave", "poi-dot", () => {
      instance.getCanvas().style.cursor = "";
      popup.remove();
    });

    return () => {
      instance.remove();
      map.current = null;
    };
  }, [sync]);

  // Park the latest payload, then sync. Data routinely arrives before the
  // style finishes loading, in which case `sync` is a no-op here and the
  // `styledata` handler picks it up instead.
  useEffect(() => {
    pending.current = { data: geojson, location };
    sync();
  }, [geojson, location, sync]);

  // Filter on the GPU via setFilter rather than rebuilding the GeoJSON -
  // toggling a category stays instant even with thousands of points.
  useEffect(() => {
    const m = map.current;
    if (!m || !m.getLayer("poi-dot")) return;

    const filter = shown
      ? (["in", ["get", "category"], ["literal", [...shown]]] as maplibregl.FilterSpecification)
      : null;
    m.setFilter("poi-dot", filter);
    m.setFilter("poi-glow", filter);
  }, [shown, geojson]);

  return (
    <section className="panel">
      <div className="panel-head">
        <div className="panel-title">
          <span className={`dot ${pois.length ? "live" : ""}`} />
          Map
        </div>
        <span className="mono-sm">
          {pois.length
            ? shown
              ? `${visibleCount.toLocaleString()} of ${pois.length.toLocaleString()} places`
              : `${pois.length.toLocaleString()} places`
            : "—"}
        </span>
      </div>

      {categories.length > 0 && (
        <div className="map-filter" role="group" aria-label="Filter places by type">
          {shown && (
            <button className="filter-chip reset" onClick={() => setShown(null)}>
              Show all
            </button>
          )}
          {categories.map(([category, count]) => (
            <button
              key={category}
              className="filter-chip"
              aria-pressed={isOn(category)}
              onClick={() => toggle(category)}
              title={shown ? "Toggle this type" : "Show only this type"}
            >
              <span className="legend-swatch" style={{ background: CATEGORY_COLORS[category] ?? DEFAULT_COLOR }} />
              {category.replace(/_/g, " ")}
              <span className="filter-count">{count}</span>
            </button>
          ))}
        </div>
      )}

      <div className="map-wrap">
        <div ref={container} style={{ position: "absolute", inset: 0 }} />
        {pois.length === 0 && <div className="map-empty">Run an analysis to plot amenities</div>}
      </div>
    </section>
  );
}
