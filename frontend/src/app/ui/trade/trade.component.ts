// TradeComponent — Händler-Modal (Buy/Sell + Coin-Anzeige).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 264-282.
//   • Renderer: `app.js` `openTrade`, `closeTrade`, `refreshTradeUI`
//                 (~6145-6240).
//
// Backend:
//   • `trade_open { npc_id, npc_name, offerings, coins }` öffnet.
//   • `trade_coins { wallet_copper }` aktualisiert die Coin-Anzeige.
//   • Sendet `buy_item { kind }` und `sell_item { item_id }`.

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

interface SellableRow {
  readonly id: number;
  readonly name: string;
  readonly quantity: number;
}

@Component({
  selector: 'app-trade',
  standalone: true,
  templateUrl: './trade.component.html',
  styleUrl: './trade.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TradeComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly trade = computed(() => this.state.activeTrade());
  readonly visible = computed<boolean>(() => this.trade() !== null);

  readonly sellable = computed<readonly SellableRow[]>(() =>
    this.state.inventory()
      .filter((it: InventoryItem) => !it.equipped_slot)
      .map((it: InventoryItem) => ({
        id: it.id,
        name: it.unique_name ?? it.name,
        quantity: it.quantity ?? 1,
      })),
  );

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.visible()) this.close(); }

  close(): void { this.state.closeTrade(); }

  buy(kind: string): void { this.ws.send({ type: 'buy_item', kind }); }
  sell(itemId: number): void { this.ws.send({ type: 'sell_item', item_id: itemId }); }
}
