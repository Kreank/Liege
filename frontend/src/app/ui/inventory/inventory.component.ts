// InventoryComponent — Modal-Overlay für Beutel + Ausrüstung.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 330-356 (`#inventory-overlay`).
//   • Renderer:   `app.js` `toggleInventory`, `renderInventory`,
//                 `_inventoryDrag*` (Z. ~4350-4600), `equipItem`,
//                 `unequipItem`, `useItem`, `dropItem`, `splitStack`.
//   • Styles:     `style.css` Z. 838-994.
//
// Tastatur: `I` toggelt das Overlay, `Esc` schließt es.
//
// Intents:
//   • equip_item                   { item_id }
//   • unequip_item                 { item_id }
//   • use_item                     { item_id }
//   • drop_item                    { item_id, quantity? }
//   • split_stack                  { item_id, amount }     (Backend liest `amount`)
//   • merge_stacks                 { kind, quality }       (Backend merge-by-kind)
//
// Drag-Drop:
//   • Inv-Slot → Equip-Slot   = `equip_item`
//   • Equip-Slot → Beutel     = `unequip_item`
//   • Inv-Slot → Inv-Slot:
//       – gleicher kind+quality (stackable)  → `merge_stacks`
//       – sonst                              → lokales Reorder (localStorage)
//
// Reorder: das Backend kennt KEINEN `inventory_reorder`-Intent. Deshalb
// halten wir eine lokale Slot-Position-Map `slot_position[item_id] = idx`
// im Signal `slotOrder` und persistieren sie in `localStorage` unter
// `liege_inventory_order`.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import { EQUIP_SLOTS } from '../../core/data/equip-slots';
import { ITEM } from '../../core/data/items';
import type {
  EquipSlot,
  InventoryItem,
  ItemDef,
  ItemQuality,
} from '../../core/models/item.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { TooltipService } from '../../core/services/tooltip.service';

/** Welche Slots werden in der Equip-Grid angezeigt (Reihenfolge = Legacy). */
const EQUIP_SLOT_ORDER: readonly EquipSlot[] = EQUIP_SLOTS.map((s) => s.key);

/** Stack-Limits pro Kategorie — gespiegelt aus `backend/items.py` `STACK_LIMITS`. */
const STACK_LIMITS: Readonly<Record<string, number>> = {
  resource: 500,
  food: 150,
  consumable: 25,
  magic: 25,
};

/** Welche Kategorien sind stackable (Spiegel zu Backend `STACKABLE_CATEGORIES`). */
const STACKABLE_CATEGORIES: ReadonlySet<string> = new Set([
  'resource',
  'food',
  'consumable',
  'magic',
]);

/** localStorage-Key für die lokale Slot-Ordnung. */
const LS_ORDER_KEY = 'liege_inventory_order';

/** Schwellwerte für die Drop-Bestätigung. */
const DROP_CONFIRM_QUANTITY = 5;
const DROP_CONFIRM_CATEGORIES: ReadonlySet<string> = new Set([
  'equipment',
  'jewelry',
  'weapon',
  'armor',
]);

/** Visueller Stack-Füll-Zustand (für Border-/Badge-Tint). */
type StackFill = 'normal' | 'warn' | 'full';

interface InventoryGridSlot {
  readonly item: InventoryItem;
  readonly def: ItemDef | null;
  readonly qualityClass: string | null;
  readonly stackFill: StackFill;
}

interface EquipGridSlot {
  readonly slot: EquipSlot;
  readonly label: string;
  readonly item: InventoryItem | null;
  readonly def: ItemDef | null;
  readonly qualityClass: string | null;
}

/** Drag-Source-Typ — gemeinsame Form, die der Drop-Target lesen kann. */
interface DragPayload {
  readonly from: 'bag' | 'equip';
  readonly item_id: number;
}

/** State für den Split-Stack-Dialog. */
interface SplitDialogState {
  readonly item: InventoryItem;
  readonly max: number;
  readonly amount: number;
}

/** State für den Drop-Bestätigungs-Dialog. */
interface DropConfirmState {
  readonly item: InventoryItem;
  readonly name: string;
  readonly quantity: number;
}

const DND_MIME = 'application/json';

