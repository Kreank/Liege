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
  /** Tier (1-5) — Schwierigkeits-/Größen-Indikator. Backend setzt das in
   *  `npcs._row_to_dict` (Welle 25). */
  readonly tier?: number;
  /** Level (creature_stats) — falls Backend liefert. Future-proof Feld;
   *  aktuell rein anzeigend im Mob-Tooltip (H3.8). */
  readonly level?: number;
  /** Power-Budget-Skalierung für Gruppen: wenn != null, ist der Mob für eine
   *  Gruppe der angegebenen Größe „aufgepowert" (HP/Damage-Boost). Future-
   *  proof — Backend liefert das aktuell noch nicht (siehe H3.8 Spec), der
   *  Tooltip zeigt die Info aber sobald sie kommt. */
  readonly scaled_for_party_size?: number;
  /** Prozentualer HP-Bonus durch Gruppen-Skalierung (z. B. 25 → +25 % HP).
   *  Future-proof analog zu `scaled_for_party_size`. */
  readonly scaled_hp_pct?: number;
}
