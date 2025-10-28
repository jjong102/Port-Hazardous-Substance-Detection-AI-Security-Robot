// pages/logs.tsx
import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/router";
import IncidentTimeline from "../frontend/components/IncidentTimeline";
import EventStatus from "../frontend/components/EventStatus";
import useIncident from "../frontend/hooks/useIncident";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL!;

// UI 전용
const CAUTION = 2.0, DANGER = 4.0;
const statusKR = { pending: "대기", approved: "승인", resolved: "해결" } as const;
const levelLabel = (v: number) => (v >= DANGER ? "위험" : v >= CAUTION ? "주의" : "정상");
const levelBadgeCls = (v: number) =>
  v >= DANGER
    ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200"
    : v >= CAUTION
    ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
    : "bg-gray-100 text-gray-700 dark:bg-neutral-800 dark:text-neutral-200";
const statusBadgeCls = (s: "pending" | "resolved" | "approved") =>
  s === "pending"
    ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200"
    : s === "resolved"
    ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
    : "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200";

type EventItem = {
  id: number; lat: number; lng: number;
  status: "pending" | "resolved" | "approved";
  created_at: string;
  substances: { substance: "NH3" | "VOC" | "CO"; max: number }[];
};

type UIItem = {
  id: number; substance: string; concentration: number;
  lat: number; lng: number; timestamp: string;
  status: "pending" | "resolved" | "approved";
};

export default function LogsPage() {
  const router = useRouter();
  const { state } = useIncident(BE);

  const [items, setItems] = useState<UIItem[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [dateFilter, setDateFilter] = useState<string>(""); // YYYY-MM-DD

  // 로컬타임 기준 YYYY-MM-DD 키
  const dateKeyLocal = (iso: string) => {
    const dt = new Date(iso); // 서버는 Z(UTC)
    const local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  };

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        // ✅ 전체 이벤트(대기/해결/승인) 조회
        const r = await fetch(`${BE}/events`, { cache: "no-store" });
        if (!alive) return;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const raw: EventItem[] = await r.json();

        const list: UIItem[] = raw.map((e) => {
          const top = [...e.substances].sort((a, b) => b.max - a.max)[0];
          return {
            id: e.id,
            substance: top?.substance ?? "-",
            concentration: top?.max ?? 0,
            lat: e.lat, lng: e.lng,
            timestamp: e.created_at,
            status: e.status,
          };
        });

        setItems(list);
        // 필터 적용 후 첫 아이템 자동 선택
        const firstId = (dateFilter ? list.filter(v => dateKeyLocal(v.timestamp) === dateFilter) : list)[0]?.id ?? null;
        setSelected(firstId);
      } catch (e: any) {
        setErr(e.message || "load fail");
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFilter]); // 날짜 바뀌면 선택 갱신

  const filteredItems = useMemo(
    () => (dateFilter ? items.filter(ev => dateKeyLocal(ev.timestamp) === dateFilter) : items),
    [items, dateFilter]
  );

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-neutral-950 dark:text-neutral-100">
      {/* 헤더 */}
      <header className="fixed top-0 inset-x-0 h-12 px-4 bg-white dark:bg-neutral-900 border-b border-gray-200 dark:border-neutral-800 z-[1100] flex items-center justify-between">
        <button onClick={() => router.push("/")} className="p-2 rounded hover:bg-gray-100 dark:hover:bg-neutral-800" aria-label="open menu">
          <span className="block w-5 h-0.5 bg-black dark:bg-white mb-1" />
          <span className="block w-5 h-0.5 bg-black dark:bg-white mb-1" />
          <span className="block w-5 h-0.5 bg-black dark:bg-white" />
        </button>
        <div className="font-semibold">해결 로그</div>
        <EventStatus state={state} />
      </header>

      <div className="pt-12 flex flex-col md:flex-row h-[calc(100vh-48px)]">
        {/* 좌측 리스트 */}
        <aside className="md:w-80 border-r border-gray-200 dark:border-neutral-800 overflow-auto p-4 bg-white dark:bg-neutral-900">
          {/* 날짜 선택 */}
          <div className="mb-4">
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="w-full rounded border px-2 py-1 text-sm bg-gray-50 dark:bg-neutral-800"
            />
            {dateFilter && (
              <button
                onClick={() => setDateFilter("")}
                className="mt-1 text-xs text-blue-600 hover:underline"
              >
                날짜 초기화
              </button>
            )}
          </div>

          {err && <div className="text-red-600 dark:text-red-300 text-sm mb-2">로드 오류: {err}</div>}
          <ul className="space-y-2">
            {filteredItems.map((ev) => {
              const lvlText = levelLabel(ev.concentration);
              const selectedCls =
                selected === ev.id
                  ? "ring-2 ring-blue-500 border-blue-300 bg-blue-50 dark:bg-blue-900/20"
                  : "border-gray-200 dark:border-neutral-700 hover:bg-gray-50 dark:hover:bg-neutral-800";
              return (
                <li key={ev.id}>
                  <button
                    onClick={() => setSelected(ev.id)}
                    className={`w-full text-left p-3 rounded-xl border transition ${selectedCls}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium truncate">
                        #{ev.id} · {ev.substance} {ev.concentration.toFixed(2)}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-xs px-2 py-0.5 rounded ${levelBadgeCls(ev.concentration)}`}>
                          {lvlText}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded ${statusBadgeCls(ev.status)}`}>
                          {statusKR[ev.status]}
                        </span>
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
                      {ev.lat.toFixed(5)}, {ev.lng.toFixed(5)} · {new Date(ev.timestamp).toLocaleString()}
                    </div>
                  </button>
                </li>
              );
            })}
            {filteredItems.length === 0 && (
              <li className="text-sm text-gray-500 dark:text-neutral-400">선택된 날짜에 로그 없음</li>
            )}
          </ul>
        </aside>

        {/* 우측 타임라인 */}
        <main className="flex-1 overflow-auto bg-gray-50 dark:bg-neutral-950">
          {selected ? (
            <div className="max-w-6xl mx-auto p-4">
              <IncidentTimeline id={selected} />
            </div>
          ) : (
            <div className="p-6 text-gray-500 dark:text-neutral-400">좌측에서 로그를 선택</div>
          )}
        </main>
      </div>
    </div>
  );
}