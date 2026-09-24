import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { MapJob } from "@/lib/api";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

function featureCollection(jobs: MapJob[], selectedJobId?: string | null) {
  return {
    type: "FeatureCollection",
    features: jobs
      .filter(
        (job) =>
          typeof job.longitude === "number" && typeof job.latitude === "number",
      )
      .map((job) => ({
        type: "Feature",
        id: job.job_id,
        geometry: {
          type: "Point",
          coordinates: [job.longitude!, job.latitude!],
        },
        properties: {
          job_id: job.job_id,
          title: job.title,
          company: job.company,
          location: job.location,
          selected: job.job_id === selectedJobId,
        },
      })),
  };
}

export function JobMap({
  jobs,
  selected,
  onSelect,
}: {
  jobs: MapJob[];
  selected: MapJob | null;
  onSelect: (job: MapJob) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const jobsRef = useRef(jobs);
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);
  const [mapError, setMapError] = useState("");

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);
  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!container.current || map.current) return;
    const instance = new maplibregl.Map({
      container: container.current,
      style: MAP_STYLE,
      center: [76.5, 23.2],
      zoom: 4.2,
      minZoom: 3,
      maxZoom: 16,
      attributionControl: false,
    });
    map.current = instance;
    instance.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    instance.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right",
    );

    instance.on("error", (event) => {
      if (event.error?.message) setMapError("The base map could not be loaded.");
    });
    instance.on("load", () => {
      instance.addSource("jobs", {
        type: "geojson",
        data: featureCollection(jobsRef.current),
        cluster: true,
        clusterMaxZoom: 13,
        clusterRadius: 46,
      });
      instance.addLayer({
        id: "job-clusters",
        type: "circle",
        source: "jobs",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": [
            "step",
            ["get", "point_count"],
            "hsl(226 92% 56%)",
            25,
            "hsl(226 82% 48%)",
            75,
            "hsl(226 70% 40%)",
          ],
          "circle-radius": ["step", ["get", "point_count"], 20, 25, 26, 75, 32],
          "circle-stroke-color": "white",
          "circle-stroke-width": 2,
        },
      });
      instance.addLayer({
        id: "job-cluster-count",
        type: "symbol",
        source: "jobs",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 12,
        },
        paint: { "text-color": "white" },
      });
      instance.addLayer({
        id: "job-points",
        type: "circle",
        source: "jobs",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "case",
            ["boolean", ["get", "selected"], false],
            "hsl(155 62% 30%)",
            "hsl(226 92% 56%)",
          ],
          "circle-radius": [
            "case",
            ["boolean", ["get", "selected"], false],
            9,
            7,
          ],
          "circle-stroke-color": "white",
          "circle-stroke-width": 2,
        },
      });
      instance.on("click", "job-clusters", async (event) => {
        const feature = instance.queryRenderedFeatures(event.point, {
          layers: ["job-clusters"],
        })[0];
        const clusterId = feature?.properties?.cluster_id;
        const source = instance.getSource("jobs") as maplibregl.GeoJSONSource;
        if (typeof clusterId !== "number") return;
        const zoom = await source.getClusterExpansionZoom(clusterId);
        if (feature.geometry.type === "Point") {
          instance.easeTo({ center: feature.geometry.coordinates as [number, number], zoom });
        }
      });
      instance.on("click", "job-points", (event) => {
        const feature = event.features?.[0];
        const jobId = feature?.properties?.job_id;
        const job = jobsRef.current.find((item) => item.job_id === jobId);
        if (job) onSelectRef.current(job);
      });
      for (const layer of ["job-clusters", "job-points"]) {
        instance.on("mouseenter", layer, () => {
          instance.getCanvas().style.cursor = "pointer";
        });
        instance.on("mouseleave", layer, () => {
          instance.getCanvas().style.cursor = "";
        });
      }
    });

    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      instance.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance?.isStyleLoaded()) return;
    const source = instance.getSource("jobs") as
      | maplibregl.GeoJSONSource
      | undefined;
    source?.setData(
      featureCollection(jobs, selectedRef.current?.job_id),
    );
  }, [jobs]);

  useEffect(() => {
    const instance = map.current;
    const source = instance?.getSource("jobs") as
      | maplibregl.GeoJSONSource
      | undefined;
    if (!instance || !source) return;
    source.setData(featureCollection(jobsRef.current, selected?.job_id));
    if (selected && typeof selected.longitude === "number" && typeof selected.latitude === "number") {
      instance.easeTo({
        center: [selected.longitude, selected.latitude],
        zoom: Math.max(instance.getZoom(), 10),
        duration: 650,
      });
    }
  }, [selected]);

  return (
    <div className="job-map-shell">
      <div ref={container} className="job-map-canvas" aria-label="Interactive job map" />
      {mapError && <p className="job-map-error">{mapError}</p>}
    </div>
  );
}
