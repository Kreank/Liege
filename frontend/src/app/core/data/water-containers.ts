// Container-Kapazitäten — mirror von items.py WATER_CONTAINER_CAPACITY (Welle 17).
// Portiert aus frontend/legacy/app.js Z. 1150-1157.

export const WATER_CONTAINER_CAPACITY: Readonly<Record<string, number>> = {
  wooden_bucket:       1,
  iron_bucket:         2,
  leather_waterskin:   3,
  wooden_watering_can: 4,
  iron_watering_can:   6,
};

export const WATER_CONTAINER_KINDS: ReadonlySet<string> = new Set(
  Object.keys(WATER_CONTAINER_CAPACITY)
);
