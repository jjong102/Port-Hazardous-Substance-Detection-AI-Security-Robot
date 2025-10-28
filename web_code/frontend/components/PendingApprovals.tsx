import { useEffect, useState } from "react";
import IncidentTimeline from "./IncidentTimeline";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL!;
const ADMIN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "";

type HazardEvent = {
  id:number; substance:string; concentration:number;
  lat:number; lng:number; timestamp:string; status:"pending"|"resolved"|"approved";
};

export default function PendingApprovals() {
  const [items, setItems] = useState<HazardEvent[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    const r = await fetch(`${BE}/incident/active`, {
      headers: ADMIN ? { "X-Admin-Token": ADMIN } : {},
      cache: "no-store",
    });
    const j = await r.json();
    const list: HazardEvent[] = Array.isArray(j) ? j : (j.items || []);
    setItems(list.filter(e => e.status === "resolved")); // 승인 대상만
  }

  useEffect(() => { load(); }, []);

  async function approve(id:number) {
    try {
      setBusyId(id);
      const r = await fetch(`${BE}/events/${id}/approve`, {
        method: "POST",
        headers: {
          "Content-Type":"application/json",
          ...(ADMIN ? { "X-Admin-Token": ADMIN } : {}),
        },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await load();
      setOpenId(null);
    } catch (e) {
      console.error(e);
      alert("승인 실패. 토큰/서버 확인");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-3">
      {items.map(ev => (
        <div key={ev.id} className="border rounded p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold">#{ev.id} · {ev.substance} {ev.concentration.toFixed(2)}</div>
              <div className="text-xs text-gray-500">
                {ev.lat.toFixed(5)}, {ev.lng.toFixed(5)} · {new Date(ev.timestamp).toLocaleString()}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="px-3 py-1.5 text-sm border rounded"
                onClick={() => setOpenId(ev.id)}>
                로그/증거
              </button>
              <button
                className="px-3 py-1.5 text-sm rounded bg-black text-white disabled:opacity-50"
                disabled={busyId === ev.id}
                onClick={() => approve(ev.id)}>
                {busyId === ev.id ? "승인 중…" : "승인"}
              </button>
            </div>
          </div>
        </div>
      ))}
      {items.length===0 && <div className="text-sm text-gray-500">승인 대기 없음</div>}

      {/* 오른쪽 드로어 */}
      {openId !== null && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/30" onClick={() => setOpenId(null)} />
          <div className="absolute right-0 top-0 h-full w-full sm:w-[420px] bg-white shadow-xl z-50">
            <div className="p-3 border-b flex items-center justify-between">
              <div className="font-semibold">#{openId} 로그/증거</div>
              <button onClick={() => setOpenId(null)} className="text-sm text-gray-500">닫기</button>
            </div>
            <IncidentTimeline id={openId}/>
          </div>
        </div>
      )}
    </div>
  );
}
