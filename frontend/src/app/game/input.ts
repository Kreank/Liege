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
  /** WASD/Arrow-Tasten: Bewegung um delta-tiles. Bug 31.05 Issue #3. */
  readonly onMoveStep: (dx: number, dy: number) => void;
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

  // ─── Keyboard: WASD + Arrow-Tasten → Bewegung um 1 Tile ──────────────
  // Repeat aktiv (emitOnRepeat=true), damit Halten kontinuierlich läuft.
  const KC = Phaser.Input.Keyboard.KeyCodes;
  const up    = kb.addKey(KC.W,    /*emitOnRepeat*/ true);
  const down  = kb.addKey(KC.S,    true);
  const left  = kb.addKey(KC.A,    true);
  const right = kb.addKey(KC.D,    true);
  const arrUp    = kb.addKey(KC.UP,    true);
  const arrDown  = kb.addKey(KC.DOWN,  true);
  const arrLeft  = kb.addKey(KC.LEFT,  true);
  const arrRight = kb.addKey(KC.RIGHT, true);
  // Throttle: Bewegungs-Intent max alle 120ms (sonst flutet WS bei
  // gehaltener Taste). Sprint senkt das auf 80ms.
  let lastMoveAt = 0;
  const moveCheck = (dx: number, dy: number) => {
    const now = performance.now();
    const interval = sprintKey.isDown ? 80 : 120;
    if (now - lastMoveAt < interval) return;
    lastMoveAt = now;
    callbacks.onMoveStep(dx, dy);
  };
  up.on('down',    () => moveCheck(0, -1));
  down.on('down',  () => moveCheck(0,  1));
  left.on('down',  () => moveCheck(-1, 0));
  right.on('down', () => moveCheck(1,  0));
  arrUp.on('down',    () => moveCheck(0, -1));
  arrDown.on('down',  () => moveCheck(0,  1));
  arrLeft.on('down',  () => moveCheck(-1, 0));
  arrRight.on('down', () => moveCheck(1,  0));

  return { isSprintHeld: () => sprintKey.isDown };
}
