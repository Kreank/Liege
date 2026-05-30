// App-Root — der Shell-Container. Hostet den Phaser-Renderer (lazy via
// @defer, damit das ~1.2-MB-Phaser-Bundle nicht im Initial-Chunk landet)
// und legt die Angular-UI-Panels (HUD, Hotbar, …) absolute-positioniert
// obendrauf.
//
// Konvention (siehe Refactor-Plan §F4-F15):
//   • <app-phaser-game> als Render-Layer (Defer-Block).
//   • Jede UI-Komponente ist standalone, OnPush, bindet an Signals aus
//     GameStateService. Keine Angular-Routen — die UI ist ein einziger
//     Bildschirm + Overlays.

import { ChangeDetectionStrategy, Component } from '@angular/core';

import { PhaserGameComponent } from './game/phaser-game.component';
import { HudComponent } from './ui/hud/hud.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [PhaserGameComponent, HudComponent],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {}
