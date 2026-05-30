// Wall-Auto-Tiling — Bitmask-Lookup fuer Wand-/Zaun-Varianten.
//
// Welle render-fix (2026-05-31):
// Das Backend liefert Wand-Strukturen als `{ type: 'wall', material: 'stone'|'wood'|'straw', ... }`
// bzw. Zaeune als `{ type: 'fence', ... }`. Der Renderer (WorldScene) hat bisher
// nur den generischen `wall.png` / `fence_straight_ns.png` angezeigt — ohne
// Ausrichtung zu den Nachbarn. WALL_MASK_TO_VARIANT (in core/data/structures.ts)
// ist seit Welle 11 definiert, wurde aber vom Renderer ignoriert.
//
// Dieser Service berechnet die 4-Nachbarn-Bitmask (N=1 E=2 S=4 W=8) fuer ein
// gegebenes Tile und mapped es ueber WALL_MASK_TO_VARIANT auf eine Variante
// (z. B. `corner_ne`). Zusammen mit der Family (`wall_stone` / `wall_wood` /
// `wall_straw` / `fence`) ergibt sich der Sprite-Key (`wall_stone_corner_ne`),
// der in STRUCTURE_SPRITES eingetragen ist und vom AssetLoader geladen wird.

import type { Structure } from '../core/models/chunk.model';
import { WALL_MASK_TO_VARIANT } from '../core/data/structures';

/** Family-IDs die das Auto-Tiling unterstuetzen. */
export type WallFamily = 'wall_stone' | 'wall_wood' | 'wall_straw' | 'fence';

/**
 * Mapped einen Strukturtype + Material auf eine Family.
 * Beispiele:
 *   ('wall', 'stone') -> 'wall_stone'
 *   ('wall', 'wood')  -> 'wall_wood'
 *   ('fence', null)   -> 'fence'
 *   ('chest', ...)    -> null  (kein Wall/Fence)
 */
export function familyOf(type: string, material: string | undefined | null): WallFamily | null {
  if (type === 'fence') return 'fence';
  if (type === 'wall') {
    const mat = material ?? 'stone';
    if (mat === 'stone' || mat === 'wood' || mat === 'straw') {
      return `wall_${mat}` as WallFamily;
    }
    return 'wall_stone';
  }
  return null;
}

/** Pruefkriterium fuer "gleiche Family am Nachbartile" (Auto-Connect-Logik). */
function neighborMatches(neighbor: Structure | null, family: WallFamily): boolean {
  if (!neighbor) return false;
  const nFamily = familyOf(neighbor.type, neighbor.material ?? null);
  return nFamily === family;
}

/**
 * Berechnet die 4-Nachbarn-Bitmask fuer ein Wall-/Fence-Tile.
 * Bits: N=1, E=2, S=4, W=8 (Set wenn dort ein passendes Family-Mitglied liegt).
 * `lookup(x, y)` muss die Struktur am Tile (oder null) zurueckliefern.
 */
export function wallMaskFor(
  x: number,
  y: number,
  lookup: (x: number, y: number) => Structure | null,
  family: WallFamily,
): number {
  let mask = 0;
  if (neighborMatches(lookup(x, y - 1), family)) mask |= 1; // N
  if (neighborMatches(lookup(x + 1, y), family)) mask |= 2; // E
  if (neighborMatches(lookup(x, y + 1), family)) mask |= 4; // S
  if (neighborMatches(lookup(x - 1, y), family)) mask |= 8; // W
  return mask;
}

/**
 * Mapped (family, mask) auf den vollstaendigen STRUCTURE_SPRITES-Schluessel.
 * Beispiel: ('wall_stone', 7) -> 'wall_stone_straight_ns' (lookup ueber
 * WALL_MASK_TO_VARIANT). Fallback wenn die Mask nicht im Lookup ist:
 * `<family>_straight_ns`.
 */
export function wallSpriteKeyFor(family: WallFamily, mask: number): string {
  const variant = WALL_MASK_TO_VARIANT[mask] ?? 'straight_ns';
  return `${family}_${variant}`;
}

/**
 * Baut eine schnelle (x,y)->Structure Lookup-Map aus einer Strukturliste.
 * O(N) zum Bauen, O(1) zum Lookup. Bei <500 sichtbaren Strukturen pro Frame
 * voellig unkritisch.
 */
export function buildStructureLookup(
  structures: readonly Structure[],
): (x: number, y: number) => Structure | null {
  const map = new Map<string, Structure>();
  for (const s of structures) {
    map.set(`${s.x},${s.y}`, s);
  }
  return (x, y) => map.get(`${x},${y}`) ?? null;
}
