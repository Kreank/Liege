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
import { CharacterComponent } from './ui/character/character.component';
import { HotbarComponent } from './ui/hotbar/hotbar.component';
import { HudComponent } from './ui/hud/hud.component';
import { InventoryComponent } from './ui/inventory/inventory.component';
import { QuestsComponent } from './ui/quests/quests.component';
import { SkillsComponent } from './ui/skills/skills.component';
import { TalentsComponent } from './ui/talents/talents.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    PhaserGameComponent,
    HudComponent,
    HotbarComponent,
    InventoryComponent,
    SkillsComponent,
    TalentsComponent,
    CharacterComponent,
    QuestsComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {}
