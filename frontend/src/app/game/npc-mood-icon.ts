// NpcMoodIcons — kleine Emoji-Icons über NPCs für deren Stimmung (H3.6).
//
// Backend feuert `npc_mood {npc_id, mood_value, mental_state}` aus dem
// `npc_mood`-Worker, sobald ein NPC den `mental_state` wechselt. Wir
// rendern pro betroffenem NPC ein kleines Emoji über dem Sprite:
//
//   • sad     → 😢
//   • fleeing → 😨
//   • berserk → 😡
//   • normal  → kein Icon (Default → unsichtbar)
//
// Begründung „kein Icon für normal": siehe ai_fragen.md H3.6 — sonst würden
// alle 100+ friendly NPCs in einer Stadt mit Emojis übersät.
//
// Lifecycle:
//   • `setMood(npcId, mentalState)` — registriert/aktualisiert das Icon.
//     Bei `normal` (oder unbekanntem State) wird das Icon entfernt.
//   • `syncPositions(npcs)` — pro Frame, damit das Icon dem Mob folgt.
//     NPCs, die nicht mehr im Snapshot sind, verlieren ihr Icon.
//   • `removeFor(npcId)` — bei `npc_died` aufräumen.
//   • `destroyAll()` — Scene-Shutdown.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Render-Depth: über NPCs, knapp unter Combat-FX und Quest-Markern. */
const DEPTH_MOOD = 52;
/** Vertikaler Offset vom NPC-Center (negativ = nach oben). */
const MOOD_OFFSET_Y = -TILE_SIZE / 2 - 6;

/** Mental-State → Emoji. `normal` fehlt absichtlich (kein Icon). */
const MOOD_EMOJI: Readonly<Record<string, string>> = {
  sad:     '😢',
  fleeing: '😨',
  berserk: '😡',
};

interface IconState {
  readonly text: Phaser.GameObjects.Text;
  /** Aktueller mental_state — Diff-Check bei wiederholten Updates. */
  state: string;
}

export class NpcMoodIcons {
  private readonly scene: Phaser.Scene;
  private readonly icons = new Map<number, IconState>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Mood-Update für einen NPC. Bei `normal` (oder unbekanntem State) wird
   * das Icon entfernt — wir zeigen nur abnormale Stimmungen.
   */
  setMood(npcId: number, mentalState: string): void {
    const emoji = MOOD_EMOJI[mentalState];
    if (!emoji) {
      // normal / unbekannt → Icon weg.
      this.removeFor(npcId);
      return;
    }
    let icon = this.icons.get(npcId);
    if (!icon) {
      const txt = this.scene.add.text(0, 0, emoji, {
        fontFamily: 'sans-serif',
        fontSize: '16px',
      });
      txt.setOrigin(0.5, 0.5);
      txt.setDepth(DEPTH_MOOD);
      icon = { text: txt, state: mentalState };
      this.icons.set(npcId, icon);
      return;
    }
    if (icon.state !== mentalState) {
      icon.text.setText(emoji);
      icon.state = mentalState;
    }
  }

  /** Pro Frame: Position dem aktuellen NPC-Snapshot anpassen + verwaiste
   *  Icons abräumen. */
  syncPositions(
    npcs: readonly { readonly id: number; readonly x: number; readonly y: number }[],
  ): void {
    if (this.icons.size === 0) return;
    const lookup = new Map<number, { x: number; y: number }>();
    for (const n of npcs) lookup.set(n.id, n);
    for (const [id, icon] of this.icons) {
      const npc = lookup.get(id);
      if (!npc) {
        icon.text.destroy();
        this.icons.delete(id);
        continue;
      }
      const cx = npc.x * TILE_SIZE + TILE_SIZE / 2;
      const cy = npc.y * TILE_SIZE + TILE_SIZE / 2 + MOOD_OFFSET_Y;
      icon.text.setPosition(cx, cy);
    }
  }

  /** NPC ist tot → Icon weg. */
  removeFor(npcId: number): void {
    const icon = this.icons.get(npcId);
    if (!icon) return;
    icon.text.destroy();
    this.icons.delete(npcId);
  }

  /** Scene-Shutdown. */
  destroyAll(): void {
    for (const icon of this.icons.values()) icon.text.destroy();
    this.icons.clear();
  }
}
