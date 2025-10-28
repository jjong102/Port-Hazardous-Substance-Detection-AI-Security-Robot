// frontend/hooks/useSSE.ts
import { useEffect, useRef } from "react";

type HandlerMap = {
  gps?: (data: any) => void;
  event?: (data: any) => void;
  ping?: (data: any) => void;
};

export default function useSSE(url: string, handlers: HandlerMap) {
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url);
    esRef.current = es;

    if (handlers.gps) es.addEventListener("gps", (e) => handlers.gps!(JSON.parse((e as MessageEvent).data)));
    if (handlers.event) es.addEventListener("event", (e) => handlers.event!(JSON.parse((e as MessageEvent).data)));
    if (handlers.ping) es.addEventListener("ping", (e) => handlers.ping!((e as MessageEvent).data));

    es.onerror = () => {
      // browser auto-reconnect fallback
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url]);

  return esRef;
}
