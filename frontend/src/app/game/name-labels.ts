// NameLabels — Namens-Texte über Spieler- und NPC-Sprites (Issue 31.05 #5).
//
// Pro Frame in `sync(players, npcs, selfPlayerId)` aufgerufen. Wir halten
// einen Phaser.Text pro id; selbst-Player kriegt goldene Farbe + leichten
// Glow zur Selbst-Identifikation, andere Spieler hellblau, NPCs grau.
//
// Welche NPCs kriegen Labels:
//   • friendly (kind ohne creature_/overworld_-Prefix) mit name-Feld
//   • alle Spieler (`OnlinePlayer.name`)
//
// Hostile mobs absichtlich nicht — würde den Screen vollmüllen. Mob-Tooltip
// (H3.8) zeigt sie on-hover.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';
import type { NPC, OnlinePlayer } from '../core/models';

const LABEL_OFFSET_Y = -TILE_SIZE / 2 - 18;
const DEPTH_LABEL = 36; // über HP-Bar (35), unter UI-Overlays
const TEXT_STYLE_BASE: Phaser.Types.GameObjects.Text.TextStyle = {
  fontFamily: 'monospace',
  fontSize: '10px',
  stroke: '#000',
  strokeThickness: 3,
  align: 'center',
};
const COLOR_SELF = '#ffd75a';
const COLOR_OTHER = '#9dccff';
const COLOR_NPC = '#d4d4cc';

type LabelKind = 'self' | 'player' | 'npc';

export class NameLabels {
  private readonly scene: Phaser.Scene;
  private readonly byKey = new Map<string, Phaser.GameObjects.Text>();
  /** Welche Keys waren im letzten sync() aktiv — Rest wird entsorgt. */
  private readonly seenLastFrame = new Set<string>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * @param resolvePos Optionaler Resolver für die ECHTE Sprite-Pixel-Position
   *   einer Entität (self läuft per Pixel-Movement, andere interpoliert). Damit
   *   klebt das Label frame-genau am Sprite statt an der niederfrequenten
   *   Server-Tile-Position — behebt Nachlaufen + Springen. Liefert er nichts
   *   (kein Sprite), nutzen wir die Tile-Koordinate als Fallback.
   */
  sync(
    players: ReadonlyArray<OnlinePlayer>,
    npcs: ReadonlyArray<NPC>,
    selfPlayerId: string | undefined,
    resolvePos?: (kind: 'player' | 'npc', id: string | number)
      => { readonly x: number; readonly y: number } | undefined,
  ): void {
    this.seenLastFrame.clear();

    // Spieler
    for (const p of players) {
      const name = p.name ?? String(p.player_id);
      if (!name) continue;
      const key = `p:${p.player_id}`;
      const kind: LabelKind = selfPlayerId === String(p.player_id) ? 'self' : 'player';
      const pos = resolvePos?.('player', p.player_id);
      const px = pos ? pos.x : (p.x + 0.5) * TILE_SIZE;
      const py = (pos ? pos.y : (p.y + 0.5) * TILE_SIZE) + LABEL_OFFSET_Y;
      this.upsert(key, name, px, py, kind);
      this.seenLastFrame.add(key);
    }

    // Friendly NPCs (alle non-creature/overworld mit name-Feld)
    for (const n of npcs) {
      if (!n.name) continue;
      if (n.kind.startsWith('creature_') || n.kind.startsWith('overworld_')) continue;
      const key = `n:${n.id}`;
      const pos = resolvePos?.('npc', n.id);
      const px = pos ? pos.x : (n.x + 0.5) * TILE_SIZE;
      const py = (pos ? pos.y : (n.y + 0.5) * TILE_SIZE) + LABEL_OFFSET_Y;
      this.upsert(key, n.name, px, py, 'npc');
      this.seenLastFrame.add(key);
    }

    // Aufräumen — was im letzten Sync nicht mehr da war
    for (const key of [...this.byKey.keys()]) {
      if (!this.seenLastFrame.has(key)) {
        this.byKey.get(key)?.destroy();
        this.byKey.delete(key);
      }
    }
  }

  private upsert(key: string, text: string, px: number, py: number, kind: LabelKind): void {
    const color = kind === 'self' ? COLOR_SELF : kind === 'player' ? COLOR_OTHER : COLOR_NPC;
    let label = this.byKey.get(key);
    if (!label) {
      label = this.scene.add.text(px, py, text, { ...TEXT_STYLE_BASE, color });
      label.setOrigin(0.5, 1);
      label.setDepth(DEPTH_LABEL);
      this.byKey.set(key, label);
    } else {
      if (label.text !== text) label.setText(text);
      label.setPosition(px, py);
      if (label.style.color !== color) label.setColor(color);
    }
  }

  destroy(): void {
    for (const label of this.byKey.values()) label.destroy();
    this.byKey.clear();
  }
}
