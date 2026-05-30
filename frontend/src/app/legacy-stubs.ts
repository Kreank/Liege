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
  // TODO F-final: Mobile-Touch-Joystick + Action-Buttons.
  //          Legacy `window.MobileUI`, `window.touchInput`.
  'mobile-controls',
] as const;
