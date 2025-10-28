// frontend/components/StatsPanel.tsx
"use client";
import React, { useEffect, useState } from "react";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL as string;
type Series = { t: string; avg: number };
type RangeKey = "24h" | "7d" | "30d";

export default function StatsPanel() {
  const [range, setRange] = useState<RangeKey>("24h");
  const [series, setSeries] = useState<Record<string, Series[]>>({});
  const [exceed, setExceed] = useState<{NH3:number; VOC:number; CO:number}>({NH3:0,VOC:0,CO:0});
  const [duration, setDuration] = useState<{NH3:number; VOC:number; CO:number}>({NH3:0,VOC:0,CO:0});
  const [intensity, setIntensity] = useState<{NH3:number; VOC:number; CO:number}>({NH3:0,VOC:0,CO:0});
  const [hazard, setHazard] = useState<{NH3:number; VOC:number; CO:number; range?:string}>({NH3:0,VOC:0,CO:0});

  useEffect(() => {
    const load = async () => {
      const [r1,r2,r3,r4,r5] = await Promise.all([
        fetch(`${BE}/stats/series?range=${range}`),
        fetch(`${BE}/stats/exceedance?range=${range}`),
        fetch(`${BE}/stats/duration?range=${range}`),
        fetch(`${BE}/stats/intensity?range=${range}`),
        fetch(`${BE}/stats/hazard_index?range=${range}`)
      ]);
      if (r1.ok) setSeries(await r1.json());
      if (r2.ok) setExceed(await r2.json());
      if (r3.ok) setDuration(await r3.json());
      if (r4.ok) setIntensity(await r4.json());
      if (r5.ok) setHazard(await r5.json());
    };
    load();
  }, [range]);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(["24h","7d","30d"] as RangeKey[]).map(k => (
          <button key={k} onClick={() => setRange(k)}
            className={`px-3 py-1 rounded-lg text-sm border ${range===k?"bg-gray-900 text-white":"hover:bg-gray-100"}`}>{k}</button>
        ))}
      </div>

      {/* KPI */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPI title="임계 초과 건수" value={`NH3 ${exceed.NH3} / VOC ${exceed.VOC} / CO ${exceed.CO}`}/>
        <KPI title="초과 지속(분)" value={`N ${duration.NH3} / V ${duration.VOC} / C ${duration.CO}`}/>
        <KPI title="강도 적분(분·ppm)" value={`N ${intensity.NH3} / V ${intensity.VOC} / C ${intensity.CO}`}/>
        <KPI title="Hazard Index(0~100)" value={`N ${hazard.NH3} / V ${hazard.VOC} / C ${hazard.CO}`}/>
      </div>

      {/* 시리즈 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {["NH3","VOC","CO"].map(k => (
          <div key={k} className="p-4 rounded-xl border">
            <div className="font-semibold mb-2">{k} 평균 추이 ({range})</div>
            <MiniSparkline points={series[k] || []}/>
          </div>
        ))}
      </div>
    </div>
  );
}

function KPI({title, value}:{title:string; value:string}) {
  return <div className="p-4 rounded-xl border"><div className="text-sm text-gray-500">{title}</div><div className="text-xl font-bold">{value}</div></div>;
}

function MiniSparkline({ points }: { points: Series[] }) {
  const w=320, h=80, pad=6;
  const xs = points.map((_,i)=>i), ys = points.map(p=>p.avg);
  const maxY = Math.max(1, ...ys, 0), minY = Math.min(0, ...ys, 0);
  const sx = (i:number)=> pad + i * ((w-2*pad) / Math.max(1, xs.length-1));
  const sy = (v:number)=> h - pad - (v - minY) * ((h-2*pad) / (maxY-minY+1e-6));
  const d = xs.map((i)=>`${i===0?'M':'L'} ${sx(i)} ${sy(ys[i]||0)}`).join(" ");
  return <svg width={w} height={h}><path d={d} fill="none" stroke="currentColor" strokeWidth="2"/></svg>;
}
