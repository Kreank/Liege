// Equipment-Slots + Equipment-Sprite-Resolver-Map.
// Portiert aus frontend/legacy/app.js Z. 1709-1740.
import type { EquipSlotDef } from '../models/item.model';

export const EQUIP_SLOTS: readonly EquipSlotDef[] = [
  { key: 'weapon',     label: 'Waffe' },
  { key: 'helmet',     label: 'Helm' },
  { key: 'chestplate', label: 'Brustpanzer' },
  { key: 'gloves',     label: 'Handschuhe' },
  { key: 'shield',     label: 'Schild' },
  { key: 'boots',      label: 'Stiefel' },
  { key: 'ring',       label: 'Ring' },
  { key: 'amulet',     label: 'Amulett' },
  { key: 'tool',       label: 'Werkzeug' },
];

// ─── Equipment-Sprite-Resolver ─────────────────────────────────────────────
// Mapping: item-kind → Asset-Basename. Greatsword nutzt sword_2h, scythe axe_2h.
export const EQUIP_BASE: Readonly<Record<string, string>> = {
  sword:          'sword_1h',
  greatsword:     'sword_2h',
  axe:            'axe_1h',
  bow:            'bow_long',
  crossbow:       'crossbow',
  dagger:         'dagger',
  throwing_knife: 'dagger',
  mace:           'mace',
  spear:          'spear',
  staff:          'staff',
  wand:           'wand',
  scythe:         'axe_2h',
  helmet:         'helmet',
  chestplate:     'chestplate',
  shield:         'shield',
  boots:          'boots',
};
