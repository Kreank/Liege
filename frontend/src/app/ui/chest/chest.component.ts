// ChestComponent — Truhe-Modal mit zwei Spalten (Inventar ↔ Truhe).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 284-301 (`#chest-overlay`).
//   • Renderer: `app.js` `openChest`, `closeChest`, `refreshChestUI`,
//                 `transferToChest`, `transferFromChest` (~6272-6330).
//
// Backend: `chest_open { chest_id, items }` öffnet, `chest_add` /
//          `chest_remove` aktualisieren. Sendet `chest_transfer_to /
//          chest_transfer_from { chest_id, item_id }`.
//
// H2.6 — Container-Aktionen: Wasser-Container im eigenen Inventar
// (Eimer/Gießkanne/Wasserschlauch) bekommen Sub-Action-Buttons:
//   • 💧 Trinken    → `drink_container {item_id}` (kein Tile-Target).
//   • 🪣 Auffüllen  → setzt `state.containerAction` (fill_container),
//                     das `<app-container-action-overlay>` intercepted
//                     den nächsten Click und feuert den Intent mit
//                     Tile-Koord.
//   • 🌱 Gießen     → analog, action='water_plant'.
// `drink_water_tile` wird **nicht** vom Chest-Panel aus angeboten —
// das gehört in das normale Welt-Click-Routing (Subagent C / WorldScene),
// weil es ein Wasser-Tile ohne Container voraussetzt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
} from '@angular/core';

import type { InventoryItem } from '../../core/models/item.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

/** Wasser-Container-Kinds (Backend `items.WATER_CONTAINER_CAPACITY`).
 *  Gleichgehalten zu `backend/items.py` — beim Hinzufügen neuer Container
 *  beide Listen pflegen. */
const WATER_CONTAINER_KINDS: readonly string[] = [
  'wooden_bucket',
  'iron_bucket',
  'leather_waterskin',
  'wooden_watering_can',
  'iron_watering_can',
];

interface PlayerRow {
  readonly id: number;
  readonly name: string;
  /** True wenn das Item ein Wasser-Container ist (H2.6 — extra Buttons). */
  readonly isContainer: boolean;
}

@Component({
  selector: 'app-chest',
  standalone: true,
  templateUrl: './chest.component.html',
  styleUrl: './chest.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChestComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly chest = computed(() => this.state.activeChest());
  readonly visible = computed<boolean>(() => this.chest() !== null);

  readonly playerItems = computed<readonly PlayerRow[]>(() =>
    this.state.inventory()
      .filter((it: InventoryItem) => !it.equipped_slot)
      .map((it: InventoryItem) => ({
        id: it.id,
        name: it.name,
        isContainer: WATER_CONTAINER_KINDS.includes(it.kind),
      })),
  );

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.close();
  }

  close(): void { this.state.closeChest(); }

  transferToChest(itemId: number): void {
    const c = this.chest();
    if (!c) return;
    this.ws.send({ type: 'chest_transfer_to', chest_id: c.chest_id, item_id: itemId });
  }

  transferFromChest(itemId: number): void {
    const c = this.chest();
    if (!c) return;
    this.ws.send({ type: 'chest_transfer_from', chest_id: c.chest_id, item_id: itemId });
  }

  // ─── H2.6 — Container-Aktionen ───────────────────────────────────────

  /** Trinken aus dem eigenen Container — kein Tile-Target nötig. Backend
   *  zieht 1 Charge ab und sendet `inventory_update` zurück. */
  drinkContainer(itemId: number): void {
    this.ws.send({ type: 'drink_container', item_id: itemId });
  }

  /** Auffüllen am Wasser/Brunnen — wir gehen in den Tile-Target-Mode.
   *  Das Chest-Panel schließt sich nicht — Spieler soll nach dem Picken
   *  weiter mit der Truhe arbeiten können. Das Overlay rendert über
   *  allem, schließt sich nach Erfolg automatisch. */
  startFillContainer(item: PlayerRow): void {
    this.state.beginContainerAction({
      action: 'fill_container',
      item_id: item.id,
      item_name: item.name,
    });
  }

  /** Acker gießen — analog. */
  startWaterPlant(item: PlayerRow): void {
    this.state.beginContainerAction({
      action: 'water_plant',
      item_id: item.id,
      item_name: item.name,
    });
  }
}
