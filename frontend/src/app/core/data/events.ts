// Event-Icons + CSS-Klassen pro Tier.
// Portiert aus frontend/legacy/app.js Z. 939-962.

/** Event-Tiers + Legacy-Kinds (DB-Bestand). */
export type EventKind =
  | 'atmosphere' | 'encounter' | 'catastrophe' | 'boss' | 'cataclysm'
  | 'weather' | 'creature' | 'discovery' | 'faction' | 'natural' | 'rumor';

export const EVENT_ICON: Readonly<Record<EventKind, string>> = {
  // Welle 20: Tiered Event-System — Icon pro Tier
  atmosphere:  '🌫',
  encounter:   '🌿',
  catastrophe: '🔥',
  boss:        '💀',
  cataclysm:   '🌑',
  // Legacy kinds (für alte Chronik-Einträge in der DB)
  weather:   '☁️',
  creature:  '🐉',
  discovery: '✨',
  faction:   '⚔️',
  natural:   '🌍',
  rumor:     '💬',
};

/** Tier → CSS-Klasse für visuelle Hervorhebung in der Chronik. */
export const TIER_CLASS: Readonly<
  Record<'atmosphere' | 'encounter' | 'catastrophe' | 'boss' | 'cataclysm', string>
> = {
  atmosphere:  'ev-tier-atmosphere',
  encounter:   'ev-tier-encounter',
  catastrophe: 'ev-tier-catastrophe',
  boss:        'ev-tier-boss',
  cataclysm:   'ev-tier-cataclysm',
};
