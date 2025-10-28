import type { AppProps } from "next/app";
import "../styles/globals.css";
import Navbar from "../frontend/components/Navbar";
import { useEffect } from "react";
import { useRouter } from "next/router";

const BE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000";

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  useEffect(() => {
    const es = new EventSource(`${BE}/stream`);
    const onEv = (ev: MessageEvent) => {
      try {
        const d = JSON.parse(ev.data);
        if (d?.event_id) router.push(`/logs/${d.event_id}`);
      } catch {}
    };
    es.addEventListener("evidence", onEv);
    return () => { es.removeEventListener("evidence", onEv); es.close(); };
  }, [router]);

  return (
    <>
      <Navbar />
      <main className="pt-12">
        <Component {...pageProps} />
      </main>
    </>
  );
}
