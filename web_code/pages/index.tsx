// pages/index.tsx
import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/router";
import useIncident, { Incident } from "../frontend/hooks/useIncident";
import ActiveIncidentGrid from "../frontend/components/ActiveIncidentGrid";
import LiveReadings from "../frontend/components/LiveReadings";
import EventStatus from "../frontend/components/EventStatus";
import StatsGeoBoard from "../frontend/components/StatsGeoBoard";

const RobotMap = dynamic(() => import("../frontend/components/RobotMap"), { ssr: false });

const BE = (process.env.NEXT_PUBLIC_BACKEND_URL as string) || "http://localhost:5000";
const TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN as string;

type ReadingMsg = {
  id: number;
  type: "NH3" | "VOC" | "CO" | "GPS";
  value?: number | null;
  lat?: number | null;
  lng?: number | null;
  vehicle_id?: string;
  timestamp: string;
};

export default function Home() {
  const router = useRouter();
  const [menu, setMenu] = useState<"live" | "stats" | "admin">("live");
  const [open, setOpen] = useState(false);
  const { incident, setIncident, state } = useIncident(BE);

  // 실시간 센서 최신값 저장 (주의 이하도 모두 수신)
  const [latestReadings, setLatestReadings] = useState<Record<string, ReadingMsg | null>>({
    NH3: null, VOC: null, CO: null,
  });
  // (선택) 최신 GPS
  const [latestGps, setLatestGps] = useState<ReadingMsg | null>(null);

  useEffect(() => {
    const es = new EventSource(`${BE}/stream`, { withCredentials: false });

    // GPS 최초/갱신
    es.addEventListener("gps", (ev) => {
      const msg = JSON.parse((ev as MessageEvent).data) as ReadingMsg;
      setLatestGps(msg);
    });

    es.onerror = () => {
      // 연결이 끊겨도 브라우저가 자동 재연결 시도
      // 필요 시 로깅만
      // console.warn("SSE disconnected");
    };

    return () => es.close();
  }, []);

  const approve = async (id: number) => {
    const r = await fetch(`${BE}/events/${id}/approve?token=${TOKEN}`, {
      method: "POST",
      headers: { "X-Admin-Token": TOKEN, "X-User": "web" },
    });
    if (!r.ok) {
      const t = await r.text();
      alert(`승인 실패 ${r.status}: ${t}`);
      return;
    }
    setIncident(null);
  };

  return (
    <div className="min-h-screen">
      {/* 헤더 */}
      <header className="fixed top-0 inset-x-0 h-12 px-4 bg-white text-gray-900 border-b z-[1100] flex items-center justify-between">
        <button onClick={() => setOpen(true)} className="p-2 rounded hover:bg-gray-100" aria-label="open menu">
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black" />
        </button>
        <div className="font-semibold">항만 유해물질 대시보드</div>
        <EventStatus state={state} />
      </header>

      {/* 드로어 */}
      {open && (
        <div className="fixed inset-0 z-[2000]">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white text-gray-900 p-4 space-y-2 shadow-2xl">
            <h2 className="text-sm font-bold mb-2">메뉴</h2>
            <NavBtn active={menu === "live"} onClick={() => { setMenu("live"); setOpen(false); }}>라이브</NavBtn>
            <NavBtn active={menu === "stats"} onClick={() => { setMenu("stats"); setOpen(false); }}>통계</NavBtn>
            <NavBtn active={menu === "admin"} onClick={() => { setMenu("admin"); setOpen(false); }}>초기화</NavBtn>
            <NavBtn active={false} onClick={() => { router.push("/logs"); setOpen(false); }}>해결 로그</NavBtn>
          </aside>
        </div>
      )}

      {/* 본문 */}
      <main className="pt-12 p-4 space-y-6">
        {menu === "live" && (
          <>
            <section>
              <h2 className="text-lg font-semibold mb-2">로봇 위치</h2>
              {/* RobotMap이 내부에서 SSE를 보지 않는다면 latestGps를 prop으로 넘겨도 됨 */}
              <RobotMap /* gps={latestGps} */ />
            </section>

            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <h3 className="text-base font-semibold">실시간(3종 센서)</h3>
                <LiveReadings />
              </div>
              <div className="space-y-3">
                <h3 className="text-base font-semibold">주의 이상 이벤트(최대 3장)</h3>
                <ActiveIncidentGrid incident={incident as Incident | null} onApprove={approve} />
              </div>
            </section>
          </>
        )}

        {menu === "stats" && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">통계</h2>
            <StatsGeoBoard />
          </div>
        )}

        {menu === "admin" && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">초기화</h2>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={async () => { await fetch(`${BE}/admin/clear_recent?hours=24`, { method: "POST" }); location.reload(); }}
                className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm"
              >
                최근 24시간 서버 통계 초기화
              </button>
              <button
                onClick={async () => {
                  if (!confirm("모든 데이터 삭제")) return;
                  await fetch(`${BE}/admin/clear_all`, { method: "POST" });
                  location.reload();
                }}
                className="px-4 py-2 rounded-lg bg-red-700 text-white text-sm"
              >
                서버 전체 초기화
              </button>
              <button
                onClick={() => { try { localStorage.clear(); sessionStorage.clear(); } catch {} ; location.reload(); }}
                className="px-4 py-2 rounded-lg bg-gray-700 text-white text-sm"
              >
                브라우저 캐시 초기화
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function NavBtn({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode; }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
        active ? "bg-gray-200 text-gray-900" : "text-gray-900 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );
}