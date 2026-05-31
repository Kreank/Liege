// MobHpBars — kleine HP-Bars über NPC-Sprites (H2.2).
//
// Backend liefert mit jedem `npc_damaged`-Frame die aktuellen `hp` und
// `max_hp`-Werte. Pro NPC zeigen wir eine schmale Bar 12 px über dem
// Sprite-Center, die nach kurzer Idle-Zeit ausblendet:
//   • Vollbar (hp >= max_hp): unsichtbar.
//   • hp / max_hp > 0.5: grün.
//   • hp / max_hp > 0.25: gelb.
//   • sonst: rot.
//
// Implementation: pro NPC ein `Phaser.GameObjects.Graphics`. Position wird
// pro Frame in `update()` aus dem aktuellen `npcsVisible()`-Snapshot
// gepatcht (die Sprite-Position selbst tween wir nicht — der Wert kommt
// direkt vom State-Sync, das passt zum Sprite-Tween, weil beide aus dem
// gleichen Frame-Source gespeist werden).
//
// Lifecycle:
//   • `noteDamage({npc_id, hp, max_hp})` — registriert/aktualisiert die
//     Bar; auto-fade nach FADE_AFTER_MS.
//   • `removeFor(npc_id)` — bei `npc_died` aufräumen.
//   • `syncPositions(npcs)` — pro Frame, damit die Bar dem Mob folgt.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Bar-Geometrie (Pixel). */
const BAR_W = 28;
const BAR_H = 4;
/** Vertikaler Offset vom Tile-Center (negativ = nach oben). */
const BAR_OFFSET_Y = -TILE_SIZE / 2 - 8;
/** Auto-Fade-Trigger nach letzter Hit-Update (ms). */
const FADE_AFTER_MS = 4000;
/** Fade-Out-Dauer (ms). */
const FADE_DURATION_MS = 400;
/** Render-Depth: über NPC-Sprite (DEPTH.NPCS = 20), unter Player (DEPTH.ME = 40). */
const DEPTH_HP_BAR = 35;

interface BarState {
  readonly graphics: Phaser.GameObjects.Graphics;
  /** Letzter Hit-Zeitpunkt (ms wall-clock). */
  lastUpdateMs: number;
  /** Aktueller HP-Ratio 0..1 (für Re-Draw bei Position-Sync). */
  ratio: number;
  /** Fade-Out-Tween (falls bereits gestartet) — damit wir ihn bei
   *  erneutem Hit canceln können. */
  fadeTween: Phaser.Tweens.Tween | null;
}

export class MobHpBars {
  private readonly scene: Phaser.Scene;
  /** Per npc_id → bar state. */
  private readonly bars = new Map<number, BarState>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Update auf Damage-Event. Erzeugt die Bar wenn nötig, setzt Ratio + Farbe.
   * Bei hp >= max_hp wird die Bar entfernt (Full = keine Anzeige laut Aufgabe).
   */
  noteDamage(npcId: number, hp: number, maxHp: number, x: number, y: number): void {
    if (maxHp <= 0) return;
    const ratio = Math.max(0, Math.min(1, hp / maxHp));
    if (ratio >= 1) {
      // NPC ist wieder voll — Bar entfernen, falls vorhanden.
      this.removeFor(npcId);
      return;
    }
    let bar = this.bars.get(npcId);
    if (!bar) {
      const g = this.scene.add.graphics();
      g.setDepth(DEPTH_HP_BAR);
      bar = { graphics: g, lastUpdateMs: 0, ratio, fadeTween: null };
      this.bars.set(npcId, bar);
    }
    // Falls ein Fade läuft: canceln + alpha resetten.
    if (bar.fadeTween) {
      bar.fadeTween.stop();
      bar.fadeTween = null;
    }
    bar.graphics.setAlpha(1);
    bar.ratio = ratio;
    bar.lastUpdateMs = Date.now();
    this.drawBar(bar, x, y);
  }

  /**
   * Pro Frame: Bar-Positionen am aktuellen Sprite/Tile festmachen + Auto-
   * Fade triggern. NPC-Liste kommt vom WorldScene-Caller (er hat sie eh
   * gelesen für den Pool-Sync).
   */
  syncPositions(npcs: readonly { readonly id: number; readonly x: number; readonly y: number; readonly hp?: number; readonly max_hp?: number }[]): void {
    if (this.bars.size === 0) return;
    const now = Date.now();
    // Map id→npc für O(1)-Lookup.
    const lookup = new Map<number, { x: number; y: number; hp?: number; max_hp?: number }>();
    for (const n of npcs) lookup.set(n.id, n);

    for (const [id, bar] of this.bars) {
      const npc = lookup.get(id);
      if (!npc) {
        // NPC nicht mehr sichtbar (z.B. tot oder out-of-range) — Bar entfernen.
        bar.graphics.destroy();
        this.bars.delete(id);
        continue;
      }
      // Falls aktueller Snapshot HP-Info hat: ratio nachpatchen (falls der
      // Mob ohne `npc_damaged`-Frame healt, z. B. Resting). Vermeidet Stale-Bars.
      if (typeof npc.hp === 'number' && typeof npc.max_hp === 'number' && npc.max_hp > 0) {
        const ratio = Math.max(0, Math.min(1, npc.hp / npc.max_hp));
        if (ratio >= 1) {
          bar.graphics.destroy();
          this.bars.delete(id);
          continue;
        }
        bar.ratio = ratio;
      }
      this.drawBar(bar, npc.x, npc.y);
      // Auto-Fade nach Idle-Zeit.
      if (!bar.fadeTween && now - bar.lastUpdateMs > FADE_AFTER_MS) {
        bar.fadeTween = this.scene.tweens.add({
          targets: bar.graphics,
          alpha: 0,
          duration: FADE_DURATION_MS,
          ease: 'Cubic.easeOut',
          onComplete: () => {
            // Final entfernen.
            bar.graphics.destroy();
            this.bars.delete(id);
          },
        });
      }
    }
  }

  /** NPC ist gestorben → Bar weg. */
  removeFor(npcId: number): void {
    const bar = this.bars.get(npcId);
    if (!bar) return;
    if (bar.fadeTween) bar.fadeTween.stop();
    bar.graphics.destroy();
    this.bars.delete(npcId);
  }

  /** Alles wegräumen (Scene-Shutdown). */
  destroyAll(): void {
    for (const bar of this.bars.values()) {
      if (bar.fadeTween) bar.fadeTween.stop();
      bar.graphics.destroy();
    }
    this.bars.clear();
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private drawBar(bar: BarState, tileX: number, tileY: number): void {
    const cx = tileX * TILE_SIZE + TILE_SIZE / 2;
    const cy = tileY * TILE_SIZE + TILE_SIZE / 2;
    const g = bar.graphics;
    g.clear();
    // Hintergrund (dunkles Rot, halb-transparent).
    g.fillStyle(0x220000, 0.75);
    g.fillRect(cx - BAR_W / 2, cy + BAR_OFFSET_Y, BAR_W, BAR_H);
    // Vordergrund (Farbe abhängig vom Ratio).
    const color = bar.ratio > 0.5 ? 0x44dd44 : bar.ratio > 0.25 ? 0xeecc22 : 0xee3322;
    g.fillStyle(color, 1);
    g.fillRect(cx - BAR_W / 2, cy + BAR_OFFSET_Y, BAR_W * bar.ratio, BAR_H);
    // Outline.
    g.lineStyle(1, 0x000000, 0.85);
    g.strokeRect(cx - BAR_W / 2, cy + BAR_OFFSET_Y, BAR_W, BAR_H);
  }
}
