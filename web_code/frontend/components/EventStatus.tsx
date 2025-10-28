// frontend/components/EventStatus.tsx
"use client";
import React from "react";
import type { IncidentState } from "../hooks/useIncident";

export default function EventStatus({ state }: { state: IncidentState }) {
  const dot = state.sse === "open" ? "bg-green-500" : "bg-yellow-500";
  return (
    <div className="flex items-center gap-3 text-xs text-gray-600">
      <span className={`inline-block w-2 h-2 rounded-full ${dot}`} />
      <span>SSE: {state.sse}</span>
      <span>| BE: {state.backend}</span>
      <span>| 업데이트: {state.lastUpdate ? new Date(state.lastUpdate).toLocaleString() : "—"}</span>
    </div>
  );
}
