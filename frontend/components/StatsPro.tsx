// frontend/components/StatsPro.tsx
"use client";
import React, { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, Legend,
  BarChart, Bar, CartesianGrid
} from "recharts";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL as string;
type RangeKey = "24h" | "7d" | "30d";
type SeriesPoint = { t: string; avg: number };
type SeriesDict = Record<"NH3"|"VOC"|"CO", SeriesPoint[] | undefined>;

export default function StatsPro() {
  const [range, setRange] = useState<RangeKey>("24h");
  const [series, setSeries] = useState<SeriesDict>({NH3:[],VOC:[],CO:[]});
  const [exceed, setExceed] = useState({NH3:0,VOC:0,CO:0});
  const [duration, setDuration] = useState({NH3:0,VOC:0,CO:0});
  const [intensity, setIntensity] = useState({NH3:0,VOC:0,CO:0});
  const [percentiles, setPercentiles] = useState<Record<string,{max:number;p:number}>>({});
  const [hazard, setHazard] = useState({NH3:0,VOC:0,CO:0});
  const [hotspots, setHotspots] = useState<{lat:number;lng:number;duration_min:number}[]>([]);

  useEffect(() => {
    const load = async () => {
      const reqs = await Promise.all([
        fetch(`${BE}/stats/series?range=${range}`),
        fetch(`${BE}/stats/exceedance?range=${range}`),
        fetch(`${BE}/stats/duration?range=${range}`),
        fetch(`${BE}/stats/intensity?range=${range}`),
        fetch(`${BE}/stats/percentiles?p=95&range=${range}`),
        fetch(`${BE}/stats/hazard_index?range=${range}`),
        fetch(`${BE}/stats/hotspots?range=${range}&grid=${range==="30d"?100:50}&limit=6`)
      ]);
      if (reqs[0].ok) setSeries(await reqs[0].json());
      if (reqs[1].ok) setExceed(await reqs[1].json());
      if (reqs[2].ok) setDuration(await reqs[2].json());
      if (reqs[3].ok) setIntensity(await reqs[3].json());
      if (reqs[4].ok) setPercentiles(await reqs[4].json());
      if (reqs[5].ok) setHazard(await reqs[5].json());
      if (reqs[6].ok) setHotspots(await reqs[6].json());
    };
    load();
  }, [range]);

  const areaData = useMemo(() => mergeSeries(series), [series]);
  const exceedData = useMemo(() => ([
    {name:"NH3", value: exceed.NH3},
    {name:"VOC", value: exceed.VOC},
    {name:"CO",  value: exceed.CO},
  ]), [exceed]);
  const durData = useMemo(() => ([
    {name:"NH3", min: duration.NH3, ei: intensity.NH3},
    {name:"VOC", min: duration.VOC, ei: intensity.VOC},
    {name:"CO",  min: duration.CO,  ei: intensity.CO},
  ]), [duration,intensity]);

  return (
    <div className="space-y-5">
      {/* 범위 토글 + KPI */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          {(["24h","7d","30d"] as RangeKey[]).map(k => (
            <button key={k} onClick={() => setRange(k)}
              className={`px-3 py-1 rounded-lg text-sm border ${range===k?"bg-gray-900 text-white":"hover:bg-gray-100"}`}>{k}</button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3">
          <KPI title="Hazard Index NH3" value={hazard.NH3}/>
          <KPI title="Hazard Index VOC" value={hazard.VOC}/>
          <KPI title="Hazard Index CO"  value={hazard.CO}/>
        </div>
      </div>

      {/* 평균 추이 멀티 에어리어 */}
      <div className="p-4 rounded-xl border">
        <div className="font-semibold mb-2">평균 농도 추이</div>
        <div style={{width:"100%", height: 260}}>
          <ResponsiveContainer>
            <AreaChart data={areaData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="t" hide />
              <YAxis />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="NH3" name="NH3" fillOpacity={0.2} strokeOpacity={1} />
              <Area type="monotone" dataKey="VOC" name="VOC" fillOpacity={0.2} strokeOpacity={1} />
              <Area type="monotone" dataKey="CO"  name="CO"  fillOpacity={0.2} strokeOpacity={1} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 임계 초과 건수 */}
      <div className="p-4 rounded-xl border">
        <div className="font-semibold mb-2">임계(≥2.0) 초과 건수</div>
        <div style={{width:"100%", height: 220}}>
          <ResponsiveContainer>
            <BarChart data={exceedData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false}/>
              <Tooltip />
              <Bar dataKey="value" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 지속시간 vs 강도 적분 */}
      <div className="p-4 rounded-xl border">
        <div className="font-semibold mb-2">지속시간(분) vs 강도 적분(분·ppm)</div>
        <div style={{width:"100%", height: 240}}>
          <ResponsiveContainer>
            <BarChart data={durData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis yAxisId="left" orientation="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip />
              <Legend />
              <Bar yAxisId="left" dataKey="min" name="지속(분)" />
              <Bar yAxisId="right" dataKey="ei"  name="강도 적분" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 백분위·최대 표 + 핫스팟 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl border">
          <div className="font-semibold mb-2">백분위(P95) · 최대</div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-gray-500"><th className="py-1">물질</th><th>P95</th><th>최대</th></tr></thead>
            <tbody>
              {["NH3","VOC","CO"].map(k=>(
                <tr key={k} className="border-t">
                  <td className="py-1">{k}</td>
                  <td>{num(percentiles[k]?.p)}</td>
                  <td>{num(percentiles[k]?.max)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 rounded-xl border">
          <div className="font-semibold mb-2">핫스팟 Top {Math.min(6, hotspots.length)}</div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-gray-500"><th className="py-1">위치</th><th>초과 지속(분)</th></tr></thead>
            <tbody>
              {hotspots.map((h,i)=>(
                <tr key={i} className="border-t">
                  <td className="py-1">{h.lat.toFixed(5)}, {h.lng.toFixed(5)}</td>
                  <td>{h.duration_min}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function KPI({title, value}:{title:string; value:number}) {
  return (
    <div className="p-3 rounded-xl border min-w-[180px]">
      <div className="text-xs text-gray-500">{title}</div>
      <div className="text-xl font-bold">{value.toFixed(1)}</div>
    </div>
  );
}

function mergeSeries(s: SeriesDict) {
  const keys = new Set<string>();
  (s.NH3||[]).forEach(p=>keys.add(p.t)); (s.VOC||[]).forEach(p=>keys.add(p.t)); (s.CO||[]).forEach(p=>keys.add(p.t));
  const by = Array.from(keys).sort().map(t => ({ t,
    NH3: (s.NH3||[]).find(p=>p.t===t)?.avg ?? 0,
    VOC: (s.VOC||[]).find(p=>p.t===t)?.avg ?? 0,
    CO:  (s.CO ||[]).find(p=>p.t===t)?.avg ?? 0,
  }));
  return by;
}

function num(v?: number){ return typeof v === "number" ? v.toFixed(2) : "—"; }
