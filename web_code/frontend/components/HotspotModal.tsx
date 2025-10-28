"use client";
import React, { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, Tooltip, Legend, BarChart, Bar, Cell } from "recharts";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL as string;

type Cell = {
  lat:number; lng:number; duration_min:number;
  series_min:number[];
  subs_min:{NH3:number;VOC:number;CO:number};
};
type Detail = {
  labels: string[];
  avg_by_sub: { NH3:number[]; VOC:number[]; CO:number[] };
  exceed_counts: { NH3:number; VOC:number; CO:number };
  avg_tta_min?: number;
  tta_samples?: number;
};

export default function HotspotModal({
  open, onClose, cell, range, grid=50,
}: { open:boolean; onClose:()=>void; cell:Cell|null; range:"24h"|"7d"|"30d"; grid?:number }) {
  const [data, setData] = useState<Detail|null>(null);

  useEffect(() => {
    let alive = true;
    if (!open || !cell) { setData(null); return; }
    (async () => {
      try {
        const q = new URLSearchParams({ lat: String(cell.lat), lng: String(cell.lng), range, grid: String(grid), split: "0" });
        const r = await fetch(`${BE}/stats/hotspot_detail?${q.toString()}`, { cache: "no-store" });
        const j = r.ok ? await r.json() : null;
        if (alive) setData(j);
      } catch { if (alive) setData(null); }
    })();
    return () => { alive = false; };
  }, [open, cell?.lat, cell?.lng, range, grid]);

  if (!open || !cell) return null;

  const colors = { NH3: "#7c3aed", VOC: "#f97316", CO: "#0ea5e9" };
  const rows = (data?.labels ?? []).map((t, i) => ({
    t,
    NH3: data?.avg_by_sub?.NH3?.[i] ?? 0,
    VOC: data?.avg_by_sub?.VOC?.[i] ?? 0,
    CO:  data?.avg_by_sub?.CO?.[i]  ?? 0,
  }));
  const bars = [
    { k: "NH3", v: data?.exceed_counts?.NH3 ?? 0 },
    { k: "VOC", v: data?.exceed_counts?.VOC ?? 0 },
    { k: "CO",  v: data?.exceed_counts?.CO  ?? 0 },
  ];

  return (
    <div className="fixed inset-0 z-[2100]">
      <div className="absolute inset-0 bg-black/50" onClick={onClose}/>
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[960px] max-w-[95vw] bg-white rounded-xl shadow-2xl p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="font-semibold text-gray-900">
            핫스팟 · {cell.lat.toFixed(5)}, {cell.lng.toFixed(5)} · 지속 {cell.duration_min.toFixed(1)}분
          </div>
          <button onClick={onClose} className="px-3 py-1 rounded-lg bg-gray-900 text-white text-sm">닫기</button>
        </div>

        <div className="text-xs text-gray-600">
  승인까지 평균: {data?.avg_tta_min ?? 0}분 {data?.tta_samples ? `(${data?.tta_samples}건)` : ""}
</div>


        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 왼쪽: 농도 추이 */}
          <div className="h-64 border rounded-lg p-2">
            <div className="text-sm text-gray-600 mb-1">물질별 농도 추이(평균)</div>
            <ResponsiveContainer>
              <LineChart data={rows}>
                <XAxis dataKey="t" hide />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="NH3" stroke={colors.NH3} dot={false} />
                <Line type="monotone" dataKey="VOC" stroke={colors.VOC} dot={false} />
                <Line type="monotone" dataKey="CO"  stroke={colors.CO}  dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 오른쪽: 물질별 발생(임계 초과) 횟수 */}
          <div className="h-64 border rounded-lg p-2">
  <div className="text-sm text-gray-600 mb-1">물질별 발생 횟수(주의 이상)</div>
  <ResponsiveContainer>
    <BarChart data={bars}>
      <XAxis dataKey="k" />
      <Tooltip />
      <Bar dataKey="v" name="횟수">
        {bars.map((b, i) => (
          <Cell key={i} fill={colors[b.k as "NH3"|"VOC"|"CO"]} />
        ))}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
</div>

        </div>

        <div className="flex gap-2 text-sm">
          {(["NH3","VOC","CO"] as const).map(k=>(
            <span key={k} className="px-2 py-1 rounded bg-gray-100 text-gray-800">
              {k} {cell.subs_min[k].toFixed(1)}m
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
