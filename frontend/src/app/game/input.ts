// Input — kapselt die Phaser-Input-Verdrahtung der WorldScene.
//
// Übersetzt rohe Pointer/Keyboard-Events in **High-Level-Intents** (mit
// Tile-Koordinaten). Die WorldScene leitet sie an `bridge.sendIntent(...)`
// weiter; dieses Modul kennt die Bridge gar nicht — es liefert nur die
// strukturierten Events.
//
// Was hier NICHT passiert:
//   • Pathfinding (macht das Backend / Server-side).
//   • Tasten-Bindings für UI-Panels (I für Inventar, K für Skills, …) —
//     die wandern mit den Panel-Components (F5+) in Angular-Komponenten,
//     die Document-Level-Keyboard-Listener anbringen.
//   • Mobile-Joystick — Legacy hatte `window.touchInput`; F4c liest das
//     (Wenn vorhanden) im update-Tick und übergibt es an die Scene.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Tile-Position aus Welt-Koordinaten. */
export interface TilePosition {
  readonly x: number;
  readonly y: number;
}

/** Callbacks, die der Input-Manager an die Scene/Bridge weiterreicht. */
export interface InputCallbacks {
  /** Tile-Klick (linke Maustaste / Tap). Param ist Tile-Koord. */
  readonly onTileClick: (pos: TilePosition) => void;
  /** Sprint-Tasten-Zustand (SHIFT) wechselt. */
  readonly onSprintChange: (on: boolean) => void;
  /** Build-Mode-Toggle (B). Nur signalisieren; die Visualisierung kommt mit F5+. */
  readonly onToggleBuildMode: () => void;
}

/**
 * Registriert alle Input-Listener auf einer Scene. Räumt nichts auf —
 * Phaser-Scene-Shutdown destroyt die Listener von selbst.
 */
export function setupInput(
  scene: Phaser.Scene,
  callbacks: InputCallbacks,
): { isSprintHeld: () => boolean } {
  if (!scene.input.keyboard) {
    // Headless / no-input — nichts zu tun. Sollte im echten Browser nie
    // vorkommen, aber TS verlangt die Null-Prüfung.
    return { isSprintHeld: () => false };
  }
  const kb = scene.input.keyboard;

  // ─── Pointer: Klick auf der Welt → Tile-Koordinate ───────────────────
  scene.input.on(
    Phaser.Input.Events.POINTER_DOWN,
    (pointer: Phaser.Input.Pointer) => {
      // Welt-Koordinate (berücksichtigt Kamera-Scroll/Zoom)
      const worldX = pointer.worldX;
      const worldY = pointer.worldY;
      const tileX = Math.floor(worldX / TILE_SIZE);
      const tileY = Math.floor(worldY / TILE_SIZE);
      callbacks.onTileClick({ x: tileX, y: tileY });
    },
  );

  // ─── Keyboard: SHIFT = Sprint ────────────────────────────────────────
  const sprintKey = kb.addKey(Phaser.Input.Keyboard.KeyCodes.SHIFT, /*emitOnRepeat*/ false);
  sprintKey.on('down', () => callbacks.onSprintChange(true));
  sprintKey.on('up', () => callbacks.onSprintChange(false));

  // ─── Keyboard: B = Build-Mode Toggle ─────────────────────────────────
  kb.on('keydown-B', () => callbacks.onToggleBuildMode());

  return { isSprintHeld: () => sprintKey.isDown };
}
