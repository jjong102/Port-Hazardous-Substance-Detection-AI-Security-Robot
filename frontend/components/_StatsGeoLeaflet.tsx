"use client";
import React, { useEffect, useRef } from "react";

type HotCell = {
  lat:number; lng:number; duration_min:number;
  series_min:number[]; subs_min: {NH3:number; VOC:number; CO:number};
};

let LCache: any = null;
async function getLeaflet() {
  if (LCache) return LCache;
  const mod = await import("leaflet");
  LCache = (mod as any).default ?? mod;
  return LCache;
}

export default function StatsGeoLeaflet({ cells }: { cells: HotCell[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);

  useEffect(() => {
    (async () => {
      const L = await getLeaflet();
      if (!ref.current || mapRef.current) return;

      const map = L.map(ref.current).setView([37.45, 126.7], 11);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);
    })();
  }, []);

  useEffect(() => {
    (async () => {
      const L = await getLeaflet();
      if (!mapRef.current || !layerRef.current) return;

      const layer = layerRef.current;
      layer.clearLayers();

      if (cells.length) {
        const bounds = (L as any).latLngBounds(cells.map(c => [c.lat, c.lng]));
        mapRef.current.fitBounds(bounds.pad(0.2));
      }

      const maxMin = Math.max(1, ...cells.map(c => c.duration_min));
      const scale = (m: number) => 30 + 70 * Math.sqrt(m / maxMin);

      const colorFor = (s: "NH3"|"VOC"|"CO") =>
        s==="NH3" ? "#7c3aed" : s==="VOC" ? "#f97316" : "#0ea5e9";

      cells.forEach(c => {
        const subs = ["NH3","VOC","CO"].filter(k => (c.subs_min as any)[k] > 0) as ("NH3"|"VOC"|"CO")[];
        const dom = subs.sort((a,b)=> (c.subs_min as any)[b] - (c.subs_min as any)[a])[0] || "NH3";
        const color = colorFor(dom);
        const textSubs = subs.length ? subs.join(", ") : dom;

        (L as any).circleMarker([c.lat, c.lng], {
          radius: scale(c.duration_min) / 10,
          color, weight: 2, fillColor: color, fillOpacity: 0.35,
        }).bindTooltip(
          `지속: ${c.duration_min.toFixed(1)}분\n물질: ${textSubs}`,
          { direction: "top" }
        ).addTo(layer);
      });
    })();
  }, [cells]);

  return <div ref={ref} style={{width:"100%", height:"100%"}} />;
}
