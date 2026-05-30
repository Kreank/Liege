// Animations-Modelle für World-Polish / Biome-Ambient / Animal- & Transport-Sheets.

/** World-Polish-Anim (Workflow-/Feedback-Overlays). */
export interface WorldPolishAnim {
  readonly key: string;
  readonly frames: number;
  readonly fps: number;
  readonly looping: boolean;
  readonly category: 'farming' | 'social' | 'work' | 'feedback' | 'ambient';
}

/** Biome-Ambient-Overlay-Definition. */
export interface BiomeAmbientDef {
  readonly id: string;
  readonly frames: number;
  readonly ms: number;
}

/** Biome-Ambient-Effekt pro Tile-ID (mit Alpha-Override). */
export interface BiomeAmbientByTile {
  readonly id: string;
  readonly alpha: number;
}

/** Tier-Animation-Sheet (P2-Asset-Drop). */
export interface AnimalAnim {
  readonly animal: string;
  readonly direction: 'south' | 'east' | 'north' | 'west';
  readonly walk_sheet: string;
  readonly idle_sheet: string;
  readonly walk_frames: number;
  readonly idle_frames: number;
  readonly walk_fw: number;
  readonly walk_fh: number;
  readonly idle_fw: number;
  readonly idle_fh: number;
}

/** Transport-Wagen-Sheet (P2-Asset-Drop). */
export interface TransportAnim {
  readonly vehicle: string;
  readonly direction: 'south' | 'east' | 'north' | 'west';
  readonly roll_sheet: string;
  readonly idle_sheet: string;
  readonly roll_frames: number;
  readonly idle_frames: number;
  readonly roll_fw: number;
  readonly roll_fh: number;
  readonly idle_fw: number;
  readonly idle_fh: number;
}
