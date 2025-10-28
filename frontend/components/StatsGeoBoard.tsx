"use client";
import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import HotspotModal from "./HotspotModal";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL as string;
const LeafletMap = dynamic(() => import("./_StatsGeoLeaflet"), { ssr: false });

type RangeKey = "24h"|"7d"|"30d";
type HotCell = {
  lat:number; lng:number; duration_min:number;
  series_min:number[]; subs_min:{NH3:number;VOC:number;CO:number};
  series_by_sub?:{NH3:number[];VOC:number[];CO:number[]};
};
type Payload = { labels: string[]; cells: HotCell[] };

export default function StatsGeoBoard() {
  const [range, setRange] = useState<RangeKey>("24h");
  const [data, setData] = useState<Payload>({ labels: [], cells: [] });
  const [sel, setSel] = useState<number|null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${BE}/stats/hotspots_series?range=${range}&grid=${range==="30d"?100:50}&limit=12&split=1`, { cache: "no-store" });
        const j = r.ok ? await r.json() : { labels: [], cells: [] };
        if (alive) setData(j);
      } catch { if (alive) setData({ labels: [], cells: [] }); }
    })();
    return () => { alive = false; };
  }, [range]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {(["24h","7d","30d"] as RangeKey[]).map(k=>(
            <button key={k} onClick={()=>setRange(k)}
              className={`px-3 py-1 rounded-lg text-sm border ${range===k?"bg-gray-900 text-white":"hover:bg-gray-100"}`}>
              {k}
            </button>
          ))}
        </div>
        <div className="text-xs text-gray-500">핫스팟 상위 {data.cells.length}개</div>
      </div>

      <div className="rounded-xl border overflow-hidden" style={{height:420}}>
        <LeafletMap cells={data.cells as any}/>
      </div>

      <div className="rounded-xl border overflow-x-auto">
        <table className="min-w-[760px] w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-2 px-3">#</th>
              <th className="py-2 px-3">위도</th>
              <th className="py-2 px-3">경도</th>
              <th className="py-2 px-3">지속(분)</th>
              <th className="py-2 px-3">물질</th>
              <th className="py-2 px-3">분석</th>
            </tr>
          </thead>
          <tbody>
            {data.cells.map((c,i)=>(
              <tr key={i} className="border-t">
                <td className="py-2 px-3">{i+1}</td>
                <td className="py-2 px-3">{c.lat.toFixed(5)}</td>
                <td className="py-2 px-3">{c.lng.toFixed(5)}</td>
                <td className="py-2 px-3">{c.duration_min.toFixed(2)}</td>
                <td className="py-2 px-3">
                  <Chips s={c.subs_min}/>
                </td>
                <td className="py-2 px-3">
                  <button onClick={()=>setSel(i)} className="px-3 py-1 rounded-lg border hover:bg-gray-100">보기</button>
                </td>
              </tr>
            ))}
            {data.cells.length===0 && (
              <tr><td colSpan={6} className="py-6 text-center text-gray-500">데이터 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <HotspotModal
  open={sel!==null}
  onClose={()=>setSel(null)}
  cell={sel!==null ? data.cells[sel] : null}
  range={range}
/>

    </div>
  );
}

function Chips({ s }:{ s:{NH3:number;VOC:number;CO:number} }) {
  const arr = ([
    ["NH3", s.NH3] as const,
    ["VOC", s.VOC] as const,
    ["CO",  s.CO]  as const,
  ]).filter(([,v])=> (v||0) > 0);
  const color = (k:string)=> k==="NH3"?"bg-purple-200 text-purple-900":k==="VOC"?"bg-orange-200 text-orange-900":"bg-sky-200 text-sky-900";
  return (
    <div className="flex flex-wrap gap-2">
      {arr.map(([k,v])=>(
        <span key={k} className={`px-2 py-0.5 rounded text-xs font-semibold ${color(k)}`}>{k} {v.toFixed(1)}m</span>
      ))}
    </div>
  );
}
