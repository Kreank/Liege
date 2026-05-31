// MobHoverController — H3.8: Mob-Tooltip bei Pointer-Hover (Welle H3-C).
//
// Aus world-scene.ts in eine eigene Datei extrahiert, um Merge-Konflikte
// mit den vielen anderen WorldScene-Erweiterungen (Subagent A/B/C/D) zu
// minimieren. Die Scene ruft im `create()` exakt einmal `attach()` auf —
// danach läuft alles autonom über Phaser-Events und Angular-Signals.
//
// Strategie:
//   • Wir registrieren EINEN Pointer-Move-Listener auf der Scene und
//     berechnen aus dem Pointer die Tile-Koord. Statt jeden NPC-Sprite
//     einzeln auf `setInteractive` zu setzen (würde mit dem Tile-Click-
//     Routing kollidieren), matchen wir gegen den `npcsVisible`-Signal-
//     Snapshot.
//   • O(N) pro Move-Event ist akzeptabel — typisch <50 NPCs auf dem
//     Bildschirm; der Lookup ist ein simpler `.find()`.
//   • Bildschirm-Koord (pointer.x/y) für den Tooltip-Anchor, nicht
//     Welt-Koord — der Tooltip lebt im DOM-Overlay (MobTooltipComponent),
//     nicht in Phaser.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';
import type { GameBridgeService } from '../core/services/game-bridge.service';
import type { TooltipService } from '../core/services/tooltip.service';

export class MobHoverController {
  constructor(
    private readonly scene: Phaser.Scene,
    private readonly bridge: GameBridgeService,
    private readonly tooltip: TooltipService,
  ) {}

  /** Registriert die Pointer-Listener auf der Scene. Nur einmal aufrufen
   *  (idempotent zu prüfen ist hier Sache des Callers — Phaser warnt
   *  bei doppelten Listenern nicht). */
  attach(): void {
    this.scene.input.on(
      Phaser.Input.Events.POINTER_MOVE,
      (pointer: Phaser.Input.Pointer) => this.handleHover(pointer),
    );
    // Pointer verlässt das Game-Canvas → Mob-Tooltip aus. Vermeidet Stale-
    // State, wenn der User die Maus über ein UI-Panel zieht.
    this.scene.input.on(Phaser.Input.Events.POINTER_OUT, () => {
      if (this.tooltip.activeMob()) this.tooltip.hide();
    });
  }

  private handleHover(pointer: Phaser.Input.Pointer): void {
    const tileX = Math.floor(pointer.worldX / TILE_SIZE);
    const tileY = Math.floor(pointer.worldY / TILE_SIZE);
    const npcs = this.bridge.state.npcsVisible();
    const npc = npcs.find((n) => n.x === tileX && n.y === tileY);
    if (npc) {
      this.tooltip.showMob(npc, pointer.x, pointer.y);
    } else if (this.tooltip.activeMob()) {
      this.tooltip.hide();
    }
  }
}
