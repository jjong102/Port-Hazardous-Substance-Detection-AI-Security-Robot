// frontend/components/RobotMap.tsx
"use client";
import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
if (typeof window !== "undefined") {
  // @ts-ignore
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: "/leaflet/marker-icon-2x.png",
    iconUrl: "/leaflet/marker-icon.png",
    shadowUrl: "/leaflet/marker-shadow.png",
  });
}
import "leaflet/dist/leaflet.css";
import useSSE from "../hooks/useSSE";

type GPS = { lat: number; lng: number; timestamp?: string; vehicle_id?: string };

const BE = process.env.NEXT_PUBLIC_BACKEND_URL as string;

export default function RobotMap() {
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const [gps, setGps] = useState<GPS | null>(null);

  // SSE live updates
  useSSE(`${BE}/stream`, {
    gps: (data) => setGps({ lat: data.lat, lng: data.lng, timestamp: data.timestamp, vehicle_id: data.vehicle_id }),
  });

  // Fallback polling every 5s
  useEffect(() => {
    let t: any;
    const pull = async () => {
      try {
        const r = await fetch(`${BE}/gps/latest`, { cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          setGps({ lat: j.lat, lng: j.lng, timestamp: j.timestamp, vehicle_id: j.vehicle_id });
        }
      } catch {}
      t = setTimeout(pull, 5000);
    };
    pull();
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!mapRef.current) {
      const map = L.map("robot-map", { preferCanvas: true }).setView([37.45, 126.7], 14);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(map);
      mapRef.current = map;
    }
  }, []);

  useEffect(() => {
    if (mapRef.current && gps?.lat && gps?.lng) {
      const latlng = L.latLng(gps.lat, gps.lng);
      if (!markerRef.current) {
        markerRef.current = L.marker(latlng, { title: gps.vehicle_id || "robot" }).addTo(mapRef.current);
      } else {
        markerRef.current.setLatLng(latlng);
      }
      mapRef.current.setView(latlng, mapRef.current.getZoom(), { animate: true });
    }
  }, [gps?.lat, gps?.lng]);

  return (
    <div className="w-full h-[420px] rounded-2xl overflow-hidden border">
      <div id="robot-map" className="w-full h-full" />
    </div>
  );
}
