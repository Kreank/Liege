// FactionsComponent — Reputation-Anzeige pro Faktion.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 196-204 (`#factions-overlay`).
//   • Renderer:   `app.js` `refreshFactionsUI`, `toggleFactions`
//                 (Z. ~7260-7305).
//   • Styles:     `style.css` Z. 418-452.
//
// Backend liefert `factions`-Signal (FactionReputation[]: faction_id,
// goodwill, tier?). Goodwill ist im Legacy als -100..+100 skaliert
// (bar-pct = abs(goodwill)/2). Tier-Strings: hostile/unfriendly/neutral/
// friendly/allied — wenn vorhanden direkt verwenden, sonst aus Goodwill
// ableiten (Legacy-Heuristik).
//
// Read-only — keine Intents.
//
// Tastatur: `F` toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { FactionReputation } from '../../core/models/quest.model';
import { GameStateService } from '../../core/services/game-state.service';

type Tier = 'hostile' | 'unfriendly' | 'neutral' | 'friendly' | 'allied';

const TIER_LABEL: Readonly<Record<Tier, string>> = {
  hostile:    'Feindlich',
  unfriendly: 'Unfreundlich',
  neutral:    'Neutral',
  friendly:   'Freundlich',
  allied:     'Verbündet',
};

interface FactionRow {
  readonly faction_id: string;
  readonly displayName: string;
  readonly goodwill: number;
  readonly tier: Tier;
  readonly tierLabel: string;
  /** 0..100 Bar-Fill auf Plus- bzw. Minus-Seite. */
  readonly barPct: number;
  readonly positive: boolean;
}

@Component({
  selector: 'app-factions',
  standalone: true,
  templateUrl: './factions.component.html',
  styleUrl: './factions.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FactionsComponent {
  private readonly state = inject(GameStateService);

  readonly visible = signal<boolean>(false);

  readonly rows = computed<readonly FactionRow[]>(() =>
    this.state.factions().map((f) => this._toRow(f)),
  );

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'f' || ev.key === 'F') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  private _toRow(f: FactionReputation): FactionRow {
    const tier: Tier = this._resolveTier(f.tier, f.goodwill);
    const clamped = Math.max(-100, Math.min(100, f.goodwill));
    return {
      faction_id: f.faction_id,
      displayName: f.name?.trim() ? f.name : this._displayName(f.faction_id),
      goodwill: f.goodwill,
      tier,
      tierLabel: TIER_LABEL[tier],
      barPct: Math.abs(clamped) / 2,
      positive: clamped >= 0,
    };
  }

  private _resolveTier(tier: string | undefined, goodwill: number): Tier {
    if (tier && ['hostile', 'unfriendly', 'neutral', 'friendly', 'allied'].includes(tier)) {
      return tier as Tier;
    }
    // Legacy-Heuristik: 5-stufige Skala bezogen auf -100..+100.
    if (goodwill >= 60)  return 'allied';
    if (goodwill >= 20)  return 'friendly';
    if (goodwill > -20)  return 'neutral';
    if (goodwill > -60)  return 'unfriendly';
    return 'hostile';
  }

  /** Faction-IDs sind snake_case (`village_guard`, `mage_guild`); wir
   *  ersetzen `_` durch Leerzeichen und kapitalisieren — primitives
   *  Display, das in F-final durch ein vom Backend geliefertes `name`
   *  ersetzt wird. */
  private _displayName(id: string | undefined | null): string {
    // Defensiv: fehlende/leere ID darf NICHT werfen (sonst crasht das
    // `rows`-computed und reißt die Change-Detection mit → UI friert ein).
    if (!id) return 'Unbekannt';
    return id
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  }
}
