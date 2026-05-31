// DayNightOverlay — Vollbild-Tint pro Tag/Nacht-Phase (H2.23).
//
// Backend liefert `time_update` / `time_tick` mit `phase: 'dawn' | 'day' |
// 'dusk' | 'night'` (siehe TimeSnapshot). Wir lesen das `time()`-Signal über
// die GameBridge pro Frame und tweenen einen Vollbild-Rectangle in der
// passenden Farbe ein:
//
//   • day      — kein Tint (alpha 0)
//   • dawn     — light-blue (#88aaff, alpha 0.08)  — "morning"
//   • dusk     — warm-orange (#ff8855, alpha 0.10) — "evening"
//   • night    — blau-violett (#2030aa, alpha 0.25)
//
// Smooth-Tween bei Phase-Wechsel (3 s) damit kein harter Snap entsteht.
//
// Render: das Rectangle hat `setScrollFactor(0)` (klebt am Viewport) und
// liegt zwischen NPCs (~20) und Disaster-Tint (~70). Disaster-Tint
// addiert sich darüber → bei Bloodmoon zur Nacht entsteht ein purpur-roter
// Mischton, was erwünscht ist.

import Phaser from 'phaser';

/** Phase-Tint-Definition. */
interface PhaseTint {
  /** RGB-Hex. */
  readonly color: number;
  /** Alpha 0..1. */
  readonly alpha: number;
}

const TINTS: Readonly<Record<string, PhaseTint>> = {
  day:   { color: 0xffffff, alpha: 0.0 },
  dawn:  { color: 0x88aaff, alpha: 0.08 },
  dusk:  { color: 0xff8855, alpha: 0.10 },
  night: { color: 0x2030aa, alpha: 0.25 },
};

/** Default für unbekannte/fehlende Phasen — wirkt wie "day" (kein Tint). */
const DEFAULT_TINT: PhaseTint = { color: 0xffffff, alpha: 0.0 };

/** Phase-Wechsel-Tween-Dauer (ms) — Aufgaben-Vorgabe: 3 s. */
const TRANSITION_MS = 3000;

/** Render-Depth: über Welt, unter Disaster-Tint (Sektion 14: DEPTH_TINT=70). */
const DEPTH_DAY_NIGHT = 45;

export class DayNightOverlay {
  private readonly scene: Phaser.Scene;
  private rect: Phaser.GameObjects.Rectangle | null = null;
  /** Aktuelle Phase (zum Diffen — nur bei Wechsel tweenen). */
  private currentPhase: string | null = null;
  /** Aktiver Color/Alpha-Tween (für Cancel bei schnell hintereinander
   *  folgenden Phase-Updates). */
  private tween: Phaser.Tweens.Tween | null = null;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Pro Frame aufrufen mit der aktuellen Phase (aus `state.time()?.phase`).
   * Idempotent — kein Tween wenn Phase gleich bleibt. Wenn die Phase
   * `undefined`/`null` ist, behandeln wir das wie "day" (kein Tint).
   */
  setPhase(phase: 'dawn' | 'day' | 'dusk' | 'night' | null | undefined): void {
    const normalized = phase ?? 'day';
    if (normalized === this.currentPhase) return;
    this.currentPhase = normalized;
    const tint = TINTS[normalized] ?? DEFAULT_TINT;
    this.applyTint(tint);
  }

  /** Räumt das Overlay ab (Scene-Shutdown). */
  destroy(): void {
    if (this.tween) {
      this.tween.stop();
      this.tween = null;
    }
    if (this.rect) {
      this.rect.destroy();
      this.rect = null;
    }
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private ensureRect(): Phaser.GameObjects.Rectangle {
    if (this.rect) return this.rect;
    const cam = this.scene.cameras.main;
    // Doppelt so groß wie der Viewport, damit kein Edge sichtbar wird bei
    // schnellem Kamera-Scroll (Resize-Listener passt zusätzlich an).
    const r = this.scene.add.rectangle(
      0, 0, cam.width, cam.height, 0xffffff, 0,
    );
    r.setOrigin(0, 0);
    r.setDepth(DEPTH_DAY_NIGHT);
    r.setScrollFactor(0);
    // Bei Window-Resize mitwachsen.
    this.scene.scale.on(Phaser.Scale.Events.RESIZE, () => {
      r.setSize(cam.width, cam.height);
    });
    this.rect = r;
    return r;
  }

  private applyTint(tint: PhaseTint): void {
    const rect = this.ensureRect();
    if (this.tween) {
      this.tween.stop();
      this.tween = null;
    }
    // Phaser-Rectangle: `fillColor` ist setbar, aber das Tween-Plugin
    // bietet keinen smoothen RGB-Tween out of the box. Wir nehmen einen
    // "Direkt-Color-Snap + Alpha-Tween"-Ansatz: Color sofort, Alpha smooth.
    rect.setFillStyle(tint.color, rect.alpha); // Color sofort
    this.tween = this.scene.tweens.add({
      targets: rect,
      alpha: tint.alpha,
      duration: TRANSITION_MS,
      ease: 'Sine.easeInOut',
      onComplete: () => {
        // Final: Fill-Style mit endgültigem Alpha setzen (Edge-Case,
        // falls Phaser den Alpha-Wert nicht synced).
        rect.setFillStyle(tint.color, tint.alpha);
        this.tween = null;
      },
    });
  }
}
