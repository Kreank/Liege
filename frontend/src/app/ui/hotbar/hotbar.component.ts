// HotbarComponent — 9-Slot-Aktionsleiste am unteren Bildschirmrand.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 115 (`#hotbar`).
//   • Renderer:   `app.js` `_loadHotbar`, `refreshHotbar`,
//                 `activateHotbarSlot` (Z. ~3767-4028).
//   • Tastatur:   `app.js` Z. ~3265-3275 (Keys 1-9 → activateHotbarSlot).
//   • Styles:     `style.css` Z. 227-265 (#hotbar + .hotbar-slot).
//
// Persistenz: localStorage-Key `liege_hotbar` (9 Slots, kind-String oder
// null). Identisches Format wie Legacy — Bestandsdaten bleiben lesbar.
//
// Intents:
//   • equip_item  / unequip_item    (Toggle für Equippables)
//   • use_item                       (Consumable / Food / Magic via Item)
//
// Drag-Drop (Welle F-extras-4):
//   • Inventar-Item → Hotbar-Slot: Inventar sendet Mime `application/json`
//     mit `{from:'bag', item_id}` (siehe `inventory.component.ts`). Wir
//     lösen den `kind` aus `state.inventory()` per item_id auf und
//     belegen den Slot. Persist nach localStorage.
//   • Hotbar-Slot → Hotbar-Slot: eigener Mime `application/x-liege-hotbar`
//     mit `{fromSlotIdx}` — wir tauschen die zwei Slots.
//   • Hotbar-Slot → außerhalb (z. B. Phaser-Canvas): `dragend` prüft
//     `dropEffect === 'none'` → Slot leeren.
//   • Right-Click auf Slot: direkt leeren + Toast.
//
// Spell-Slot-Hook (Welle 25 / F13):
//   `slot.kind` kann später auch eine Spell-ID sein. Der Use-Handler muss
//   dann `cast_spell {spell_id: slot.kind}` statt `use_item` senden.
//   Der Resolver würde Spells über `state.spells().learned` finden statt
//   über `state.inventory()`. Aktuell nicht implementiert — siehe
//   `_resolveSpellOrItem` für die Stelle, an der das später ansetzt.
//
// Cooldown-Hook (Welle G4):
//   `cooldownsRemaining` Map<string, number> (kind → Sekunden) ist der
//   Anker, an dem ein Cast-Bar/Cooldown-Overlay später andocken kann.
//   Aktuell leer; Template rendert nichts, solange der Eintrag fehlt.
//
// User-Feedback ohne dedizierten Toast-Service: wir nutzen
// `state.appendChat({kind:'system', text})` als Logline (gleiches Muster
// wie `ui/research/`, `ui/chat/`).

import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  HostListener,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';

import { ITEM } from '../../core/data/items';
import type { InventoryItem, ItemDef } from '../../core/models/item.model';
import type { SpellEntry } from '../../core/models/talent.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { TooltipService } from '../../core/services/tooltip.service';

const STORAGE_KEY = 'liege_hotbar';
const SLOT_COUNT = 9;

/** Mime-Type, den die Hotbar selbst beim internen Drag-Reorder schreibt. */
const HOTBAR_MIME = 'application/x-liege-hotbar';
/** Mime-Type, den das Inventar (`inventory.component.ts`) als Source nutzt. */
const INVENTORY_MIME = 'application/json';
/** Welle 53: Mime-Type, den das Spellbook beim Drag eines Zaubers schreibt. */
const SPELL_MIME = 'application/x-liege-spell';

/** Quality-Order für Tooltip-Sortierung — höhere Qualität priorisieren. */
const QR: Readonly<Record<string, number>> = {
  rough: 0, normal: 1, fine: 2, masterwork: 3, legendary: 4,
};

/** Inventar-Drag-Payload-Form (siehe `inventory.component.ts` DragPayload). */
interface InventoryDragPayload {
  readonly from: 'bag' | 'equip';
  readonly item_id: number;
}

