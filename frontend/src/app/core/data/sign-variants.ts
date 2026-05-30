// Welle 51 — Settlement-Schilder.
// Slug muss zu assets/props/settlement/signs/professional/manifest.json passen,
// Backend structures.py SIGN_SLUGS muss identisch sein.
// Portiert aus frontend/legacy/app.js Z. 479-518.
import type { SignVariant } from '../models/structure.model';

export const SIGN_VARIANTS: readonly SignVariant[] = [
  ['schmiede',         'Schmiede',          '⚒️'],
  ['gasthaus',         'Gasthaus',          '🍺'],
  ['wohnhaus',         'Wohnhaus',          '🏠'],
  ['baeckerei',        'Bäckerei',          '🍞'],
  ['marktstand',       'Marktstand',        '⚖️'],
  ['lagerhaus',        'Lagerhaus',         '📦'],
  ['apotheke_heiler',  'Apotheke / Heiler', '⚕️'],
  ['stall',            'Stall',             '🐴'],
  ['wache',            'Wache',             '🛡️'],
  ['kaserne',          'Kaserne',           '⚔️'],
  ['rathaus',          'Rathaus',           '👑'],
  ['bergwerk',         'Bergwerk',          '⛏️'],
  ['saegewerk',        'Sägewerk',          '🪚'],
  ['holzfaeller',      'Holzfäller',        '🪓'],
  ['bauernhof',        'Bauernhof',         '🌾'],
  ['muehle',           'Mühle',             '🌬️'],
  ['fischerhuette',    'Fischerhütte',      '🐟'],
  ['taverne_brauerei', 'Taverne / Brauerei','🍻'],
  ['schneiderei',      'Schneiderei',       '🧵'],
  ['gerberei',         'Gerberei',          '🦌'],
  // Welle 34b — vorübergehend raus: Emblem off-pattern, Asset-Rework folgt.
  // ['jaegerhuette',     'Jägerhütte',        '🏹'],
  // ['alchemie',         'Alchemie',          '⚗️'],
  // ['magierturm',       'Magierturm',        '🪄'],
  ['kapelle',          'Kapelle',           '⛪'],
  ['friedhof',         'Friedhof',          '🪦'],
  ['bibliothek',       'Bibliothek',        '📚'],
  ['schule',           'Schule',            '📝'],
  ['goldschmied',      'Goldschmied',       '💍'],
  ['waffenladen',      'Waffenladen',       '🗡️'],
  ['ruestungsschmied', 'Rüstungsschmied',   '🪖'],
  ['hafen',            'Hafen',             '⚓'],
  ['brunnen',          'Brunnen-Schild',    '⛲'],
  ['ritualplatz',      'Ritualplatz',       '🌀'],
  ['portalraum',       'Portalraum',        '🌌'],
  // Welle 34b — vorübergehend raus (Emblem off-pattern):
  // ['verzauberer',      'Verzauberer',       '✨'],
  ['drachenstall',     'Drachenstall',      '🐉'],
];
