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
//   • `craft { recipe_id, station }` produziert ein Item (recipe_id = Rezept-`id`,
//     z. B. `wooden_sword` — NICHT der `output`, da mehrere Rezepte denselben
//     Output liefern).
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

import { ITEM } from '../../core/data/items';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { BillsComponent } from '../bills/bills.component';

const STATION_LABEL: Readonly<Record<string, string>> = {
  workbench: 'Werkbank',
  furnace:   'Schmelze',
  anvil:     'Amboss',
  hand:      '🛠 Handwerken',
};

/** Anzeige-Labels + Reihenfolge der Rezept-Kategorien (Backend-Slugs aus
 *  recipes.py). Reihenfolge bestimmt die Sektions-Abfolge im Grid. */
const CATEGORY_LABEL: Readonly<Record<string, string>> = {
  weapon:     '⚔️ Waffen',
  armor:      '🛡 Rüstung',
  tool:       '🔧 Werkzeuge',
  jewelry:    '💍 Schmuck',
  consumable: '🧪 Verbrauchbares',
  food:       '🍖 Nahrung',
  material:   '🧱 Material',
  magic:      '✨ Magie',
};
const CATEGORY_ORDER: readonly string[] = [
  'weapon', 'armor', 'tool', 'jewelry', 'consumable', 'food', 'material', 'magic',
];

/** Ein einzelnes Rezept, wie es das Backend (`crafting_open`) liefert. */
interface CraftRecipe {
  readonly id: string;
  readonly name?: string;
  readonly output: string;
  readonly category?: string;
  readonly requires?: string | null;
  readonly inputs: readonly { readonly kind: string; readonly quantity: number }[];
}

/** Eine Kategorie-Sektion fürs gruppierte Grid. */
interface RecipeGroup {
  readonly cat: string;
  readonly label: string;
  readonly recipes: readonly CraftRecipe[];
}

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

  /** Rezepte nach Kategorie gruppiert — fürs kategorisierte Grid (Vorbild:
   *  Forschungs-Panel). Bekannte Kategorien folgen CATEGORY_ORDER, unbekannte
   *  landen alphabetisch dahinter. */
  readonly groupedRecipes = computed<readonly RecipeGroup[]>(() => {
    const c = this.crafting();
    if (!c) return [];
    const groups = new Map<string, CraftRecipe[]>();
    for (const r of c.recipes as readonly CraftRecipe[]) {
      const cat = r.category ?? 'other';
      const arr = groups.get(cat);
      if (arr) arr.push(r);
      else groups.set(cat, [r]);
    }
    const rank = (cat: string): number => {
      const i = CATEGORY_ORDER.indexOf(cat);
      return i === -1 ? CATEGORY_ORDER.length : i;
    };
    return [...groups.entries()]
      .sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0]))
      .map(([cat, recipes]) => ({
        cat,
        label: CATEGORY_LABEL[cat] ?? this._humanizeSlug(cat),
        recipes,
      }));
  });

  /** Anzeige-Name eines Rezepts: bevorzugt den Backend-`name` (z. B.
   *  „Holzschwert"), sonst der humanisierte `output`-Slug als Fallback. */
  recipeName(r: CraftRecipe): string {
    return r.name ?? this._humanizeSlug(r.output);
  }

  /** Icon-Pfad des Output-Items (für die Rezept-Karte). null → kein Icon. */
  iconPath(r: CraftRecipe): string | null {
    return ITEM[r.output]?.path ?? null;
  }

  /** Lesbarer Material-Name für einen Input-Kind (z. B. „Holz" statt „wood"). */
  matName(kind: string): string {
    return ITEM[kind]?.name ?? this._humanizeSlug(kind);
  }

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

  craft(recipeId: string): void {
    const c = this.crafting();
    if (!c) return;
    // Backend (handle_craft) matcht auf die Rezept-`id` (z.B. `wooden_sword`),
    // NICHT auf `output` — mehrere Rezepte teilen sich denselben Output (sword).
    this.ws.send({ type: 'craft', recipe_id: recipeId, station: c.station });
  }

  /** ×5-Auftrag erzeugen (Legacy „bill-btn"). */
  addBill(recipeId: string, count: number): void {
    const c = this.crafting();
    if (!c) return;
    this.ws.send({
      type: 'add_bill',
      station_type: c.station,
      recipe_id: recipeId,
      count,
    });
  }
}