@Component({
  selector: 'app-inventory',
  standalone: true,
  templateUrl: './inventory.component.html',
  styleUrl: './inventory.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InventoryComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);
  private readonly tooltip = inject(TooltipService);

  // ─── Tooltip-Hover (F-extras-3) ──────────────────────────────────────
  showTooltip(item: InventoryItem, ev: MouseEvent): void {
    this.tooltip.show(item, ev.clientX, ev.clientY);
  }
  moveTooltip(ev: MouseEvent): void {
    this.tooltip.move(ev.clientX, ev.clientY);
  }
  hideTooltip(): void { this.tooltip.hide(); }

  readonly visible = signal<boolean>(false);

  /** Lokale Slot-Position-Map (item_id → visualSlotIdx). Wird in localStorage gespiegelt. */
  private readonly slotOrder = signal<Readonly<Record<number, number>>>(this._loadSlotOrder());

  /** Aktueller Modal-Dialog (Split-Stack), wenn offen. */
  readonly splitDialog = signal<SplitDialogState | null>(null);

  /** Aktueller Modal-Dialog (Drop-Bestätigung), wenn offen. */
  readonly dropConfirm = signal<DropConfirmState | null>(null);

  /** Items im Beutel (nicht equipped), sortiert nach lokaler Slot-Position. */
  readonly bagItems = computed<readonly InventoryGridSlot[]>(() => {
    const order = this.slotOrder();
    const raw = this.state
      .inventory()
      .filter((it) => !it.equipped_slot)
      .map((it) => {
        const def = ITEM[it.kind] ?? null;
        const category = it.category ?? def?.category ?? '';
        return {
          item: it,
          def,
          qualityClass: this._qualityClass(it.quality),
          stackFill: this._stackFill(it, category),
        };
      });
    // Stabil sortieren nach lokaler Position; Items ohne Eintrag landen am
    // Ende (in Insert-Reihenfolge — das ist die Backend-Reihenfolge).
    return raw
      .map((slot, idx) => ({ slot, idx, pos: order[slot.item.id] ?? Number.MAX_SAFE_INTEGER - idx }))
      .sort((a, b) => a.pos - b.pos)
      .map((x) => x.slot);
  });

  /** Equip-Slots (in fester Reihenfolge). */
  readonly equipSlots = computed<readonly EquipGridSlot[]>(() => {
    const inv = this.state.inventory();
    return EQUIP_SLOT_ORDER.map((slot) => {
      const equipped = inv.find((it) => it.equipped_slot === slot) ?? null;
      return {
        slot,
        label: EQUIP_SLOTS.find((s) => s.key === slot)?.label ?? slot,
        item: equipped,
        def: equipped ? ITEM[equipped.kind] ?? null : null,
        qualityClass: equipped ? this._qualityClass(equipped.quality) : null,
      };
    });
  });

  readonly walletCopper = computed<number>(() => this.state.walletCopper());

  // ─── Tastatur ────────────────────────────────────────────────────────
  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'i' || ev.key === 'I') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape') {
      // Dialoge schließen sich zuerst, sonst das Overlay.
      if (this.splitDialog()) { this.splitDialog.set(null); ev.preventDefault(); return; }
      if (this.dropConfirm()) { this.dropConfirm.set(null); ev.preventDefault(); return; }
      if (this.visible()) { this.visible.set(false); ev.preventDefault(); }
    }
  }

  // ─── Actions ─────────────────────────────────────────────────────────
  close(): void { this.visible.set(false); }

  /** Klick auf Inv-Slot — mit Shift öffnet sich der Split-Dialog. */
  onSlotClick(item: InventoryItem, ev: MouseEvent): void {
    if (ev.shiftKey) {
      ev.preventDefault();
      ev.stopPropagation();
      this.openSplitDialog(item);
      return;
    }
    this.useOrEquip(item);
  }

  useOrEquip(item: InventoryItem): void {
    const def = ITEM[item.kind];
    if (!def) return;
    if (def.slot) {
      if (item.equipped_slot) {
        this.bridge.sendIntent({ type: 'unequip_item', item_id: item.id });
      } else {
        this.bridge.sendIntent({ type: 'equip_item', item_id: item.id });
      }
      return;
    }
    // H2.18 — Spell-Item-Learning: Backend hat einen separaten `learn_spell`-
    // Intent für magic-Kategorie-Items, deren `kind` ein Spell-Catalog-Eintrag
    // ist (spell_book, ice_scroll, holy_shield_scroll, …). Wenn der Spieler
    // den Spell NOCH NICHT gelernt hat, lernt er ihn durch Verbrauch des Items.
    // Sonst (bereits gelernt) fällt das Item auf `use_item` zurück, was bei
    // consume-bare Scrolls den Cast direkt auslöst.
    if (def.category === 'magic' && this._isLearnableUnknownSpell(item.kind)) {
      this.bridge.sendIntent({ type: 'learn_spell', item_id: item.id });
      return;
    }
    if (def.category === 'consumable' || def.category === 'food' || def.category === 'magic') {
      this.bridge.sendIntent({ type: 'use_item', item_id: item.id });
    }
  }

  /** True wenn das Item-Kind im Spell-Catalog steht und der Spieler ihn noch
   *  nicht gelernt hat. Backend `handle_learn_spell` matcht über `combat.SPELLS`
   *  + `learned_spells`; das Frontend spiegelt beide über `state.spells()`. */
  private _isLearnableUnknownSpell(kind: string): boolean {
    const spells = this.state.spells();
    const inCatalog = spells.catalog.some((s) => s.id === kind);
    if (!inCatalog) return false;
    return !spells.learned.includes(kind);
  }

  /** Right-Click → Drop, ggf. mit Bestätigung. */
  dropItem(item: InventoryItem, ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    const def = ITEM[item.kind];
    const qty = item.quantity ?? 1;
    const category = item.category ?? def?.category ?? '';
    if (qty >= DROP_CONFIRM_QUANTITY || DROP_CONFIRM_CATEGORIES.has(category)) {
      this.dropConfirm.set({
        item,
        name: def?.name ?? item.name ?? item.kind,
        quantity: qty,
      });
      return;
    }
    this._sendDrop(item);
  }

  confirmDrop(): void {
    const st = this.dropConfirm();
    if (!st) return;
    this._sendDrop(st.item);
    this.dropConfirm.set(null);
  }

  cancelDrop(): void { this.dropConfirm.set(null); }

  private _sendDrop(item: InventoryItem): void {
    this.bridge.sendIntent({ type: 'drop_item', item_id: item.id });
  }

  /** Doppelklick → Split in zwei Hälften (Legacy-Default). */
  splitStack(item: InventoryItem, ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    const total = item.quantity ?? 1;
    if (total <= 1) return;
    const half = Math.floor(total / 2);
    if (half < 1) return;
    // Backend liest `amount`; `quantity` bleibt als Alias mit drin damit
    // ältere Backend-Builds nicht plötzlich brechen.
    this.bridge.sendIntent({
      type: 'split_stack',
      item_id: item.id,
      amount: half,
      quantity: half,
    });
  }

  /** Shift+Klick → Modal mit Menge-Slider. */
  openSplitDialog(item: InventoryItem): void {
    const total = item.quantity ?? 1;
    if (total <= 1) return;
    this.splitDialog.set({ item, max: total - 1, amount: Math.floor(total / 2) || 1 });
  }

  /** Slider-/Input-Bind im Dialog. */
  setSplitAmount(value: number): void {
    const st = this.splitDialog();
    if (!st) return;
    const clamped = Math.max(1, Math.min(st.max, Math.floor(value)));
    this.splitDialog.set({ ...st, amount: clamped });
  }

  /** Dialog-Submit. */
  confirmSplit(): void {
    const st = this.splitDialog();
    if (!st) return;
    this.bridge.sendIntent({
      type: 'split_stack',
      item_id: st.item.id,
      amount: st.amount,
      quantity: st.amount,
    });
    this.splitDialog.set(null);
  }

  cancelSplit(): void { this.splitDialog.set(null); }

  unequip(item: InventoryItem): void {
    this.bridge.sendIntent({ type: 'unequip_item', item_id: item.id });
  }

  // ─── Drag-Drop ───────────────────────────────────────────────────────
  onDragStart(ev: DragEvent, payload: DragPayload): void {
    if (!ev.dataTransfer) return;
    ev.dataTransfer.setData(DND_MIME, JSON.stringify(payload));
    ev.dataTransfer.effectAllowed = 'move';
  }

  onDragOver(ev: DragEvent): void {
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
  }

  /** Drop auf einen Equip-Slot — Inv-Item equippen. */
  onDropEquip(ev: DragEvent, _slot: EquipSlot): void {
    ev.preventDefault();
    const payload = this._readPayload(ev);
    if (!payload) return;
    if (payload.from === 'bag') {
      // Backend bestimmt selbst den Ziel-Slot anhand des Item-Kinds; Slot
      // wird informativ mit-gesendet (Legacy: equip_item ohne Slot).
      this.bridge.sendIntent({ type: 'equip_item', item_id: payload.item_id });
    }
    // Equip → Equip ist no-op (Backend würde es ohnehin als equip auflösen).
  }

  /** Drop auf den Beutel-Bereich (leerer Spalt) — equipped Item ablegen. */
  onDropBag(ev: DragEvent): void {
    ev.preventDefault();
    const payload = this._readPayload(ev);
    if (!payload) return;
    if (payload.from === 'equip') {
      this.bridge.sendIntent({ type: 'unequip_item', item_id: payload.item_id });
    }
    // bag→bag ohne konkreten Ziel-Slot ist no-op (Reorder läuft pro Slot).
  }

  /** Drop auf einen konkreten Inv-Slot — Reorder/Merge/Swap. */
  onDropBagSlot(ev: DragEvent, target: InventoryGridSlot): void {
    ev.preventDefault();
    ev.stopPropagation();
    const payload = this._readPayload(ev);
    if (!payload) return;

    // Equip → Beutel-Slot: Item unequippen (ignoriert die genaue Slot-Position).
    if (payload.from === 'equip') {
      this.bridge.sendIntent({ type: 'unequip_item', item_id: payload.item_id });
      return;
    }

    // bag → bag
    if (payload.item_id === target.item.id) return; // selber Slot

    const source = this.state.inventory().find((it) => it.id === payload.item_id);
    if (!source) return;

    const sameKind = source.kind === target.item.kind && (source.quality ?? 'normal') === (target.item.quality ?? 'normal');
    const def = ITEM[source.kind];
    const category = source.category ?? def?.category ?? '';
    if (sameKind && STACKABLE_CATEGORIES.has(category)) {
      // Merge via Backend (merge-by-kind+quality).
      this.bridge.sendIntent({
        type: 'merge_stacks',
        kind: source.kind,
        quality: (source.quality ?? 'normal') as ItemQuality,
      });
      return;
    }

    // Anderer kind → lokal swappen (Slot-Positionen tauschen).
    this._swapSlotPositions(source.id, target.item.id);
  }

  // ─── Helpers ─────────────────────────────────────────────────────────
  private _readPayload(ev: DragEvent): DragPayload | null {
    try {
      const raw = ev.dataTransfer?.getData(DND_MIME);
      if (!raw) return null;
      const parsed: unknown = JSON.parse(raw);
      if (
        parsed &&
        typeof parsed === 'object' &&
        'from' in parsed &&
        'item_id' in parsed &&
        typeof (parsed as { item_id: unknown }).item_id === 'number'
      ) {
        return parsed as DragPayload;
      }
    } catch {
      // ignore
    }
    return null;
  }

  private _qualityClass(quality: string | undefined): string | null {
    if (!quality || quality === 'normal') return null;
    return quality; // rough/fine/masterwork/legendary
  }

  /** Berechnet den Stack-Füll-Zustand für die Border-/Badge-Tints. */
  private _stackFill(item: InventoryItem, category: string): StackFill {
    if (!STACKABLE_CATEGORIES.has(category)) return 'normal';
    const limit = STACK_LIMITS[category];
    if (!limit) return 'normal';
    const qty = item.quantity ?? 1;
    if (qty >= limit) return 'full';
    if (qty / limit > 0.8) return 'warn';
    return 'normal';
  }

  /** Tauscht die lokalen Slot-Positionen zweier Items + persistiert. */
  private _swapSlotPositions(aId: number, bId: number): void {
    // Sicherstellen, dass alle aktuell sichtbaren Items eine konkrete Position
    // haben, sonst „rutscht“ der Tausch durch den `MAX_SAFE_INTEGER`-Fallback
    // nicht stabil. Wir bilden die sichtbare Reihenfolge auf 0..n ab.
    const visible = this.bagItems();
    const order: Record<number, number> = {};
    visible.forEach((slot, idx) => { order[slot.item.id] = idx; });
    const ai = order[aId];
    const bi = order[bId];
    if (ai === undefined || bi === undefined) return;
    order[aId] = bi;
    order[bId] = ai;
    this.slotOrder.set(order);
    this._persistSlotOrder(order);
  }

  private _loadSlotOrder(): Readonly<Record<number, number>> {
    if (typeof localStorage === 'undefined') return {};
    try {
      const raw = localStorage.getItem(LS_ORDER_KEY);
      if (!raw) return {};
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const out: Record<number, number> = {};
        for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
          const id = Number(k);
          if (Number.isFinite(id) && typeof v === 'number' && Number.isFinite(v)) {
            out[id] = v;
          }
        }
        return out;
      }
    } catch {
      // ignore parse errors — wir fallen auf leeres Mapping zurück.
    }
    return {};
  }

  private _persistSlotOrder(order: Record<number, number>): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(LS_ORDER_KEY, JSON.stringify(order));
    } catch {
      // Quota oder Privacy-Mode → leise ignorieren, Order lebt im Signal weiter.
    }
  }

  // Template-Helfer: payload-Form erzeugen ohne Closure-Allocs im HTML.
  bagPayload(item: InventoryItem): DragPayload {
    return { from: 'bag', item_id: item.id };
  }
  equipPayload(item: InventoryItem): DragPayload {
    return { from: 'equip', item_id: item.id };
  }
}
