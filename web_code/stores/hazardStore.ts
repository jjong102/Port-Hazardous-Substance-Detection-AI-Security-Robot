// stores/hazardStore.ts
import { create } from 'zustand';  // ← 여기 변경

// 이벤트 데이터 타입 정의
export interface HazardEvent {
  id: string;
  substance: string;
  concentration: number;
  lat: number;
  lng: number;
  timestamp: string;
}

// 스토어에 담길 상태와 액션 타입
interface HazardState {
  events: HazardEvent[];
  addEvent: (event: HazardEvent) => void;
}

// 실제 스토어 생성
export const useHazardStore = create<HazardState>(set => ({
  events: [],
  addEvent: event =>
    set(state => ({
      events: [event, ...state.events],
    })),
}));
