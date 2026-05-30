// Time + Weather (Backend-Vertrag).

export interface TimeSnapshot {
  readonly day: number;
  readonly hour: number;
  readonly minute: number;
  readonly phase?: 'dawn' | 'day' | 'dusk' | 'night';
  readonly is_blood_moon?: boolean;
}

export interface WeatherSnapshot {
  readonly kind: string;
  readonly intensity: number;
}
