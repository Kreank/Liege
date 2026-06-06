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
  effect,
  inject,
  signal,
} from '@angular/core';

import { ITEM } from '../../core/data/items';
import type { InventoryItem } from '../../core/models/item.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

/** Tab-Modus im Trade-Modal (H2.21). */
type TradeTab = 'buy' | 'sell';

/** Schwellwert für Sell-Confirmation: Equipment/Quality oder hoher Stack. */
const SELL_CONFIRM_QUANTITY = 5;
const SELL_CONFIRM_CATEGORIES: ReadonlySet<string> = new Set([
  'weapon', 'armor', 'jewelry', 'equipment',
]);

interface SellableRow {
  readonly id: number;
  readonly name: string;
  readonly quantity: number;
  readonly category: string;
  readonly needsConfirm: boolean;
}

interface SellConfirmState {
  readonly item: SellableRow;
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

  /** Aktiver Tab im Trade-Modal — H2.21. */
  readonly tab = signal<TradeTab>('buy');

  /** Optionaler Confirm-Dialog für teure/equipment-Sells. */
  readonly sellConfirm = signal<SellConfirmState | null>(null);

  constructor() {
    // Beim Öffnen eines neuen Trades immer zum „Kaufen"-Tab springen
    // (Standard-Flow ist „Spieler will Händler-Angebote sehen"). Wenn der
    // Spieler explizit auf „Verkaufen" geklickt hat, bleibt das Tab dort
    // BIS das Modal schließt — der Re-Reset triggert via `trade()`-Change.
    let lastNpcId: number | null = null;
    effect(() => {
      const t = this.trade();
      const npcId = t?.npc_id ?? null;
      if (npcId !== lastNpcId) {
        this.tab.set('buy');
        this.sellConfirm.set(null);
        lastNpcId = npcId;
      }
    });
  }

  readonly sellable = computed<readonly SellableRow[]>(() =>
    this.state.inventory()
      .filter((it: InventoryItem) => !it.equipped_slot)
      .map((it: InventoryItem) => {
        const def = ITEM[it.kind];
        const category = it.category ?? def?.category ?? '';
        const qty = it.quantity ?? 1;
        return {
          id: it.id,
          name: it.unique_name ?? it.name,
          quantity: qty,
          category,
          needsConfirm: qty >= SELL_CONFIRM_QUANTITY || SELL_CONFIRM_CATEGORIES.has(category),
        };
      }),
  );

  // ─── Welle 53: Sortierung (gegen „alles wild durcheinander") ───────────
  readonly sortBy = signal<'category' | 'name' | 'price'>('category');
  setSort(s: 'category' | 'name' | 'price'): void { this.sortBy.set(s); }

  private readonly CAT_ORDER: Readonly<Record<string, number>> = {
    weapon: 0, armor: 1, magic: 2, consumable: 3, food: 4, resource: 5, ammo: 6,
  };
  private catRank(c: string): number { return this.CAT_ORDER[c] ?? 99; }
  private cmp(s: string, ca: string, na: string, pa: number,
              cb: string, nb: string, pb: number): number {
    if (s === 'name') return na.localeCompare(nb);
    if (s === 'price') return (pa - pb) || na.localeCompare(nb);
    return (this.catRank(ca) - this.catRank(cb)) || na.localeCompare(nb);
  }

  /** Kauf-Angebote mit Kategorie angereichert + sortiert. */
  readonly displayOfferings = computed(() => {
    const t = this.trade();
    if (!t) return [];
    const s = this.sortBy();
    return t.offerings
      .map((o) => ({ ...o, category: ITEM[o.kind]?.category ?? '' }))
      .sort((a, b) => this.cmp(s, a.category, a.name, a.price, b.category, b.name, b.price));
  });

  /** Verkaufsliste sortiert (Sell-Preis unbekannt → Preis-Sort fällt auf Name). */
  readonly displaySellable = computed(() => {
    const s = this.sortBy();
    return [...this.sellable()]
      .sort((a, b) => this.cmp(s, a.category, a.name, 0, b.category, b.name, 0));
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.sellConfirm()) { this.sellConfirm.set(null); return; }
    if (this.visible()) this.close();
  }

  close(): void { this.state.closeTrade(); }

  switchTab(t: TradeTab): void { this.tab.set(t); }

  buy(kind: string): void { this.ws.send({ type: 'buy_item', kind }); }

  /** Sell-Klick: bei „teuren" Items zuerst Confirm-Dialog, sonst direkt. */
  sell(item: SellableRow): void {
    if (item.needsConfirm) {
      this.sellConfirm.set({ item });
      return;
    }
    this._sendSell(item.id);
  }

  confirmSell(): void {
    const st = this.sellConfirm();
    if (!st) return;
    this._sendSell(st.item.id);
    this.sellConfirm.set(null);
  }

  cancelSell(): void { this.sellConfirm.set(null); }

  private _sendSell(itemId: number): void {
    this.ws.send({ type: 'sell_item', item_id: itemId });
  }
}
