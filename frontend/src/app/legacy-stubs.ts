// Legacy-Stubs — Marker für noch-nicht migrierte UI-/DOM-Stellen aus
// `frontend/legacy/app.js` `WorldScene`. **Diese Datei enthält absichtlich
// KEINEN Funktionscode** — nur Konstanten + Kommentar-Marker.
//
// Regel (Refactor-Plan §F4):
//   • Render-/Input-Teile wandern in `game/world-scene.ts`.
//   • UI-/DOM-/Panel-Teile bleiben vorerst un-migriert und werden hier mit
//     einem `// TODO F5+: <Panel>`-Marker dokumentiert.
//   • Eine Panel-Migration (F5-F15) entfernt den passenden Marker und legt
//     die zugehörige Angular-Component an.
//
// Diese Datei ist die EINZIGE Stelle, an der `// TODO F5+`-Marker stehen
// dürfen (siehe Plan). Sucht der Plan nach offenen UI-Punkten → grep hier.

export const F4_PENDING_UI_PANELS = [
  // TODO F5+: Minimap (DOM-Canvas, kein Phaser — wird per `drawMinimap`
  //          gemalt). Eventuell als Angular-Component mit `<canvas>`.
  'minimap',

  // TODO F5+: Top-Right-Links (Admin/Logout) — werden Legacy via
  //          `document.body.appendChild` rangehängt; gehört in den App-Shell.
  'top-right-links',

  // TODO F5+: Settings-Overlay (Audio-Sliders Master/SFX/Music + Mute).
  //          Legacy `setupSoundSettings`. Liegt komplett im IIFE oben.
  'settings',

  // TODO F5+: Mobile-Touch-Joystick + Action-Buttons.
  //          Legacy `window.MobileUI`, `window.touchInput`.
  'mobile-controls',
] as const;
