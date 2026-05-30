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
//   • split_stack                  { item_id, quantity }
//
// Drag-Drop: Inv-Slot → Equip-Slot löst `equip_item` aus; Equip-Slot →
// Inv löst `unequip_item` aus. Inv-Slot → Inv-Slot ist reine UI-Reorder
// und wird in F-final mit Persistenz nachgeholt — F7 hält Reorder rein
// als optisches Feedback (kein Server-Roundtrip).

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
} from '../../core/models/item.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { TooltipService } from '../../core/services/tooltip.service';

/** Welche Slots werden in der Equip-Grid angezeigt (Reihenfolge = Legacy). */
const EQUIP_SLOT_ORDER: readonly EquipSlot[] = EQUIP_SLOTS.map((s) => s.key);

interface InventoryGridSlot {
  readonly item: InventoryItem;
  readonly def: ItemDef | null;
  readonly qualityClass: string | null;
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

  /** Items im Beutel (nicht equipped). */
  readonly bagItems = computed<readonly InventoryGridSlot[]>(() =>
    this.state
      .inventory()
      .filter((it) => !it.equipped_slot)
      .map((it) => ({
        item: it,
        def: ITEM[it.kind] ?? null,
        qualityClass: this._qualityClass(it.quality),
      })),
  );

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
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  // ─── Actions ─────────────────────────────────────────────────────────
  close(): void { this.visible.set(false); }

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
    if (def.category === 'consumable' || def.category === 'food' || def.category === 'magic') {
      this.bridge.sendIntent({ type: 'use_item', item_id: item.id });
    }
  }

  dropItem(item: InventoryItem, ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    this.bridge.sendIntent({ type: 'drop_item', item_id: item.id });
  }

  splitStack(item: InventoryItem, ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    const total = item.quantity ?? 1;
    if (total <= 1) return;
    const half = Math.floor(total / 2);
    if (half < 1) return;
    this.bridge.sendIntent({ type: 'split_stack', item_id: item.id, quantity: half });
  }

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
  onDropEquip(ev: DragEvent, slot: EquipSlot): void {
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

  /** Drop auf den Beutel-Bereich — equipped Item ablegen. */
  onDropBag(ev: DragEvent): void {
    ev.preventDefault();
    const payload = this._readPayload(ev);
    if (!payload) return;
    if (payload.from === 'equip') {
      this.bridge.sendIntent({ type: 'unequip_item', item_id: payload.item_id });
    }
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

  // Template-Helfer: payload-Form erzeugen ohne Closure-Allocs im HTML.
  bagPayload(item: InventoryItem): DragPayload {
    return { from: 'bag', item_id: item.id };
  }
  equipPayload(item: InventoryItem): DragPayload {
    return { from: 'equip', item_id: item.id };
  }
}
