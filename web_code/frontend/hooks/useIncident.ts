// frontend/hooks/useIncident.ts
import { useEffect, useRef, useState } from "react";

export type Incident = {
  id: number; vehicle_id: string; status: "pending"|"approved"|"resolved";
  lat: number; lng: number;
  created_at?: string; approved_at?: string|null; resolved_at?: string|null;
  substances: { substance: "NH3"|"VOC"|"CO"; max: number; last_at?: string|null }[];
};

export type IncidentState = {
  sse: "open" | "closed";
  lastUpdate: string | null;
  backend: string;
};

export default function useIncident(BE: string) {
  const [inc, setInc] = useState<Incident | null>(null);
  const [state, setState] = useState<IncidentState>({ sse: "closed", lastUpdate: null, backend: BE });
  const timer = useRef<any>(null);

  // 폴백 폴링
  useEffect(() => {
    const pull = async () => {
      try {
        const r = await fetch(`${BE}/incident/active`, { cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          setInc(j);
          setState(s => ({...s, lastUpdate: new Date().toISOString()}));
        } else {
          setInc(null);
        }
      } catch {
        // ignore
      } finally {
        timer.current = setTimeout(pull, 5000);
      }
    };
    pull();
    return () => clearTimeout(timer.current);
  }, [BE]);

  // SSE
  useEffect(() => {
    const es = new EventSource(`${BE}/stream`);
    es.onopen = () => setState(s => ({...s, sse: "open"}));
    es.onerror = () => setState(s => ({...s, sse: "closed"}));
    es.addEventListener("incident", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      if (data?.status === "approved" || data?.status === "resolved") setInc(null);
      else setInc(data);
      setState(s => ({...s, lastUpdate: new Date().toISOString()}));
    });
    return () => es.close();
  }, [BE]);

  return { incident: inc, setIncident: setInc, state };
}
