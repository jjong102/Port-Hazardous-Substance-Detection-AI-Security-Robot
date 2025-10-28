// frontend/components/ActiveIncidentCard.tsx
"use client";
import React from "react";
import type { Incident } from "../hooks/useIncident";

const CAUTION = 2.0;
const DANGER = 4.0;

type Level = "danger" | "warn" | "normal";
const sev = (v: number): Level => (v >= DANGER ? "danger" : v >= CAUTION ? "warn" : "normal");
const sevBadge = (l: Level) =>
  l === "danger" ? "bg-red-100 text-red-800"
  : l === "warn" ? "bg-amber-100 text-amber-800"
  : "bg-gray-100 text-gray-700";
const sevLabel = (l: Level) => (l === "danger" ? "위험" : l === "warn" ? "주의" : "정상");

// 칩을 값 기준으로 색상 지정
const chipClassByValue = (v: number) =>
  v >= DANGER
    ? "border-red-500 text-red-700"
    : v >= CAUTION
    ? "border-amber-500 text-amber-700"
    : "border-sky-500 text-sky-700";

type Props = {
  incident: Incident | null;
  onApprove: (id: number) => void;
};

export default function ActiveIncidentCard({ incident, onApprove }: Props) {
  if (!incident)
    return <div className="p-4 rounded-xl border text-sm text-gray-500">활성 인시던트 없음</div>;

  const subs = incident.substances || [];
  const maxAny = subs.length ? Math.max(...subs.map((s) => s.max)) : 0;
  const level: Level = sev(maxAny);

  return (
    <div className="p-4 rounded-xl border flex items-center justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <div className="font-semibold">이상 이벤트 · {incident.status}</div>
          <span className={`text-xs px-2 py-0.5 rounded ${sevBadge(level)}`}>
            {sevLabel(level)}{maxAny ? ` · ${maxAny.toFixed(2)}` : ""}
          </span>
        </div>

        <div className="flex flex-wrap gap-2 mb-1">
          {subs.map((x) => (
            <span
              key={x.substance}
              className={`px-2 py-1 rounded-md text-xs font-semibold border ${chipClassByValue(x.max)}`}
              title={`${x.substance} max`}
            >
              {x.substance} {x.max.toFixed(2)}
            </span>
          ))}
        </div>

        <div className="text-xs text-gray-500">
          {incident.lat.toFixed(5)}, {incident.lng.toFixed(5)}
        </div>
      </div>

      <div className="flex gap-2 shrink-0">
        {incident.status === "pending" && (
          <button
            onClick={() => onApprove(incident.id)}
            className="px-3 py-1 rounded-lg bg-blue-600 text-white text-sm"
          >
            승인
          </button>
        )}
      </div>
    </div>
  );
}
