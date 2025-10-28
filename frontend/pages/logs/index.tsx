// frontend/pages/logs/index.tsx
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";

const BE = (process.env.NEXT_PUBLIC_BACKEND_URL as string) || "http://localhost:5000";

const CAUTION = 2.0; const DANGER = 4.0;
const sev = (v:number)=> v>=DANGER?"danger":v>=CAUTION?"warn":"normal";
const badge = (l:string)=> l==="danger"?"bg-red-100 text-red-800":l==="warn"?"bg-amber-100 text-amber-800":"bg-gray-100 text-gray-700";


type Incident = {
  id: number; status: string; lat: number; lng: number;
  created_at?: string; substances?: { substance: string; max: number }[];
};

function NavBtn({ children, onClick, active=false }:{
  children: React.ReactNode; onClick: () => void; active?: boolean;
}) {
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

export default function LogsIndex() {
  const router = useRouter();
  const [list, setList] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  const load = async () => {
    try {
      const r = await fetch(`${BE}/incidents/active`, { cache: "no-store" });
      const d = r.ok ? await r.json() : [];
      setList(Array.isArray(d) ? d : d ? [d] : []);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen">
      {/* 헤더 */}
      <header className="fixed top-0 inset-x-0 h-12 px-4 bg-white text-gray-900 border-b z-[1200] flex items-center justify-between">
        <button onClick={() => setOpen(true)} className="p-2 rounded hover:bg-gray-100" aria-label="open menu">
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black" />
        </button>
        <div className="font-semibold">해결 전 로그</div>
        <button onClick={load} className="text-sm px-3 py-1 rounded bg-gray-100 hover:bg-gray-200">새로고침</button>
      </header>

      {/* 드로어 */}
      {open && (
        <div className="fixed inset-0 z-[2001]">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white text-gray-900 p-4 space-y-2 shadow-2xl">
            <h2 className="text-sm font-bold mb-2">메뉴</h2>
            <NavBtn onClick={() => { router.push("/"); setOpen(false); }}>라이브</NavBtn>
            <NavBtn onClick={() => { router.push("/?tab=stats"); setOpen(false); }}>통계</NavBtn>
            <NavBtn onClick={() => { router.push("/?tab=admin"); setOpen(false); }}>초기화</NavBtn>
            <NavBtn active onClick={() => { router.push("/logs"); setOpen(false); }}>해결 전 로그</NavBtn>
          </aside>
        </div>
      )}

      {/* 본문 */}
      <main className="pt-12 p-4 max-w-6xl mx-auto">
        {loading ? (
          <div className="text-gray-500">불러오는 중…</div>
        ) : list.length === 0 ? (
          <div className="text-gray-500">활성 인시던트 없음</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {list.map((e) => (
              <Link href={`/logs/${e.id}`} key={e.id} className="border rounded-lg p-3 hover:shadow">
                <div className="flex items-center justify-between">
                  <div className="font-medium">#{e.id}</div>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    e.status === "pending" ? "bg-amber-100 text-amber-800"
                    : e.status === "resolved" ? "bg-blue-100 text-blue-800"
                    : "bg-gray-100 text-gray-700"
                  }`}>{e.status}</span>
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  {e.lat.toFixed(5)}, {e.lng.toFixed(5)}
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {(e.substances || []).slice(0, 3).map((s) => (
                    <span key={s.substance} className="text-xs px-2 py-0.5 rounded border">
                      {s.substance} {s.max.toFixed(2)}
                    </span>
                  ))}
                </div>
                {e.created_at && (
                  <div className="text-xs text-gray-400 mt-2">
                    {new Date(e.created_at).toLocaleString()}
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
