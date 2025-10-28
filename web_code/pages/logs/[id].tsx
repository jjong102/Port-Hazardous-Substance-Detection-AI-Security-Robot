import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";

const BE = (process.env.NEXT_PUBLIC_BACKEND_URL || "").replace(/\/$/, "");
const toAbs = (u?: string) => (!u ? "" : /^https?:\/\//i.test(u) ? u : `${BE}${u.startsWith("/") ? "" : "/"}${u}`);

type Evidence = { id: number; kind: string; url?: string; note?: string; ts: string };
type Action = { id: number; actor: string; action: string; detail?: string; ts: string };

export default function LogDetail() {
  const router = useRouter();
  const id = router.query.id as string | undefined;

  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [actions, setActions] = useState<Action[] | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!id) return;
    try {
      const r = await fetch(`${BE}/events/${id}/timeline`, { cache: "no-store" });
      if (!r.ok) throw new Error();
      const j = await r.json();
      setEvidence(j.evidence || []);
      setActions(j.actions || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const title = useMemo(() => (id ? `로그 #${id}` : "로그"), [id]);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="sticky top-0 z-50 border-b border-neutral-800 bg-neutral-950/80 backdrop-blur px-4 h-12 flex items-center justify-between">
        <div className="font-semibold">{title}</div>
        <div className="flex gap-2">
          <Link href="/logs" className="text-sm px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700">
            목록
          </Link>
          <Link href="/" className="text-sm px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700">
            라이브
          </Link>
        </div>
      </header>

      <main className="p-4 max-w-6xl mx-auto">
        {loading ? (
          <div className="text-neutral-400">불러오는 중…</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 좌측: 증거 그리드 */}
            <section className="lg:col-span-2">
              <h2 className="text-base font-semibold mb-3">증거</h2>
              {(!evidence || evidence.length === 0) ? (
                <div className="text-neutral-400 text-sm">없음</div>
              ) : (
                <ul className="grid gap-4 sm:grid-cols-2">
                  {evidence!.map((ev) => (
                    <li key={ev.id} className="rounded-2xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
                      <div className="p-3 flex items-center justify-between">
                        <span className="text-xs px-2 py-0.5 rounded bg-neutral-800">{ev.kind}</span>
                        <span className="text-xs text-neutral-400">{fmt(ev.ts)}</span>
                      </div>

                      <MediaPreview kind={ev.kind} url={toAbs(ev.url)} />

                      {(ev.note || ev.url) && (
                        <div className="p-3 border-t border-neutral-800 text-sm">
                          {ev.note && <div className="text-neutral-200">{ev.note}</div>}
                          {ev.url && (
                            <a className="text-blue-500 underline mt-1 inline-block" href={toAbs(ev.url)} target="_blank">
                              파일 열기
                            </a>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* 우측: 액션 타임라인 */}
            <section className="lg:col-span-1">
              <h2 className="text-base font-semibold mb-3">액션 타임라인</h2>
              {(!actions || actions.length === 0) ? (
                <div className="text-neutral-400 text-sm">없음</div>
              ) : (
                <ol className="relative border-l border-neutral-800 pl-4">
                  {actions!.map((a) => {
                    const style = colorOf(a.action);
                    return (
                      <li key={a.id} className="mb-6 ml-2">
                        <span className={`absolute -left-[9px] mt-1 h-3 w-3 rounded-full ${style.dot}`} />
                        <div className="text-xs text-neutral-400">{fmt(a.ts)}</div>
                        <div className={`text-sm font-medium ${style.text}`}>{labelOf(a.action)}</div>
                        <div className="text-xs text-neutral-500">{a.actor}{a.detail ? ` · ${a.detail}` : ""}</div>
                      </li>
                    );
                  })}
                </ol>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function MediaPreview({ kind, url }: { kind?: string; url?: string }) {
  if (!url) return null;
  if (kind === "photo") {
    return <img src={url} className="w-full aspect-video object-cover" alt="evidence" />;
  }
  if (kind === "video") {
    return <video src={url} controls className="w-full aspect-video" />;
  }
  if (kind === "audio") {
    return (
      <div className="p-3">
        <audio src={url} controls className="w-full" />
      </div>
    );
  }
  return null;
}

function colorOf(action: string) {
  if (action === "approve") return { dot: "bg-emerald-500", text: "text-emerald-400" };
  if (action === "resolve") return { dot: "bg-blue-500", text: "text-blue-400" };
  if (action === "detected") return { dot: "bg-amber-500", text: "text-amber-400" };
  if (action === "created") return { dot: "bg-neutral-500", text: "text-neutral-300" };
  return { dot: "bg-purple-500", text: "text-purple-300" };
}

function labelOf(a: string) {
  if (a === "approve") return "승인";
  if (a === "resolve") return "해결";
  if (a === "detected") return "감지";
  if (a === "created") return "생성";
  return a;
}

function fmt(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}
