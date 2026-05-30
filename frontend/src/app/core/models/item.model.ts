// Item-Modelle (Definitionen + Runtime-Instances aus dem Backend).

/** Item-Kategorien — entscheidet über Default-Gewicht & Ground-Scale. */
export type ItemCategory =
  | 'weapon'
  | 'armor'
  | 'jewelry'
  | 'consumable'
  | 'food'
  | 'magic'
  | 'tool'
  | 'resource';

/** Equipment-Slot-Keys. */
export type EquipSlot =
  | 'weapon'
  | 'helmet'
  | 'chestplate'
  | 'gloves'
  | 'shield'
  | 'boots'
  | 'ring'
  | 'amulet'
  | 'tool';

/** Qualitätsstufen (Backend-Vertrag). */
export type ItemQuality = 'rough' | 'normal' | 'fine' | 'masterwork' | 'legendary';

/** Pro-Sprite-Set Rarity-Stufen (semantisch identisch zu ItemQuality). */
export type ItemRarity = 'poor' | 'common' | 'rare' | 'very_rare' | 'legendary';

/** Eine Zeile in der ITEM-Tabelle. */
export interface ItemDef {
  /** Deutscher Anzeige-Name. */
  readonly name: string;
  /** Phaser-Texture-Key (Default-Sprite). */
  readonly sprite: string;
  /** Item-Kategorie. */
  readonly category: ItemCategory;
  /** Equipment-Slot (nur für equip-bare Items). */
  readonly slot?: EquipSlot;
  /** Asset-URL für DOM-Renderings (Inventar-Icons im HUD). */
  readonly path?: string;
}

/** Slot-Definition für das EQUIP_SLOTS-Array. */
export interface EquipSlotDef {
  readonly key: EquipSlot;
  readonly label: string;
}

/** Per-Item rolled stats (Welle 23 — Variance pro Instance). */
export interface RolledStats {
  readonly damage_min?: number;
  readonly damage_max?: number;
  readonly speed?: number;
  readonly crit?: number;
  readonly range?: number;
  readonly armor_pen?: number;
  readonly two_handed?: boolean;
  readonly cleave?: boolean;
  readonly defense?: number;
  readonly weight?: number;
  readonly block_chance?: number;
  readonly speed_bonus?: number;
  readonly crit_chance_bonus?: number;
}

/** Affix-Eintrag (Prefix/Suffix mit Stat-Boost). */
export interface ItemAffix {
  readonly name_part: string;
  readonly kind: 'prefix' | 'suffix';
  readonly tier: number;
  readonly stats: Readonly<Record<string, number>>;
}

/** Runtime-Item-Instanz, wie sie das Backend per WS sendet. */
export interface InventoryItem {
  readonly id: number;
  readonly kind: string;
  readonly quantity?: number;
  readonly quality?: ItemQuality;
  readonly equipped_slot?: EquipSlot | null;
  readonly affixes?: readonly ItemAffix[];
  readonly rolled_stats?: RolledStats;
  /** Backend-gerollter Cosmetic-Skin (Welle 25). */
  readonly cosmetic_skin?: string;
}

/** Ground-Item (auf der Karte droppender Loot). */
export interface GroundItem {
  readonly id: number;
  readonly kind: string;
  readonly quantity?: number;
  readonly quality?: ItemQuality;
  readonly x: number;
  readonly y: number;
}
