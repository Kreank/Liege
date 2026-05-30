// TooltipService — globaler Hover-Tooltip-Anchor für Item-Daten.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • `app.js` `showItemTooltip`, `hideItemTooltip`, `pinItemTooltip`,
//     `unpinItemTooltip` (Z. 4225-4429).
//
// Design-Entscheidung F-extras-3:
//   • Wir ziehen NUR die Hover-Variante in einen zentralen Service, weil
//     mehrere Panels (Inventar, Hotbar, Trade, Crafting, Chest) am gleichen
//     Anchor hängen. Der „Pinned Tooltip mit Aktions-Buttons" aus dem
//     Legacy ist konzeptionell näher an einem Context-Menü und wird vom
//     Inventar bereits über sein eigenes Action-Submenü abgedeckt — wir
//     bauen ihn jetzt NICHT mit, sonst läuft F-extras-3 in Scope-Creep.
//     Die optionale `pin()`-Methode existiert aber als Hook für später.
//
// Komponenten rufen `tooltip.show(item, x, y)` auf `mouseover`/`mousemove`,
// `tooltip.hide()` auf `mouseleave`. Die `ItemTooltipComponent` ist die
// einzige Stelle, die den DOM-Knoten rendert; sie liest hier ihre State-
// Signals.

import { Injectable, signal } from '@angular/core';

import type { InventoryItem } from '../models/item.model';

/** Eine Item-Form, die der Tooltip versteht. Wir geben uns mit dem Schnitt
 *  zufrieden, damit auch synthetische „Items" (Ground-Drops mit Mini-
 *  Daten, Trade-Offerings, Recipe-Output-Stubs) den Tooltip benutzen
 *  können. */
export type TooltipItem = Pick<
  InventoryItem,
  'kind' | 'name' | 'quality' | 'category' | 'quantity' | 'unique_name'
> & {
  readonly id?: number;
  readonly equipped_slot?: InventoryItem['equipped_slot'];
};

interface TooltipPayload {
  readonly item: TooltipItem;
  readonly x: number;
  readonly y: number;
  readonly pinned: boolean;
}

@Injectable({ providedIn: 'root' })
export class TooltipService {
  readonly active = signal<TooltipPayload | null>(null);

  show(item: TooltipItem, x: number, y: number): void {
    // Pinned-Tooltip nicht durch Hover überschreiben (Legacy-Verhalten:
    // `if (tt.classList.contains('pinned')) return;`).
    const cur = this.active();
    if (cur?.pinned) return;
    this.active.set({ item, x, y, pinned: false });
  }

  move(x: number, y: number): void {
    const cur = this.active();
    if (!cur || cur.pinned) return;
    this.active.set({ ...cur, x, y });
  }

  hide(): void {
    const cur = this.active();
    if (!cur || cur.pinned) return;
    this.active.set(null);
  }

  /** Pinned-Variante (Right-Click) — bleibt sichtbar bis `unpin()`. F-final
   *  kann darauf aufbauen, um Aktions-Buttons anzubieten. */
  pin(item: TooltipItem, x: number, y: number): void {
    this.active.set({ item, x, y, pinned: true });
  }

  unpin(): void {
    const cur = this.active();
    if (cur?.pinned) this.active.set(null);
  }
}
