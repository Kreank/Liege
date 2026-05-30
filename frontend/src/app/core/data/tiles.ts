// Datentabelle TILE — portiert aus frontend/legacy/app.js Z. 455-472.
// IDs und Farben sind eingefroren (Backend kennt sie als numerische Tile-IDs).
import type { TileDef, TileKey } from '../models/tile.model';

export const TILE: Record<TileKey, TileDef> = {
  WATER:    { id: 0, name: 'Wasser',    sprite: 'tile_water',    miniColor: '#1a4a7a' },
  SAND:     { id: 1, name: 'Strand',    sprite: 'tile_sand',     miniColor: '#c8a85a' },
  GRASS:    { id: 2, name: 'Grasland',  sprite: 'tile_grass',    miniColor: '#3d7a3a' },
  FOREST:   { id: 3, name: 'Wald',      sprite: 'tile_forest',   miniColor: '#1a4a1a' },
  MOUNTAIN: { id: 4, name: 'Gebirge',   sprite: 'tile_mountain', miniColor: '#7a6a5a' },
  DESERT:   { id: 5, name: 'Wüste',     sprite: 'tile_desert',   miniColor: '#d4a865' },
  JUNGLE:   { id: 6, name: 'Dschungel', sprite: 'tile_jungle',   miniColor: '#1f5f1f' },
  LAVA:     { id: 7, name: 'Lava',      sprite: 'tile_lava',     miniColor: '#c83820' },
  SNOW:     { id: 8, name: 'Schnee',    sprite: 'tile_snow',     miniColor: '#e8f0f8' },
  SWAMP:    { id: 9, name: 'Sumpf',     sprite: 'tile_swamp',    miniColor: '#4a5a3a' },
};

/** ID → TileDef lookup, parallel zu TILE_BY_ID im Legacy. */
export const TILE_BY_ID: Record<number, TileDef> = Object.fromEntries(
  Object.values(TILE).map((t) => [t.id, t])
);

export const TILE_SIZE = 64;
export const CHUNK_SIZE = 32;

/** IDs die nicht walkbar sind — Frontend-Prediction (Wasser, Berg, Lava). */
export const NON_WALKABLE_TILES: ReadonlySet<number> = new Set([0, 4, 7]);
