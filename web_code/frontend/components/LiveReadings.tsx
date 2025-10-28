// frontend/components/LiveReadings.tsx
"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";

const BE =
  (process.env.NEXT_PUBLIC_BACKEND_URL as string) || "http://localhost:5000";

type Reading = {
  id: number;
  type: "NH3" | "VOC" | "CO" | "GPS";
  value: number | null;
  lat?: number | null;
  lng?: number | null;
  vehicle_id?: string;
  timestamp: string; // ISO (UTC, ends with Z)
};
type Trio = { NH3?: Reading; VOC?: Reading; CO?: Reading };

export default function LiveReadings() {
  const [vals, setVals] = useState<Trio>({});
  const [err, setErr] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  // 초기 값: readings/latest로 타입별 최신 1건 채우기
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${BE}/readings/latest`, { cache: "no-store" });
        if (!r.ok) return; // 없어도 됨
        const j = await r.json();
        // 응답은 {NH3, VOC, CO} or 단일 오브젝트일 수 있음
        const next: Trio = {};
        if (j.NH3) next.NH3 = j.NH3 as Reading;
        if (j.VOC) next.VOC = j.VOC as Reading;
        if (j.CO) next.CO = j.CO as Reading;
        if (alive) setVals((prev) => ({ ...next, ...prev }));
      } catch {}
    })();
    return () => {
      alive = false;
    };
  }, []);

  // SSE 구독: /stream 의 "reading" 이벤트만 구독
  useEffect(() => {
    const es = new EventSource(`${BE}/stream`);
    esRef.current = es;

    const onReading = (ev: MessageEvent) => {
      try {
        const msg: Reading = JSON.parse(ev.data);
        if (msg?.type === "NH3" || msg?.type === "VOC" || msg?.type === "CO") {
          setVals((prev) => ({ ...prev, [msg.type]: msg }));
        }
      } catch (e: any) {
        // 무시
      }
    };
    const onError = () => setErr("실시간 연결 끊김 (자동 재시도 중)...");
    const onOpen = () => setErr(null);

    es.addEventListener("reading", onReading as EventListener);
    es.addEventListener("open", onOpen as EventListener);
    es.addEventListener("error", onError as EventListener);

    return () => {
      es.removeEventListener("reading", onReading as EventListener);
      es.removeEventListener("open", onOpen as EventListener);
      es.removeEventListener("error", onError as EventListener);
      es.close();
      esRef.current = null;
    };
  }, []);

  const nh3 = vals.NH3?.value ?? undefined;
  const voc = vals.VOC?.value ?? undefined;
  const co = vals.CO?.value ?? undefined;

  return (
    <div className="space-y-2">
      {err && (
        <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
          {err}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <GasTile label="NH3" reading={vals.NH3} value={nh3} />
        <GasTile label="VOC" reading={vals.VOC} value={voc} />
        <GasTile label="CO"  reading={vals.CO}  value={co} />
      </div>
    </div>
  );
}

function GasTile({
  label,
  value,
  reading,
}: {
  label: "NH3" | "VOC" | "CO";
  value?: number;
  reading?: Reading;
}) {
  const thr = 2.0;
  const risky = (value ?? 0) >= thr;
  const ts = useMemo(() => {
    if (!reading?.timestamp) return "";
    const d = new Date(reading.timestamp);
    return isNaN(d.getTime()) ? "" : d.toLocaleString();
  }, [reading?.timestamp]);

  return (
    <div
      className={`p-4 rounded-xl border ${
        risky ? "border-red-400" : "border-gray-200"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">{label}</div>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            risky ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-700"
          }`}
        >
          {risky ? "주의 이상" : "정상"}
        </span>
      </div>

      <div className="mt-1 text-2xl font-bold">{fmt(value)}</div>

      <div className="mt-1 text-[11px] text-gray-500">
        {ts ? `업데이트: ${ts}` : "대기 중…"}
      </div>
    </div>
  );
}

function fmt(v?: number) {
  return typeof v === "number" ? v.toFixed(2) : "—";
}