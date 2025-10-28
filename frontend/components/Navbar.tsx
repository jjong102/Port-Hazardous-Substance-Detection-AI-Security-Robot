import Link from "next/link";
import { useRouter } from "next/router";
import { useState } from "react";

export default function Navbar() {
  const r = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <>
      <header className="fixed top-0 inset-x-0 h-12 px-4 bg-white text-gray-900 border-b z-[1100] flex items-center justify-between">
        <button onClick={() => setOpen(true)} className="p-2 rounded hover:bg-gray-100" aria-label="open menu">
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black mb-1" />
          <span className="block w-5 h-0.5 bg-black" />
        </button>
        <Link href="/" className="font-semibold">항만 유해물질 대시보드</Link>
        <div />
      </header>

      {open && (
        <div className="fixed inset-0 z-[2000]">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-white text-gray-900 p-4 space-y-2 shadow-2xl">
            <p className="text-sm font-bold mb-2">메뉴</p>
            <NavBtn href="/" active={r.pathname === "/"} onClose={() => setOpen(false)}>라이브</NavBtn>
            <NavBtn href="/?tab=stats" onClose={() => setOpen(false)}>통계</NavBtn>
            <NavBtn href="/?tab=admin" onClose={() => setOpen(false)}>초기화</NavBtn>
            <NavBtn href="/logs" active={r.pathname.startsWith("/logs")} onClose={() => setOpen(false)}>
              해결 전 로그
            </NavBtn>
          </aside>
        </div>
      )}
    </>
  );
}

function NavBtn({
  href, children, active=false, onClose,
}: { href: string; children: React.ReactNode; active?: boolean; onClose: () => void }) {
  return (
    <Link
      href={href}
      onClick={onClose}
      className={`block w-full px-3 py-2 rounded-lg text-sm ${
        active ? "bg-gray-200 text-gray-900" : "text-gray-900 hover:bg-gray-100"
      }`}
    >
      {children}
    </Link>
  );
}
