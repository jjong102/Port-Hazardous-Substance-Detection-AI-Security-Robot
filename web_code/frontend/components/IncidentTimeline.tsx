// frontend/components/IncidentTimeline.tsx
import { useEffect, useMemo, useState } from "react";

const BE = (process.env.NEXT_PUBLIC_BACKEND_URL || "").replace(/\/$/, "");
const ADMIN = process.env.NEXT_PUBLIC_ADMIN_TOKEN ?? "";
const toAbs = (u?: string) => (!u ? "" : /^https?:\/\//i.test(u) ? u : `${BE}${u.startsWith("/") ? "" : "/"}${u}`);
const H: HeadersInit | undefined = ADMIN ? { "X-Admin-Token": ADMIN } : undefined;

type Evidence = { id: number; kind: "photo" | "video" | "audio" | "note" | string; url?: string; note?: string; ts: string };
type Action = { id: number; actor: string; action: string; detail?: string; ts: string };

const ACT_KR: Record<string, string> = {
  created: "생성",
  detected: "감지",
  resolve: "해결",
  approved: "승인",
  approve: "승인",
  perimeter: "경계 변경",
  report_build: "보고서 생성",
  sop_step: "SOP 단계",
  cosign: "코사인",
};
const ACTOR_KR: Record<string, string> = { system: "시스템", app: "앱", web: "웹" };

export default function IncidentTimeline({ id }: { id: number }) {
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const headers = ADMIN ? { "X-Admin-Token": ADMIN } : {};

  const load = async () => {
    try {
      const r = await fetch(`${BE}/events/${id}/timeline`, {
        headers: H,
        cache: "no-store",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setEvidence((j.evidence || []) as Evidence[]);
      setActions((j.actions || []) as Action[]);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "load fail");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const byDay = useMemo(() => {
    const g: Record<string, Action[]> = {};
    for (const a of actions) {
      const d = fmtDate(a.ts, { dateOnly: true });
      (g[d] ||= []).push(a);
    }
    return g;
  }, [actions]);

  if (err) return <div className="p-4 text-red-500">{err}</div>;
  if (loading) return <div className="p-4">불러오는 중…</div>;

  return (
    <div className="space-y-8">
      {/* 증거 */}
      <section>
        <div className="sticky top-0 z-10 -mx-4 px-4 py-2 backdrop-blur bg-white/70 dark:bg-neutral-950/70 border-b border-gray-200 dark:border-neutral-800">
          <h3 className="text-base font-semibold">증거</h3>
        </div>

        {evidence.length === 0 ? (
          <div className="p-4 text-sm text-gray-500 dark:text-neutral-400">기록 없음</div>
        ) : (
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-3">
            {evidence.map((e) => (
              <li key={e.id} className="rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden">
                <div className="p-3 flex items-center justify-between">
                  <span className="text-sm font-medium">{labelKR(e.kind)}</span>
                  <span className="text-xs text-gray-500 dark:text-neutral-400">{fmtDate(e.ts)}</span>
                </div>

                {renderBody(e)}

                <div className="p-3 flex items-center gap-2">
                  {e.url && (
                    <a
                      className="text-xs px-2.5 py-1 rounded-md bg-blue-600 text-white hover:bg-blue-700"
                      href={toAbs(e.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      파일 열기
                    </a>
                  )}
                  {e.note && <span className="text-sm text-gray-700 dark:text-neutral-200">{e.note}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 액션 */}
      <section>
        <div className="sticky top-0 z-10 -mx-4 px-4 py-2 backdrop-blur bg-white/70 dark:bg-neutral-950/70 border-b border-gray-200 dark:border-neutral-800">
          <h3 className="text-base font-semibold">액션 타임라인</h3>
        </div>

        {actions.length === 0 ? (
          <div className="p-4 text-sm text-gray-500 dark:text-neutral-400">기록 없음</div>
        ) : (
          <div className="space-y-6 pt-3">
            {Object.entries(byDay).map(([d, arr]) => (
              <div key={d} className="space-y-2">
                <div className="text-xs font-semibold text-gray-500 dark:text-neutral-400">{d}</div>
                {arr.map((a) => (
                  <div
                    key={a.id}
                    className="rounded-xl border border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-3"
                  >
                    <div className="text-sm font-medium">{ACT_KR[a.action] || a.action}</div>
                    <div className="text-xs text-gray-500 dark:text-neutral-400 mt-0.5">
                      {fmtDate(a.ts)} · {ACTOR_KR[a.actor] || a.actor}
                      {a.detail ? <span> · {a.detail}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/* ---------- helpers ---------- */

function labelKR(kind: string) {
  switch (kind) {
    case "photo": return "사진";
    case "video": return "영상";
    case "audio": return "음성";
    case "note": return "메모";
    default: return kind;
  }
}

function fmtDate(ts: string, opt?: { dateOnly?: boolean }) {
  try {
    // Handles both ISO with Z and "YYYY-MM-DD HH:MM:SS"
    const date = /Z$/.test(ts) ? new Date(ts) : new Date(ts.replace(" ", "T"));
    return date.toLocaleString("ko-KR", opt?.dateOnly ? { year: "numeric", month: "long", day: "numeric" } : undefined);
  } catch {
    return ts;
  }
}

function renderBody(e: Evidence) {
  const url = toAbs(e.url);
  if (e.kind === "photo" && url)
    return <img src={url} alt="evidence" className="w-full aspect-video object-cover border-t border-gray-200 dark:border-neutral-800" />;
  if (e.kind === "video" && url)
    return (
      <video controls className="w-full aspect-video border-t border-gray-200 dark:border-neutral-800">
        <source src={url} />
      </video>
    );
  if (e.kind === "audio" && url)
    return (
      <div className="px-3 pb-1 border-t border-gray-200 dark:border-neutral-800">
        <audio controls className="w-full mt-1">
          <source src={url} />
        </audio>
      </div>
    );
  if (e.kind === "note")
    return null;
  // unknown with file
  if (url)
    return <div className="px-3 pb-1 text-xs text-gray-500 dark:text-neutral-400 border-t border-gray-200 dark:border-neutral-800">첨부 파일</div>;
  return null;
}
