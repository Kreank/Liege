// CraftingComponent — Werkbank / Schmelze / Amboss / Hand-Crafting.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 303-315.
//   • Renderer: `app.js` `openCrafting`, `closeCrafting`, `refreshCraftingUI`
//                 (~6332-6450 — Category-Tabs, Recipe-Rows).
//
// Backend:
//   • `crafting_open { station, recipes }` öffnet das Modal.
//   • Hand-Crafting öffnet der Spieler aktiv per `open_hand_crafting`.
//   • `craft { output, station }` produziert ein Item / Bill.
//
// Scope: Wir migrieren das Grundgerüst (Station-Label, Recipe-Grid,
// Klick-Action). Das volle Category-Tab-System + Research-Gate (Welle 22)
// + Bills-Section gehören:
//   • Tabs/Subcats → Cleanup-Phase nach F-final (Verhaltenserhaltend
//     genug für jetzt — Backend filtert Rezepte sowieso bereits).
//   • Bills-Section → eigene BillsComponent in F-extras-2.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  effect,
  inject,
} from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { BillsComponent } from '../bills/bills.component';

const STATION_LABEL: Readonly<Record<string, string>> = {
  workbench: 'Werkbank',
  furnace:   'Schmelze',
  anvil:     'Amboss',
  hand:      '🛠 Handwerken',
};

@Component({
  selector: 'app-crafting',
  standalone: true,
  imports: [BillsComponent],
  templateUrl: './crafting.component.html',
  styleUrl: './crafting.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CraftingComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly crafting = computed(() => this.state.activeCrafting());
  readonly visible = computed<boolean>(() => this.crafting() !== null);

  readonly stationLabel = computed<string>(() => {
    const c = this.crafting();
    if (!c) return '';
    return STATION_LABEL[c.station] ?? c.station;
  });

  constructor() {
    // Beim Öffnen einer Crafting-Station fragen wir frische Bills an
    // (Legacy frontend/legacy/app.js Z. 6343 — `list_bills` im openCrafting).
    // Verfolgt nur Station-Wechsel; ein erneutes Open derselben Station
    // schickt erneut, das ist auch das Legacy-Verhalten.
    let lastStation: string | null = null;
    effect(() => {
      const c = this.crafting();
      const station = c?.station ?? null;
      if (station && station !== lastStation) {
        this.ws.send({ type: 'list_bills', station_type: station });
      }
      lastStation = station;
    });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.visible()) this.close(); }

  /**
   * H2.19 — Hand-Crafting-Hotkey „H". Öffnet das Crafting-Modal mit
   * Station=`hand` (alle Hand-Rezepte). Backend antwortet mit `crafting_open
   * {station:'hand', recipes:[...]}`, GameState setzt `activeCrafting`.
   *
   * Wird auch ausgelöst, wenn das Modal bereits offen ist: dann sendet wir
   * erneut und das Modal aktualisiert sich auf Station=hand (toggelt also
   * von Werkbank/Ofen/Amboss → Hand, wenn man das will).
   *
   * Hotkey-Konflikt-Check: `H` ist nicht in der Bestiary/Skills/Talents-
   * Mapping belegt; Chronik nutzt `J` (Journal) — siehe ai_fragen 2026-05-31.
   */
  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'h' || ev.key === 'H') {
      ev.preventDefault();
      this.ws.send({ type: 'open_hand_crafting' });
    }
  }

  /**
   * H2.20 — Recipe-Lock-Tooltip-Text. Liefert einen erklärenden String, wenn
   * das Rezept eine `requires`-Vorbedingung trägt (z. B. Research-Node oder
   * Skill-Level). Backend-Convention (siehe crafting.py): `requires`-String
   * ist entweder ein Research-Node-Slug (`steel_smelting`) oder ein
   * Skill-Lock (`skill:forging:5`). Wir parsen beides best-effort.
   *
   * Leerer String → kein Lock → kein Tooltip-Render.
   */
  lockTooltip(req: string | null | undefined): string {
    if (!req) return '';
    // Skill-Lock-Format: `skill:<skill_name>:<level>` (z. B. `skill:forging:5`).
    const skillMatch = /^skill:([a-z_]+):(\d+)$/i.exec(req);
    if (skillMatch) {
      return `🔒 Skill ${this._capitalize(skillMatch[1])} Level ${skillMatch[2]}`;
    }
    // Research-Lock — Slug in Klartext „titlecasen".
    return `🔬 Forschung benötigt: ${this._humanizeSlug(req)}`;
  }

  private _capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  private _humanizeSlug(slug: string): string {
    return slug.split(/[_\-]/).map((p) => this._capitalize(p)).join(' ');
  }

  close(): void { this.state.closeCrafting(); }

  craft(output: string): void {
    const c = this.crafting();
    if (!c) return;
    this.ws.send({ type: 'craft', output, station: c.station });
  }

  /** ×5-Auftrag erzeugen (Legacy „bill-btn"). */
  addBill(output: string, count: number): void {
    const c = this.crafting();
    if (!c) return;
    this.ws.send({
      type: 'add_bill',
      station_type: c.station,
      recipe_id: output,
      count,
    });
  }
}
