// Chunk-/Structure-/Event-Modelle.

/** 2D-Array von Tile-IDs. */
export type TileGrid = readonly (readonly number[])[];

/** Welt-Chunk (32×32 Tiles). */
export interface Chunk {
  readonly cx: number;
  readonly cy: number;
  readonly tiles: TileGrid;
  readonly biome?: string;
}

/** Strukur-Snapshot (auf der Welt platziertes Objekt). */
export interface Structure {
  readonly id: number;
  readonly type: string;
  readonly x: number;
  readonly y: number;
  readonly hp?: number;
  readonly max_hp?: number;
  readonly material?: string;
  readonly variant?: string;
  /** Owner-Player-ID (für Häuser/Truhen). */
  readonly owner_id?: number | null;
  /** True wenn das Frontend die Tür offen rendern soll. */
  readonly open?: boolean;
}

/** Welt-Event-Eintrag (Chronik). */
export interface WorldEvent {
  readonly id: number | string;
  readonly kind: string;
  readonly tier?: string;
  readonly title?: string;
  readonly description?: string;
  readonly ts?: string;
  readonly x?: number;
  readonly y?: number;
}

/** Dungeon-Marker auf der Minimap. */
export interface DungeonMarker {
  readonly id: number | string;
  readonly x: number;
  readonly y: number;
  readonly name?: string;
  readonly tier?: number;
}
