// Structure-Modell. Spiegelt die STRUCTURE-Tabelle aus dem Legacy-Code.

/** Ein einzelner Bau-/Welt-Object-Typ. */
export interface StructureDef {
  /** Hotkey im Bau-Menü, leer wenn kein Shortcut belegt ist. */
  readonly key: string;
  /** Deutscher Anzeige-Name (UI-Tooltip). */
  readonly name: string;
  /** Emoji-Icon für die Bau-Menü-Buttons. */
  readonly icon: string;
  /** True, wenn die Struktur den Tile blockiert (für Pathing-Prediction). */
  readonly blocking: boolean;
  /** Phaser-Texture-Key. */
  readonly sprite: string;
  /** Struktur hat einen Material-Selector (Stein/Holz/Stroh). */
  readonly hasMaterial?: boolean;
  /** True, wenn der Typ NICHT im Bau-Menü auftaucht (nur Render-State). */
  readonly notBuildable?: boolean;
}

/** Welt-Deko, die kein Bau-Eintrag ist, aber dennoch harvest-bar. */
export interface NaturalStructureKind {
  readonly kind: string;
}

/** Footprint = [Breite, Höhe] in Tiles, Default [1,1]. */
export type StructureFootprint = readonly [number, number];

/** Top-Level Bau-Kategorie (RimWorld-Stil Tabs im Menü). */
export interface BuildCategory {
  readonly id: string;
  readonly icon: string;
  readonly label: string;
  readonly types?: readonly string[];
  readonly subcategories?: readonly BuildSubcategory[];
}

export interface BuildSubcategory {
  readonly id: string;
  readonly icon: string;
  readonly label: string;
  readonly types: readonly string[];
}

/** Eintrag aus SIGN_VARIANTS — slug, deutsches Label, Emblem-Emoji. */
export type SignVariant = readonly [slug: string, label: string, icon: string];
