// Input — kapselt die Phaser-Input-Verdrahtung der WorldScene.
//
// Übersetzt rohe Pointer/Keyboard-Events in **High-Level-Intents** (mit
// Tile-Koordinaten) und stellt einen **held-state** der Richtungstasten
// bereit, den der Scene-update-Tick pro Frame pollt (Legacy-Style
// kontinuierliches Pixel-Movement — myPx/myPy aus app.js).
//
// Was hier NICHT passiert:
//   • Pathfinding (macht das Backend / Server-side).
//   • Pixel-Bewegung selbst — die rechnet die Scene im update-Tick aus den
//     keys-Flags + Kollisions-Check.
//   • Tasten-Bindings für UI-Panels (I für Inventar, K für Skills, …) —
//     die wandern mit den Panel-Components (F5+) in Angular-Komponenten,
//     die Document-Level-Keyboard-Listener anbringen.

import Phaser from 'phaser';

import { TILE_SIZE } from '../core/data/tiles';

/** Tile-Position aus Welt-Koordinaten. */
export interface TilePosition {
  readonly x: number;
  readonly y: number;
}

/** Held-State der Richtungstasten (Polling im Update-Tick). */
export interface HeldKeys {
  up: boolean;
  down: boolean;
  left: boolean;
  right: boolean;
  sprint: boolean;
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
 *
 * Liefert ein `keys`-Objekt zurück, dessen Felder die Scene pro Frame
 * pollt. So bleibt die Frame-Logik (Pixel-Move, Kollisions-Check) bei der
 * Scene und der Input-Layer bleibt dünn.
 */
export function setupInput(
  scene: Phaser.Scene,
  callbacks: InputCallbacks,
): { isSprintHeld: () => boolean; keys: Readonly<HeldKeys> } {
  const keys: HeldKeys = {
    up: false, down: false, left: false, right: false, sprint: false,
  };

  if (!scene.input.keyboard) {
    return { isSprintHeld: () => false, keys };
  }
  const kb = scene.input.keyboard;

  // ─── Pointer: Klick auf der Welt → Tile-Koordinate ───────────────────
  scene.input.on(
    Phaser.Input.Events.POINTER_DOWN,
    (pointer: Phaser.Input.Pointer) => {
      const worldX = pointer.worldX;
      const worldY = pointer.worldY;
      const tileX = Math.floor(worldX / TILE_SIZE);
      const tileY = Math.floor(worldY / TILE_SIZE);
      callbacks.onTileClick({ x: tileX, y: tileY });
    },
  );

  // ─── Keyboard: B = Build-Mode Toggle ─────────────────────────────────
  kb.on('keydown-B', () => callbacks.onToggleBuildMode());

  // ─── Held-state-Tracking (Window-Level, damit Canvas-Focus egal ist).
  // Phaser-Keyboard hört auf das Canvas; sobald der User in ein <input>
  // (Char-Modal, Chat) klickt, geht der Focus weg → Phaser-keydown stoppt.
  // window.addEventListener fängt das überall ab; wir filtern aktive
  // Text-Felder explizit (sonst tippt jede WASD-Eingabe in der Welt mit).
  const isTextField = (el: EventTarget | null): boolean => {
    if (!(el instanceof HTMLElement)) return false;
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.isContentEditable) return true;
    return false;
  };

  const setKey = (k: keyof HeldKeys, v: boolean): void => {
    if (k === 'sprint') {
      if (keys.sprint !== v) {
        keys.sprint = v;
        callbacks.onSprintChange(v);
      }
      return;
    }
    keys[k] = v;
  };

  const winKeyDown = (ev: KeyboardEvent) => {
    if (isTextField(ev.target)) return;
    switch (ev.key.toLowerCase()) {
      case 'w': case 'arrowup':    setKey('up', true);    ev.preventDefault(); break;
      case 's': case 'arrowdown':  setKey('down', true);  ev.preventDefault(); break;
      case 'a': case 'arrowleft':  setKey('left', true);  ev.preventDefault(); break;
      case 'd': case 'arrowright': setKey('right', true); ev.preventDefault(); break;
      case 'shift':                setKey('sprint', true); break;
    }
  };
  const winKeyUp = (ev: KeyboardEvent) => {
    switch (ev.key.toLowerCase()) {
      case 'w': case 'arrowup':    setKey('up', false);    break;
      case 's': case 'arrowdown':  setKey('down', false);  break;
      case 'a': case 'arrowleft':  setKey('left', false);  break;
      case 'd': case 'arrowright': setKey('right', false); break;
      case 'shift':                setKey('sprint', false); break;
    }
  };
  // Fokus-Verlust (Tab-Switch, Alt-Tab) → alle Tasten loslassen, sonst
  // läuft der Char weiter wenn der User zurückkommt.
  const onBlur = () => {
    setKey('up', false); setKey('down', false);
    setKey('left', false); setKey('right', false);
    setKey('sprint', false);
  };
  window.addEventListener('keydown', winKeyDown);
  window.addEventListener('keyup', winKeyUp);
  window.addEventListener('blur', onBlur);
  scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
    window.removeEventListener('keydown', winKeyDown);
    window.removeEventListener('keyup', winKeyUp);
    window.removeEventListener('blur', onBlur);
  });

  return {
    isSprintHeld: () => keys.sprint,
    keys,
  };
}
