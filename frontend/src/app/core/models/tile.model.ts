// Tile-Definition. Spiegel des Backend-Tile-Modells (siehe backend/world/* —
// die Welt sendet Chunks als 2D-Tile-ID-Array). Mini-Color ist nur für die
// Minimap-Darstellung im Frontend.
export interface TileDef {
  /** Numerische Tile-ID, wie sie das Backend in Chunks sendet. */
  readonly id: number;
  /** Deutscher Anzeige-Name. */
  readonly name: string;
  /** Phaser-Texture-Key für die Welt-Darstellung. */
  readonly sprite: string;
  /** CSS-Farbe für die Minimap-Pixel. */
  readonly miniColor: string;
}

/** Schlüssel der TILE-Map (gross geschrieben wie im Legacy-Code). */
export type TileKey =
  | 'WATER'
  | 'SAND'
  | 'GRASS'
  | 'FOREST'
  | 'MOUNTAIN'
  | 'DESERT'
  | 'JUNGLE'
  | 'LAVA'
  | 'SNOW'
  | 'SWAMP';
