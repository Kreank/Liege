// Dungeon-Tile-Konstanten — Spiegel des Backend-Modells `dungeon_world.py`.
//
// Welle H1-A (2026-05-31): Dungeon-Floors kommen vom Backend mit eigenem
// Tile-ID-Schema, das NICHT identisch mit den Overworld-Biome-IDs aus
// `tiles.ts` ist (Overworld: 0=Wasser, 1=Strand … vs. Dungeon: 0=Wand,
// 1=Boden …). Wir halten die beiden Schemata bewusst getrennt — der
// `DungeonRenderer` rendert mit dieser Tabelle, die Overworld-Tile-Layer
// in `WorldScene.syncTileLayer` mit `tiles.ts`.
//
// Backend-Referenz: backend/dungeon_world.py Z. 26:
//     WALL, FLOOR, CORRIDOR, STAIRS_UP, STAIRS_DOWN = 0, 1, 2, 3, 4

/** Numerische Tile-IDs aus `dungeon_world.py` (Wert-stabil). */
export const DUNGEON_TILE = {
  WALL:        0,
  FLOOR:       1,
  CORRIDOR:    2,
  STAIRS_UP:   3,
  STAIRS_DOWN: 4,
} as const;

/** ID → Phaser-Texture-Key (registriert im `AssetLoaderService`). */
export const DUNGEON_TILE_SPRITE: Readonly<Record<number, string>> = {
  [DUNGEON_TILE.WALL]:        'dungeon_tile_wall',
  [DUNGEON_TILE.FLOOR]:       'dungeon_tile_floor',
  [DUNGEON_TILE.CORRIDOR]:    'dungeon_tile_floor', // Korridor = Boden-Variante
  [DUNGEON_TILE.STAIRS_UP]:   'dungeon_tile_stairs_up',
  [DUNGEON_TILE.STAIRS_DOWN]: 'dungeon_tile_stairs_down',
};

/** Asset-Pfade — Single-PNG pro Tile-Typ. Pfade existieren unter
 *  `/assets/dungeons/` (siehe `assets/dungeons/dungeon_wall.png` etc.). */
export const DUNGEON_TILE_ASSETS: Readonly<Record<string, string>> = {
  dungeon_tile_wall:        '/assets/dungeons/dungeon_wall.png',
  dungeon_tile_floor:       '/assets/dungeons/dungeon_floor.png',
  dungeon_tile_stairs_up:   '/assets/dungeons/stairs_up.png',
  dungeon_tile_stairs_down: '/assets/dungeons/stairs_down.png',
};

/** Fallback-Farben (RGB-Hex), falls Asset 404. KEIN Magenta — dunkles
 *  Grau für Wand, schwarz für Boden (so erkennbar dass es ein Dungeon ist). */
export const DUNGEON_FALLBACK_COLORS: Readonly<Record<number, number>> = {
  [DUNGEON_TILE.WALL]:        0x2a2630,
  [DUNGEON_TILE.FLOOR]:       0x14121a,
  [DUNGEON_TILE.CORRIDOR]:    0x1c1a24,
  [DUNGEON_TILE.STAIRS_UP]:   0x8a7a3a,
  [DUNGEON_TILE.STAIRS_DOWN]: 0x6a5a2a,
};

/** Feature-Sprites im Dungeon (Truhen, Decor, ausgelöste Fallen). */
export const DUNGEON_FEATURE_SPRITES = {
  chest_closed: 'dungeon_feat_chest_closed',
  chest_opened: 'dungeon_feat_chest_opened',
  altar:        'dungeon_feat_altar',
  brazier:      'dungeon_feat_brazier',
  sarcophagus:  'dungeon_feat_sarcophagus',
  wall_torch:   'dungeon_feat_torch',
  trap:         'dungeon_feat_trap',
} as const;

/** Asset-Pfade für Features. */
export const DUNGEON_FEATURE_ASSETS: Readonly<Record<string, string>> = {
  // Welle H1-A: aktuell nur 1 Chest-PNG verfügbar (treasure_chest.png).
  // "geöffnet" rendern wir durch Tint+Alpha auf dem gleichen Sprite, bis
  // ein dedizierter offen-PNG nachgeliefert wird.
  dungeon_feat_chest_closed: '/assets/dungeons/treasure_chest.png',
  dungeon_feat_chest_opened: '/assets/dungeons/treasure_chest.png',
  dungeon_feat_altar:        '/assets/dungeon_props/altar.png',
  dungeon_feat_brazier:      '/assets/dungeon_props/brazier.png',
  dungeon_feat_sarcophagus:  '/assets/dungeon_props/sarcophagus.png',
  dungeon_feat_torch:        '/assets/dungeon_props/wall_torch.png',
  // Trap-Sprite fehlt — Fallback-Rect im Renderer (rot, semi-transparent).
};
