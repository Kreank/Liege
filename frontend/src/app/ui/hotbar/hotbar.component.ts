// HotbarComponent — 9-Slot-Aktionsleiste am unteren Bildschirmrand.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 115 (`#hotbar`).
//   • Renderer:   `app.js` `_loadHotbar`, `refreshHotbar`,
//                 `activateHotbarSlot` (Z. ~3767-4028).
//   • Tastatur:   `app.js` Z. ~3265-3275 (Keys 1-9 → activateHotbarSlot).
//   • Styles:     `style.css` Z. 227-265 (#hotbar + .hotbar-slot).
//
// Welle 25 Spell-Slots (Spellbook → Hotbar) sind bewusst NICHT in F6
// migriert — Spellbook/Cast-Bar kommt in F13, dann erweitern wir die
// Hotbar um Spell-Slots. Notiert in REFACTOR_NOTES §F6.
//
// Persistenz: localStorage-Key `liege_hotbar` (9 Slots, kind-String oder
// null). Identisches Format wie Legacy — Bestandsdaten bleiben lesbar.
//
// Intents:
//   • equip_item  / unequip_item    (Toggle für Equippables)
//   • use_item                       (Consumable / Food / Magic via Item)
// Drag-Drop und Spell-Cast-CD bleiben F-final (siehe Notes).

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import { ITEM } from '../../core/data/items';
import type { InventoryItem, ItemDef } from '../../core/models/item.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

const STORAGE_KEY = 'liege_hotbar';
const SLOT_COUNT = 9;

/** Quality-Order für Tooltip-Sortierung — höhere Qualität priorisieren. */
const QR: Readonly<Record<string, number>> = {
  rough: 0, normal: 1, fine: 2, masterwork: 3, legendary: 4,
};

interface HotbarSlotView {
  readonly index: number;
  readonly key: string;
  readonly kind: string | null;
  readonly def: ItemDef | null;
  readonly count: number;
  readonly equipped: boolean;
  readonly active: boolean;
  readonly empty: boolean;
  readonly tooltip: string | null;
}

@Component({
  selector: 'app-hotbar',
  standalone: true,
  templateUrl: './hotbar.component.html',
  styleUrl: './hotbar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HotbarComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);

  /** Slot-Belegung (null = leer, sonst kind-String). */
  private readonly _slots = signal<readonly (string | null)[]>(this._loadFromStorage());
  /** Aktiver Slot (Highlight). */
  private readonly _activeIndex = signal<number>(0);

  readonly slots = computed<readonly HotbarSlotView[]>(() => {
    const slots = this._slots();
    const inv = this.state.inventory();
    const active = this._activeIndex();

    // Counts pro kind, nur nicht-equipped zählen.
    const counts: Record<string, number> = {};
    for (const it of inv) {
      if (it.equipped_slot) continue;
      counts[it.kind] = (counts[it.kind] ?? 0) + 1;
    }

    const views: HotbarSlotView[] = [];
    for (let i = 0; i < SLOT_COUNT; i++) {
      const kind = slots[i] ?? null;
      const def = kind ? ITEM[kind] ?? null : null;
      const cnt = kind ? counts[kind] ?? 0 : 0;
      const equipped = kind ? inv.some((it) => it.kind === kind && !!it.equipped_slot) : false;
      const empty = !kind || (cnt === 0 && !equipped);
      const tooltip = def ? `${def.name}${cnt > 0 ? ` (${cnt})` : ''}` : null;
      views.push({
        index: i,
        key: String(i + 1),
        kind,
        def,
        count: cnt,
        equipped,
        active: i === active,
        empty,
        tooltip,
      });
    }
    return views;
  });

  // ─── Tastatur 1-9 ────────────────────────────────────────────────────
  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    // Wenn ein <input>/<textarea> fokussiert ist, nicht zu greifen.
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    const code = ev.key;
    if (code.length === 1 && code >= '1' && code <= '9') {
      const idx = Number(code) - 1;
      this.activate(idx);
      ev.preventDefault();
    }
  }

  // ─── Click-Handler ───────────────────────────────────────────────────
  activate(idx: number): void {
    if (idx < 0 || idx >= SLOT_COUNT) return;
    this._activeIndex.set(idx);
    const kind = this._slots()[idx];
    if (!kind) return;
    const def = ITEM[kind];
    if (!def) return;

    const inv = this.state.inventory();
    // Equippable → Toggle (equip wenn frei, sonst unequip)
    if (def.slot) {
      const equipped = inv.find((it) => it.kind === kind && !!it.equipped_slot);
      if (equipped) {
        this.bridge.sendIntent({ type: 'unequip_item', item_id: equipped.id });
        return;
      }
      const free = this._pickBestQuality(inv, kind);
      if (free) {
        this.bridge.sendIntent({ type: 'equip_item', item_id: free.id });
      }
      return;
    }
    // Consumable / Food / Magic → use_item auf erste freie Instance
    if (def.category === 'consumable' || def.category === 'food' || def.category === 'magic') {
      const free = inv.find((it) => it.kind === kind && !it.equipped_slot);
      if (free) this.bridge.sendIntent({ type: 'use_item', item_id: free.id });
    }
  }

  /** Rechtsklick → Slot leeren. */
  clearSlot(idx: number, ev: MouseEvent): void {
    ev.preventDefault();
    if (idx < 0 || idx >= SLOT_COUNT) return;
    const next = this._slots().slice();
    next[idx] = null;
    this._slots.set(next);
    this._saveToStorage(next);
  }

  // ─── Storage ─────────────────────────────────────────────────────────
  private _loadFromStorage(): readonly (string | null)[] {
    try {
      const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length === SLOT_COUNT) {
          return parsed.map((v) => (typeof v === 'string' ? v : null));
        }
      }
    } catch {
      // Storage nicht verfügbar / korrupt — leere Hotbar.
    }
    return new Array(SLOT_COUNT).fill(null);
  }

  private _saveToStorage(slots: readonly (string | null)[]): void {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(slots));
      }
    } catch {
      // ignore
    }
  }

  // ─── Helpers ─────────────────────────────────────────────────────────
  /** Beste-Qualität-Instance für Equip wählen (Legacy refreshHotbar-Logik). */
  private _pickBestQuality(inv: readonly InventoryItem[], kind: string): InventoryItem | null {
    const stack = inv.filter((it) => it.kind === kind && !it.equipped_slot);
    if (stack.length === 0) return null;
    const sorted = stack.slice().sort((a, b) => (QR[b.quality ?? 'normal'] ?? 0) - (QR[a.quality ?? 'normal'] ?? 0));
    return sorted[0];
  }
}
