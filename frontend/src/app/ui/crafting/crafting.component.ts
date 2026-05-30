// CraftingComponent — Werkbank / Schmelze / Amboss / Hand-Crafting.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 303-315.
//   • Renderer: `app.js` `openCrafting`, `closeCrafting`, `refreshCraftingUI`
//                 (~6332-6450 — Category-Tabs, Recipe-Rows).
//
// Backend:
//   • `crafting_open { station, recipes }` öffnet das Modal.
//   • Hand-Crafting öffnet der Spieler aktiv per `open_hand_crafting`.
//   • `craft { output, station }` produziert ein Item / Bill.
//
// Scope: Wir migrieren das Grundgerüst (Station-Label, Recipe-Grid,
// Klick-Action). Das volle Category-Tab-System + Research-Gate (Welle 22)
// + Bills-Section gehören:
//   • Tabs/Subcats → Cleanup-Phase nach F-final (Verhaltenserhaltend
//     genug für jetzt — Backend filtert Rezepte sowieso bereits).
//   • Bills-Section → eigene BillsComponent in F-extras-2.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  effect,
  inject,
} from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { BillsComponent } from '../bills/bills.component';

const STATION_LABEL: Readonly<Record<string, string>> = {
  workbench: 'Werkbank',
  furnace:   'Schmelze',
  anvil:     'Amboss',
  hand:      '🛠 Handwerken',
};

@Component({
  selector: 'app-crafting',
  standalone: true,
  imports: [BillsComponent],
  templateUrl: './crafting.component.html',
  styleUrl: './crafting.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CraftingComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly crafting = computed(() => this.state.activeCrafting());
  readonly visible = computed<boolean>(() => this.crafting() !== null);

  readonly stationLabel = computed<string>(() => {
    const c = this.crafting();
    if (!c) return '';
    return STATION_LABEL[c.station] ?? c.station;
  });

  constructor() {
    // Beim Öffnen einer Crafting-Station fragen wir frische Bills an
    // (Legacy frontend/legacy/app.js Z. 6343 — `list_bills` im openCrafting).
    // Verfolgt nur Station-Wechsel; ein erneutes Open derselben Station
    // schickt erneut, das ist auch das Legacy-Verhalten.
    let lastStation: string | null = null;
    effect(() => {
      const c = this.crafting();
      const station = c?.station ?? null;
      if (station && station !== lastStation) {
        this.ws.send({ type: 'list_bills', station_type: station });
      }
      lastStation = station;
    });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.visible()) this.close(); }

  close(): void { this.state.closeCrafting(); }

  craft(output: string): void {
    const c = this.crafting();
    if (!c) return;
    this.ws.send({ type: 'craft', output, station: c.station });
  }

  /** ×5-Auftrag erzeugen (Legacy „bill-btn"). */
  addBill(output: string, count: number): void {
    const c = this.crafting();
    if (!c) return;
    this.ws.send({
      type: 'add_bill',
      station_type: c.station,
      recipe_id: output,
      count,
    });
  }
}
