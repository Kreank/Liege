// BillsComponent — Workshop-Aufträge im Crafting-Overlay.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 309-312 (`#crafting-bills-section`).
//   • Renderer:   `app.js` `refreshBillsUI`, `addBill`, `removeBill`
//                 (Z. 6336-6557).
//   • Styles:     `style.css` Z. 1087-1098.
//
// Sichtbarkeit: das Panel rendert sich genau dann, wenn das Crafting-Overlay
// aktiv ist (`state.activeCrafting`) — es ist ein In-Crafting-Sub-Panel und
// kein eigenständiges Modal. Es zeigt nur die Bills der aktiven Station.
//
// Intents:
//   • add_bill    { station_type, recipe_id, count }
//   • remove_bill { bill_id }
//   • list_bills  { station_type } — wird beim Crafting-Open gefeuert
//     (siehe `crafting.component.ts`).
//
// Hinweis: Der `×5`-Knopf, der einen Bill anlegt, lebt im Crafting-Panel
// (an der Rezept-Zeile). Diese Komponente besitzt die Bill-LISTE, nicht
// die Bill-Erzeugung. `add_bill` ist trotzdem exportiert, damit andere
// Panels (zukünftig auch das Rezept-Detail) sie via Bridge benutzen können.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';

import type { Bill } from '../../core/models/bill.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

interface BillRow {
  readonly id: number;
  readonly displayName: string;
  readonly progress: string;
  readonly status: string;
  readonly statusClass: 'active' | 'blocked' | '';
}

@Component({
  selector: 'app-bills',
  standalone: true,
  templateUrl: './bills.component.html',
  styleUrl: './bills.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BillsComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  /** Wir rendern uns nur, wenn Crafting offen ist. */
  readonly visible = computed<boolean>(() => this.state.activeCrafting() !== null);

  readonly rows = computed<readonly BillRow[]>(() => {
    const cr = this.state.activeCrafting();
    if (!cr) return [];
    const allBills = this.state.bills();
    return allBills
      .filter((b) => b.station_type === cr.station)
      .map((b) => {
        const rec = cr.recipes.find((r) => r.output === b.recipe_id);
        // Legacy nutzt rec.name → unsere RecipeDef hat `output` als Schlüssel
        // und keinen separaten Display-Namen. Fallback = recipe_id.
        const displayName = rec ? rec.output : b.recipe_id;
        const statusRaw = (b.status ?? '').toString();
        const statusClass: 'active' | 'blocked' | '' =
          statusRaw === 'active' ? 'active' :
          statusRaw === 'blocked' ? 'blocked' : '';
        return {
          id: b.id,
          displayName,
          progress: `${b.completed}/${b.target_count}`,
          status: statusRaw,
          statusClass,
        };
      });
  });

  remove(billId: number): void {
    this.ws.send({ type: 'remove_bill', bill_id: billId });
  }

  /** Convenience für andere Komponenten (Crafting-Panel). */
  add(stationType: string, recipeId: string, count: number): void {
    this.ws.send({
      type: 'add_bill',
      station_type: stationType,
      recipe_id: recipeId,
      count,
    });
  }

  // Template-Helper.
  trackById(_idx: number, row: BillRow): number { return row.id; }

  // Public API für externe Callsites (z. B. Crafting-Component könnte
  // den Server zum Refresh prodden).
  refresh(stationType: string): void {
    this.ws.send({ type: 'list_bills', station_type: stationType });
  }

  // Exposed für Templates, die das volle Bill-Objekt brauchen.
  asBill(b: Bill): Bill { return b; }
}
