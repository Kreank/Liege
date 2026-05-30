// World-Polish + Biome-Ambient + Animal/Transport-Animations.
// Portiert aus frontend/legacy/app.js Z. 1749-1875.
// Die P2-Animal/Transport-Listen sind im Legacy 1:1 mit allen 4 Richtungen
// ausgeschrieben — wir erzeugen sie hier aus einem Generator, das Ergebnis ist
// bytegleich (selbe URLs, selbe frame-counts, selbe Richtungs-Reihenfolge).
import type {
  AnimalAnim,
  BiomeAmbientByTile,
  BiomeAmbientDef,
  TransportAnim,
  WorldPolishAnim,
} from '../models/animation.model';

// Welle 50 — World-Polish-Animations (192×192 Overlays, 12 FPS).
export const WORLD_POLISH_ANIMS: readonly WorldPolishAnim[] = [
  { key:'water_flowers',         frames:14, fps:12, looping:false, category:'farming'  },
  { key:'water_crop_tile',       frames:14, fps:12, looping:false, category:'farming'  },
  { key:'hoe_soil',              frames:12, fps:12, looping:false, category:'farming'  },
  { key:'sow_seeds',             frames:12, fps:12, looping:false, category:'farming'  },
  { key:'harvest_crop',          frames:12, fps:12, looping:false, category:'farming'  },
  { key:'crop_growth_sparkle',   frames:16, fps:12, looping:true,  category:'farming'  },
  { key:'speech_bubble_talk',    frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_trade',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_question',frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_alert',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'thought_bubble_work',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'mining_chip',           frames:10, fps:12, looping:false, category:'work'     },
  { key:'chop_wood',             frames:10, fps:12, looping:false, category:'work'     },
  { key:'build_hammer',          frames:10, fps:12, looping:false, category:'work'     },
  { key:'crafting_sparks',       frames:14, fps:12, looping:true,  category:'work'     },
  { key:'item_pickup_pop',       frames:10, fps:12, looping:false, category:'feedback' },
  { key:'loot_twinkle',          frames:14, fps:12, looping:true,  category:'feedback' },
  { key:'level_up_ring',         frames:16, fps:12, looping:true,  category:'feedback' },
  { key:'negative_mood_pulse',   frames:12, fps:12, looping:false, category:'feedback' },
  { key:'footstep_dust',         frames: 8, fps:12, looping:true,  category:'ambient'  },
  { key:'leaf_rustle',           frames:16, fps:12, looping:true,  category:'ambient'  },
  { key:'campfire_embers',       frames:16, fps:12, looping:true,  category:'ambient'  },
];

// Biome-Ambient-Overlays.
export const BIOME_AMBIENT_DEFS: readonly BiomeAmbientDef[] = [
  { id: 'desert_heat_haze',      frames: 12, ms:  75 },
  { id: 'desert_dust',           frames: 12, ms:  80 },
  { id: 'jungle_humidity_motes', frames: 12, ms:  90 },
  { id: 'jungle_leaf_drift',     frames: 12, ms: 110 },
  { id: 'swamp_mist',            frames: 12, ms: 105 },
  { id: 'volcanic_ash',          frames: 12, ms:  80 },
];

export const BIOME_AMBIENT_MS: Readonly<Record<string, number>> =
  Object.fromEntries(BIOME_AMBIENT_DEFS.map((d) => [d.id, d.ms]));

export const BIOME_AMBIENT_FRAMES: Readonly<Record<string, number>> =
  Object.fromEntries(BIOME_AMBIENT_DEFS.map((d) => [d.id, d.frames]));

// Tile-Biome → Ambient-Effekt + Alpha.
export const BIOME_AMBIENT_BY_TILE: Readonly<Record<number, BiomeAmbientByTile>> = {
  1: { id: 'desert_dust',           alpha: 0.16 },
  5: { id: 'desert_heat_haze',      alpha: 0.20 },
  6: { id: 'jungle_humidity_motes', alpha: 0.18 },
  7: { id: 'volcanic_ash',          alpha: 0.24 },
  9: { id: 'swamp_mist',            alpha: 0.22 },
};

// ─── P2 Animal-Animations (Asset-Drop 2026-05-27) ─────────────────────────
// Pro Animal × 4 Richtungen, gleiche walk_frames/idle_frames-Werte. Frame-
// Größen variieren pro animal. Wir generieren die List 1:1 aus dem Spec.
type AnimalSpec = readonly [animal: string, fw: number, fh: number];

const _P2_ANIMAL_SPECS: readonly AnimalSpec[] = [
  ['cow',          96, 96],
  ['sheep',        64, 64],
  ['goat',         64, 64],
  ['pig',          64, 64],
  ['horse',        96, 96],
  ['farm_dog',     96, 96],
  // Welle 24 — Poultry + Wildlife
  ['chicken_hen',  64, 64],
  ['rooster',      64, 64],
  ['duck',         64, 64],
  ['goose',        64, 64],
  ['fox',          96, 96],
  ['rabbit',       64, 64],
];

const _DIRECTIONS = ['south', 'east', 'north', 'west'] as const;

function _buildAnimalAnims(): readonly AnimalAnim[] {
  const out: AnimalAnim[] = [];
  for (const [animal, fw, fh] of _P2_ANIMAL_SPECS) {
    for (const direction of _DIRECTIONS) {
      out.push({
        animal,
        direction,
        walk_sheet: `/assets/animations/animals/${animal}/${direction}/walk_sheet.png`,
        idle_sheet: `/assets/animations/animals/${animal}/${direction}/idle_sheet.png`,
        walk_frames: 4,
        idle_frames: 2,
        walk_fw: fw,
        walk_fh: fh,
        idle_fw: fw,
        idle_fh: fh,
      });
    }
  }
  return out;
}

export const WORLD_DETAIL_P2_ANIMAL_ANIMS: readonly AnimalAnim[] = _buildAnimalAnims();

// ─── P2 Transport-Animations ──────────────────────────────────────────────
type TransportSpec = readonly [vehicle: string, fw: number, fh: number];

const _P2_TRANSPORT_SPECS: readonly TransportSpec[] = [
  ['handcart_empty',       128, 128],
  ['farm_cart_hay',        128, 128],
  ['horse_cart_single',    160, 160],
  ['market_wagon_covered', 160, 160],
];

function _buildTransportAnims(): readonly TransportAnim[] {
  const out: TransportAnim[] = [];
  for (const [vehicle, fw, fh] of _P2_TRANSPORT_SPECS) {
    for (const direction of _DIRECTIONS) {
      out.push({
        vehicle,
        direction,
        roll_sheet: `/assets/animations/transport/${vehicle}/${direction}/roll_sheet.png`,
        idle_sheet: `/assets/animations/transport/${vehicle}/${direction}/idle_sheet.png`,
        roll_frames: 4,
        idle_frames: 2,
        roll_fw: fw,
        roll_fh: fh,
        idle_fw: fw,
        idle_fh: fh,
      });
    }
  }
  return out;
}

export const WORLD_DETAIL_P2_TRANSPORT_ANIMS: readonly TransportAnim[] = _buildTransportAnims();