/** Hotbar-interner Drag-Payload für Slot-Reorder. */
interface HotbarDragPayload {
  readonly fromSlotIdx: number;
}

interface HotbarSlotView {
  readonly index: number;
  readonly key: string;
  readonly kind: string | null;
  readonly def: ItemDef | null;
  /** Welle 53: Icon-Pfad — Item-Sprite ODER Spell-Icon (für Spell-Slots). */
  readonly iconPath: string | null;
  readonly count: number;
  readonly equipped: boolean;
  readonly active: boolean;
  /** „Slot belegt, aber kein Inventar-Item dahinter" → 50% Opacity. */
  readonly missing: boolean;
  /** True wenn der Slot komplett leer ist (kein kind zugewiesen). */
  readonly empty: boolean;
  readonly tooltip: string | null;
  /** Cooldown-Rest in Sekunden (Hook für Welle G4). */
  readonly cooldownRemaining: number;
  /** Vorformatierte Cooldown-Anzeige (z. B. „2.3"). */
  readonly cooldownLabel: string;
  /** H3.3 — Mana-Cost-Indicator. `null` wenn der Slot kein Spell zeigt,
   *  sonst die Kost und das Affordable-Flag. UI zeigt den Wert als kleines
   *  Badge unten links; bei `!affordable` rot getintet. */
  readonly manaCost: number | null;
  readonly manaAffordable: boolean;
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
  private readonly tooltip = inject(TooltipService);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    // H2.4 — RAF-Tick starten/stoppen je nach Spell-Cooldown-Aktivität.
    // Wir wollen nicht permanent ticken (CPU sparen), nur solange mindestens
    // ein laufender Cooldown im State steht.
    effect(() => {
      const cds = this.state.spellCooldowns();
      const now = Date.now();
      const hasActive = Array.from(cds.values()).some((endMs) => endMs > now);
      if (hasActive) this._startCdTicker();
      else this._stopCdTicker();
    });
    this.destroyRef.onDestroy(() => this._stopCdTicker());
  }

  private _startCdTicker(): void {
    if (this._cdRafId !== null) return;
    const loop = (): void => {
      this._cdTick.set(Date.now());
      // Eigene Live-Check, ob noch Cooldown läuft, sonst Loop beenden.
      const cds = this.state.spellCooldowns();
      const now = Date.now();
      const stillActive = Array.from(cds.values()).some((endMs) => endMs > now);
      if (stillActive) {
        this._cdRafId = requestAnimationFrame(loop);
      } else {
        this._cdRafId = null;
      }
    };
    this._cdRafId = requestAnimationFrame(loop);
  }

  private _stopCdTicker(): void {
    if (this._cdRafId !== null) {
      cancelAnimationFrame(this._cdRafId);
      this._cdRafId = null;
    }
  }

  /** Slot-Belegung (null = leer, sonst kind-String). */
  private readonly _slots = signal<readonly (string | null)[]>(this._loadFromStorage());
  /** Aktiver Slot (Highlight). */
  private readonly _activeIndex = signal<number>(0);

  /** Lokale Cooldown-Restzeiten pro kind (Sekunden) — bleibt als Hook
   *  bestehen, falls in Zukunft Item-Cooldowns (Healtränke etc.) kommen.
   *  Spell-Cooldowns leben separat im `GameStateService.spellCooldowns`
   *  als End-Timestamp-Map und werden weiter unten in `slots` gemischt. */
  readonly cooldownsRemaining = signal<ReadonlyMap<string, number>>(new Map());

  /** RAF-Tick für Live-Update der Spell-Cooldown-Anzeige. Wir tickern nur,
   *  solange mindestens ein Cooldown läuft (siehe Effect im Konstruktor),
   *  um CPU bei leerem State zu sparen. */
  private readonly _cdTick = signal<number>(Date.now());
  private _cdRafId: number | null = null;

  readonly slots = computed<readonly HotbarSlotView[]>(() => {
    const slots = this._slots();
    const inv = this.state.inventory();
    const active = this._activeIndex();
    const cooldowns = this.cooldownsRemaining();
    // Spell-Cooldowns aus GameState — Map<spell_id, endMs>. Hotbar-Slot mit
    // `kind === spell_id` rendert den Rest als Sekunden.
    const spellCds = this.state.spellCooldowns();
    void this._cdTick(); // Reactivity-Anker: ticker triggert Re-Compute.
    const now = Date.now();

    // H3.3 — Spell-Catalog für Mana-Cost-Lookup. Map<spell_id, mana_cost>.
    // Backend liefert `spells.catalog` aus `init.spell_catalog`, das fast
    // immer wenige Dutzend Einträge hat — die Map ist günstig pro Re-Compute.
    const spellsState = this.state.spells();
    const spellManaCosts = new Map<string, number>();
    const spellById = new Map<string, SpellEntry>();
    for (const sp of spellsState.catalog) {
      spellById.set(sp.id, sp);
      if (typeof sp.mana_cost === 'number') {
        spellManaCosts.set(sp.id, sp.mana_cost);
      }
    }
    const curMana = this.state.player()?.mana ?? 0;

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
      // Welle 53: Spell-Slot (kein Item-Def, aber im Spell-Catalog).
      const spellEntry = kind && !def ? spellById.get(kind) ?? null : null;
      const cnt = kind ? counts[kind] ?? 0 : 0;
      const equipped = kind ? inv.some((it) => it.kind === kind && !!it.equipped_slot) : false;
      const empty = !kind;
      // Spells sind nie „missing" (sie liegen nicht im Inventar).
      const missing = !!kind && !spellEntry && cnt === 0 && !equipped;
      const iconPath = def?.path ?? spellEntry?.icon_path ?? null;
      // H3.3 — Mana-Cost: nur wenn der Slot kein Item-Def hat (Spells haben
      // keinen ITEM-Eintrag, sondern leben im Spell-Catalog).
      const manaCost = kind && !def ? spellManaCosts.get(kind) ?? null : null;
      const manaAffordable = manaCost == null || curMana >= manaCost;
      const tooltip = def
        ? `${def.name}${cnt > 0 ? ` (${cnt})` : ''}`
        : spellEntry
          ? `${spellEntry.name}${manaCost != null ? ` — ${manaCost} Mana` : ''}`
          : manaCost != null
            ? `Mana-Kost: ${manaCost}`
            : null;
      // Item-Cooldown (lokal) ODER Spell-Cooldown (aus GameState-End-Timestamp).
      let cd = kind ? cooldowns.get(kind) ?? 0 : 0;
      if (kind && cd <= 0) {
        const endMs = spellCds.get(kind);
        if (endMs && endMs > now) cd = (endMs - now) / 1000;
      }
      const cdLabel = cd > 0 ? (cd >= 10 ? Math.ceil(cd).toString() : cd.toFixed(1)) : '';
      views.push({
        index: i,
        key: String(i + 1),
        kind,
        def,
        iconPath,
        count: cnt,
        equipped,
        active: i === active,
        empty,
        missing,
        tooltip,
        cooldownRemaining: cd,
        cooldownLabel: cdLabel,
        manaCost,
        manaAffordable,
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

  // ─── Click / Hotkey-Handler ──────────────────────────────────────────
  activate(idx: number): void {
    if (idx < 0 || idx >= SLOT_COUNT) return;
    this._activeIndex.set(idx);
    const kind = this._slots()[idx];
    if (!kind) return; // No-op auf leerem Slot.

    // Welle 53 — Spell-Cast aus der Hotbar: hat `kind` keine Item-Definition,
    // ist es (potenziell) eine Spell-ID. Wenn gelernt → casten (self/group
    // direkt, zielende Zauber öffnen das Target-Overlay — wie im Spellbook).
    const def = ITEM[kind] ?? null;
    if (!def) {
      const sp = this.state.spells();
      const entry = sp.catalog.find((e) => e.id === kind);
      if (entry && sp.learned.includes(kind)) {
        const tk = entry.target_kind;
        if (tk === 'self' || tk === 'group' || tk === undefined) {
          this.bridge.sendIntent({ type: 'cast_spell', spell_id: kind });
        } else {
          this.state.beginSpellTargeting(entry);
        }
      } else if (entry) {
        this._notifyMissing(entry.name);   // bekannt, aber nicht gelernt
      }
      return;
    }

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
      } else {
        this._notifyMissing(def.name);
      }
      return;
    }
    // Consumable / Food / Magic → use_item auf erste freie Instance
    if (def.category === 'consumable' || def.category === 'food' || def.category === 'magic') {
      const free = inv.find((it) => it.kind === kind && !it.equipped_slot);
      if (free) {
        this.bridge.sendIntent({ type: 'use_item', item_id: free.id });
      } else {
        this._notifyMissing(def.name);
      }
    }
  }

  /** Rechtsklick → Slot leeren + Toast. */
  clearSlot(idx: number, ev: MouseEvent): void {
    ev.preventDefault();
    if (idx < 0 || idx >= SLOT_COUNT) return;
    const slots = this._slots();
    if (!slots[idx]) return; // war eh leer
    const next = slots.slice();
    next[idx] = null;
    this._slots.set(next);
    this._saveToStorage(next);
    this.state.appendChat({
      kind: 'system',
      text: `Slot ${idx + 1} geleert.`,
    });
  }

  // ─── Drag-Drop ───────────────────────────────────────────────────────

  /** Source: Slot wird gegriffen. Wir schreiben unseren Mime. */
  onSlotDragStart(ev: DragEvent, idx: number): void {
    const kind = this._slots()[idx];
    if (!kind || !ev.dataTransfer) {
      ev.preventDefault();
      return;
    }
    const payload: HotbarDragPayload = { fromSlotIdx: idx };
    ev.dataTransfer.setData(HOTBAR_MIME, JSON.stringify(payload));
    ev.dataTransfer.effectAllowed = 'move';
  }

  /** Target: ermöglicht Drop. */
  onSlotDragOver(ev: DragEvent): void {
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
  }

  /** Target: Drop auf Slot — entweder Inventory-Assign oder Hotbar-Reorder. */
  onSlotDrop(ev: DragEvent, idx: number): void {
    ev.preventDefault();
    if (!ev.dataTransfer) return;

    // Hotbar-intern hat Vorrang (eigener Mime).
    const hotbarRaw = ev.dataTransfer.getData(HOTBAR_MIME);
    if (hotbarRaw) {
      const hp = this._parseHotbarPayload(hotbarRaw);
      if (hp && hp.fromSlotIdx !== idx) {
        this._swapSlots(hp.fromSlotIdx, idx);
      }
      return;
    }

    // Welle 53 — Spell aus dem Spellbook zugewiesen: Slot trägt dann die
    // Spell-ID (activate() castet sie). _assignSlot speichert nur den String.
    const spellRaw = ev.dataTransfer.getData(SPELL_MIME);
    if (spellRaw) {
      this._assignSlot(idx, spellRaw);
      return;
    }

    // Inventory-Drag.
    const invRaw = ev.dataTransfer.getData(INVENTORY_MIME);
    if (invRaw) {
      const ip = this._parseInventoryPayload(invRaw);
      if (!ip) return;
      // Resolve kind über item_id im aktuellen Inventory.
      const item = this.state.inventory().find((it) => it.id === ip.item_id);
      if (!item) return;
      this._assignSlot(idx, item.kind);
    }
  }

  /** Nach jedem Slot-Drag prüfen, ob außerhalb gedroppt wurde → Slot
   *  leeren. `dropEffect === 'none'` heißt: kein gültiges Target hat
   *  akzeptiert. */
  onSlotDragEnd(ev: DragEvent, idx: number): void {
    if (!ev.dataTransfer) return;
    if (ev.dataTransfer.dropEffect === 'none') {
      const slots = this._slots();
      if (!slots[idx]) return;
      const next = slots.slice();
      next[idx] = null;
      this._slots.set(next);
      this._saveToStorage(next);
      this.state.appendChat({
        kind: 'system',
        text: `Slot ${idx + 1} entfernt.`,
      });
    }
  }

  // ─── Tooltip-Hover ───────────────────────────────────────────────────

  showSlotTooltip(slot: HotbarSlotView, ev: MouseEvent): void {
    if (!slot.kind || !slot.def) return; // Leerer Slot → kein Tooltip.
    // Bevorzugt eine echte Inventory-Instance (mit quality/affixes),
    // damit der Tooltip-Service die volle Item-Form bekommt.
    const inv = this.state.inventory();
    const inst = inv.find((it) => it.kind === slot.kind && !it.equipped_slot)
      ?? inv.find((it) => it.kind === slot.kind)
      ?? null;
    if (inst) {
      this.tooltip.show(inst, ev.clientX, ev.clientY);
      return;
    }
    // Synthetic-Item — Slot ist „leer aber zugewiesen". Tooltip-Service
    // akzeptiert auch TooltipItem-Pick-Schnitt.
    this.tooltip.show(
      {
        kind: slot.kind,
        name: slot.def.name,
        category: slot.def.category,
      },
      ev.clientX,
      ev.clientY,
    );
  }
  moveTooltip(ev: MouseEvent): void { this.tooltip.move(ev.clientX, ev.clientY); }
  hideTooltip(): void { this.tooltip.hide(); }

  // ─── Internals ───────────────────────────────────────────────────────

  private _assignSlot(idx: number, kind: string): void {
    if (idx < 0 || idx >= SLOT_COUNT) return;
    const next = this._slots().slice();
    next[idx] = kind;
    this._slots.set(next);
    this._saveToStorage(next);
  }

  private _swapSlots(a: number, b: number): void {
    if (a === b) return;
    if (a < 0 || a >= SLOT_COUNT || b < 0 || b >= SLOT_COUNT) return;
    const next = this._slots().slice();
    const tmp = next[a] ?? null;
    next[a] = next[b] ?? null;
    next[b] = tmp;
    this._slots.set(next);
    this._saveToStorage(next);
  }

  private _notifyMissing(name: string): void {
    this.state.appendChat({
      kind: 'system',
      text: `Keine ${name} im Inventar.`,
    });
  }

  private _parseHotbarPayload(raw: string): HotbarDragPayload | null {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (
        parsed && typeof parsed === 'object' &&
        'fromSlotIdx' in parsed &&
        typeof (parsed as { fromSlotIdx: unknown }).fromSlotIdx === 'number'
      ) {
        const idx = (parsed as { fromSlotIdx: number }).fromSlotIdx;
        if (Number.isInteger(idx) && idx >= 0 && idx < SLOT_COUNT) {
          return { fromSlotIdx: idx };
        }
      }
    } catch {
      // ignore
    }
    return null;
  }

  private _parseInventoryPayload(raw: string): InventoryDragPayload | null {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (
        parsed && typeof parsed === 'object' &&
        'from' in parsed && 'item_id' in parsed &&
        typeof (parsed as { item_id: unknown }).item_id === 'number'
      ) {
        const p = parsed as { from: unknown; item_id: number };
        if (p.from === 'bag' || p.from === 'equip') {
          return { from: p.from, item_id: p.item_id };
        }
      }
    } catch {
      // ignore
    }
    return null;
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
    return sorted[0] ?? null;
  }
}
