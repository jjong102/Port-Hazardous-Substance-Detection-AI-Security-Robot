// frontend/components/ActiveIncidentGrid.tsx
"use client";
import React from "react";
import type { Incident } from "../hooks/useIncident";

export default function ActiveIncidentGrid({
  incident,
  onApprove,
}: {
  incident: Incident | null;
  onApprove: (id: number) => void;
}) {
  if (!incident || !incident.substances?.length) {
    return <div className="p-4 rounded-xl border text-sm text-gray-500">활성 인시던트 없음</div>;
  }
  const thr = 2.0;
  const subs = incident.substances
    .filter((s) => (s.max ?? 0) >= thr)
    .sort((a, b) => (b.max ?? 0) - (a.max ?? 0))
    .slice(0, 3);

  return (
    <div className="space-y-3">
      
{incident.status === "resolved" && (
  <div className="flex justify-end">
    <button
      onClick={() => onApprove(incident.id)}
      className="px-3 py-1 rounded-lg bg-blue-600 text-white text-sm"
    >
      승인
    </button>
  </div>
)}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {subs.map((s) => (
          <Card key={s.substance} s={s} lat={incident.lat} lng={incident.lng} />
        ))}
      </div>
    </div>
  );
}

function Card({
  s,
  lat,
  lng,
}: {
  s: { substance: "NH3" | "VOC" | "CO"; max: number };
  lat: number;
  lng: number;
}) {
  const color =
    s.substance === "NH3"
      ? "border-purple-400"
      : s.substance === "VOC"
      ? "border-orange-400"
      : "border-sky-400";
  return (
    <div className={`p-4 rounded-xl border ${color}`}>
      <div className="text-xs text-gray-400">{s.substance}</div>
      <div className="text-2xl font-bold">{s.max.toFixed(2)}</div>
      <div className="mt-1 inline-block rounded bg-red-100 text-red-700 text-xs px-2 py-0.5">주의 이상</div>
      <div className="mt-2 text-xs text-gray-500">
        {lat.toFixed(5)}, {lng.toFixed(5)}
      </div>
    </div>
  );
}
