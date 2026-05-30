import { Routes } from '@angular/router';

// F4: Phaser-Renderer als Default-Route — die Welt rendert in einen Vollbild-
// Host. UI-Panels (F5+) werden später als Overlay-Components über den Render
// gelegt (Routing oder feste Component-Composition in `App`).
export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./game/phaser-game.component').then((m) => m.PhaserGameComponent),
  },
];
