// NpcSpeechBubbles — kleine Sprechblasen über NPCs (H2.11).
//
// Backend sendet `npc_speech {npc_id, text, delay_ms?}` aus dem
// `npc_chatter`-Worker (Stadt-Chatter, 2er/3er-Konversationen).
// Pro NPC zeigen wir eine kleine weiß-graue Bubble mit dem Text 8 Sekunden
// lang an, fade-out über 400 ms. Max 1 Bubble pro NPC — neue ersetzen alte
// (Konversations-Updates kommen sequenziell).
//
// Position: über dem Sprite-Center, dynamisch über `syncPositions()` an die
// aktuelle NPC-Position gepatcht.
//
// Implementation:
//   • Container pro Bubble: Background-Rectangle + Text. Container vereinfacht
//     gemeinsame Movement + Fade.
//   • Text-Wrap bei ~140 px Breite (~14-18 Zeichen, abhängig von Wort-Länge).

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Render-Depth: über NPCs, unter Combat-FX. */
const DEPTH_BUBBLE = 50;
/** Sichtbar-Dauer (ms) — Aufgaben-Vorgabe: 8 s. */
const VISIBLE_DURATION_MS = 8000;
/** Fade-Out-Dauer. */
const FADE_OUT_MS = 400;
/** Bubble-Layout. */
const BUBBLE_PADDING_X = 6;
const BUBBLE_PADDING_Y = 4;
const BUBBLE_MAX_WIDTH = 140;
const BUBBLE_FONT_SIZE = '12px';
const BUBBLE_OFFSET_Y = -TILE_SIZE / 2 - 22;

interface BubbleState {
  readonly container: Phaser.GameObjects.Container;
  /** Wann (ms) die Bubble entfernt wird (für Cleanup-Pruning). */
  expiresAt: number;
  /** Aktiver Fade-Out-Tween (damit wir ihn bei Replace stoppen können). */
  fadeTween: Phaser.Tweens.Tween | null;
  /** Auto-Cleanup-Timer (damit Replace ihn cancelt). */
  timer: Phaser.Time.TimerEvent | null;
}

export class NpcSpeechBubbles {
  private readonly scene: Phaser.Scene;
  private readonly bubbles = new Map<number, BubbleState>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Neue Bubble (oder Ersatz). Backend kann `delay_ms` mitschicken (für
   * sequenzielle Conversation-Lines); wir respektieren das per
   * `scene.time.delayedCall`. Wenn die NPC zwischendurch despawnt, würde
   * die Bubble trotzdem spawnen (Text bezieht sich auf NPC-Id, nicht auf
   * Sprite) — der nächste `syncPositions`-Tick räumt sie dann auf.
   */
  show(npcId: number, text: string, delayMs = 0): void {
    if (!text) return;
    if (delayMs > 0) {
      this.scene.time.delayedCall(delayMs, () => this.spawnNow(npcId, text));
      return;
    }
    this.spawnNow(npcId, text);
  }

  /** Pro Frame: Bubble-Position dem NPC anpassen. */
  syncPositions(npcs: readonly { readonly id: number; readonly x: number; readonly y: number }[]): void {
    if (this.bubbles.size === 0) return;
    const lookup = new Map<number, { x: number; y: number }>();
    for (const n of npcs) lookup.set(n.id, n);
    for (const [id, bubble] of this.bubbles) {
      const npc = lookup.get(id);
      if (!npc) {
        // NPC weg → Bubble weg.
        this.dispose(id);
        continue;
      }
      const cx = npc.x * TILE_SIZE + TILE_SIZE / 2;
      const cy = npc.y * TILE_SIZE + TILE_SIZE / 2 + BUBBLE_OFFSET_Y;
      bubble.container.setPosition(cx, cy);
    }
  }

  /** NPC ist tot → Bubble weg. */
  removeFor(npcId: number): void {
    this.dispose(npcId);
  }

  /** Alles weg (Scene-Shutdown). */
  destroyAll(): void {
    for (const id of Array.from(this.bubbles.keys())) {
      this.dispose(id);
    }
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private spawnNow(npcId: number, text: string): void {
    // Falls bereits eine Bubble läuft: ersetzen (neueste gewinnt).
    this.dispose(npcId);

    const container = this.scene.add.container(0, 0);
    container.setDepth(DEPTH_BUBBLE);

    const txt = this.scene.add.text(0, 0, text, {
      fontFamily: 'Arial, sans-serif',
      fontSize: BUBBLE_FONT_SIZE,
      color: '#101018',
      wordWrap: { width: BUBBLE_MAX_WIDTH, useAdvancedWrap: true },
    });
    txt.setOrigin(0.5, 1);

    const w = txt.width + BUBBLE_PADDING_X * 2;
    const h = txt.height + BUBBLE_PADDING_Y * 2;

    const bg = this.scene.add.rectangle(0, -h / 2, w, h, 0xf2f0e8, 0.95);
    bg.setStrokeStyle(1, 0x404040, 0.9);
    bg.setOrigin(0.5, 0.5);

    // Pfeil unter der Bubble (kleines Dreieck).
    const tail = this.scene.add.triangle(0, 0, -5, -2, 5, -2, 0, 6, 0xf2f0e8, 0.95);
    tail.setStrokeStyle(1, 0x404040, 0.9);

    container.add([bg, txt, tail]);
    // Text-Origin oben: 0.5,1 → text.y = 0 setzt baseline auf container-origin;
    // wir verschieben den Text in die Bubble (vertikal zentriert).
    txt.setY(-BUBBLE_PADDING_Y);

    const state: BubbleState = {
      container,
      expiresAt: Date.now() + VISIBLE_DURATION_MS,
      fadeTween: null,
      timer: null,
    };
    state.timer = this.scene.time.delayedCall(VISIBLE_DURATION_MS - FADE_OUT_MS, () => {
      state.fadeTween = this.scene.tweens.add({
        targets: container,
        alpha: 0,
        duration: FADE_OUT_MS,
        ease: 'Cubic.easeOut',
        onComplete: () => {
          container.destroy(true);
          this.bubbles.delete(npcId);
        },
      });
    });
    this.bubbles.set(npcId, state);
  }

  private dispose(npcId: number): void {
    const bubble = this.bubbles.get(npcId);
    if (!bubble) return;
    if (bubble.fadeTween) bubble.fadeTween.stop();
    if (bubble.timer) bubble.timer.remove();
    bubble.container.destroy(true);
    this.bubbles.delete(npcId);
  }
}
