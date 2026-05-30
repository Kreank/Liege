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

interface PlayerRow {
  readonly id: number;
  readonly name: string;
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
      .map((it: InventoryItem) => ({ id: it.id, name: it.name })),
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
}
