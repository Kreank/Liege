// Affix-Stat-Labels (deutsche Übersetzung der Affix-Stat-Keys).
// Portiert aus frontend/legacy/app.js Z. 1126-1145.
import type { AffixStatLabel } from '../models/affix.model';

export const AFFIX_STAT_LABELS: Readonly<Record<string, AffixStatLabel>> = {
  damage_pct:           { de: 'Schaden',         suffix: '%' },
  speed_pct:            { de: 'Angriffsgeschw.', suffix: '%' },
  crit_chance_pct:      { de: 'Krit-Chance',     suffix: '%' },
  crit_damage_pct:      { de: 'Krit-Schaden',    suffix: '%' },
  defense_flat:         { de: 'Defense',         suffix: '' },
  hp_flat:              { de: 'HP',              suffix: '' },
  mana_flat:            { de: 'Mana',            suffix: '' },
  fire_damage:          { de: '🔥 Feuerschaden', suffix: '' },
  ice_damage:           { de: '❄️ Eisschaden',   suffix: '' },
  lightning_damage:     { de: '⚡ Blitzschaden', suffix: '' },
  necrotic_damage:      { de: '☠️ Nekrotisch',   suffix: '' },
  lifesteal_pct:        { de: 'Lebenssaug',      suffix: '%' },
  armor_pen_pct:        { de: 'Rüstungsdurchdr.',suffix: '%' },
  regen_pct:            { de: 'Regeneration',    suffix: '%' },
  magic_resist_pct:     { de: 'Magieresistenz',  suffix: '%' },
  fire_resist_pct:      { de: '🔥 Feuerresist',  suffix: '%' },
  ice_resist_pct:       { de: '❄️ Eisresist',    suffix: '%' },
  lightning_resist_pct: { de: '⚡ Blitzresist',  suffix: '%' },
};
