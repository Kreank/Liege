// NPC-/Creature-Modelle.

/** Visualisierungs-Eintrag pro NPC-Kind. */
export interface NpcSprite {
  /** Phaser-Texture-Key. */
  readonly sprite: string;
  /** RGB-Tint (0xffffff = no tint). */
  readonly tint: number;
  /** Deutscher Anzeige-Name. */
  readonly label: string;
}

/** Preset-Walk-Config für Player-Sprites (anti-Flicker, Welle 2026-05-29). */
export interface PresetWalkConfig {
  readonly srcDir: 'left' | 'right';
  readonly baseFacing: 'left' | 'right';
  readonly flip2: boolean;
}

/** NPC-Snapshot wie ihn das Backend per WS sendet. */
export interface NPC {
  readonly id: number;
  readonly kind: string;
  readonly x: number;
  readonly y: number;
  readonly hp?: number;
  readonly max_hp?: number;
  readonly hostile?: boolean;
  readonly name?: string;
  /** Optionaler Sprite-Variant-Override (z. B. bandit_axe). */
  readonly sprite_variant?: string;
}
