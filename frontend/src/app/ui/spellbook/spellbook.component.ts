// SpellbookComponent — Zauberbuch mit Schulen-Tabs (Healer/Mage).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 131-145 (`#spellbook-overlay`).
//   • Renderer: `app.js` `toggleSpellbook`, `_refreshSpellbook`
//                 (Z. ~4167-4222).
//   • Styles:  `style.css` Z. 325-377.
//
// Read-only — keine Intents. (Cast erfolgt aus der Hotbar via `cast_learned`,
// das in F6 bereits zugängliche Bindung läuft.) Drag-Drop von Spells in die
// Hotbar bleibt vorerst eine F-final-Sache; das Spellbook zeigt nur Status
// + Detail-Beschreibung.
//
// Tastatur: `P` toggelt, `Esc` schließt (siehe Legacy Z. 3286 + 3327).

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { SpellEntry, SpellSchool } from '../../core/models/talent.model';
import { GameStateService } from '../../core/services/game-state.service';

interface SpellTile {
  readonly id: string;
  readonly name: string;
  readonly icon: string | null;
  readonly skillReq: number;
  readonly learned: boolean;
  readonly meetsReq: boolean;
  readonly locked: boolean;
  readonly entry: SpellEntry;
}

interface DetailRow {
  readonly title: string;
  readonly description: string;
  readonly meta: string;
}

const SCHOOL_LABEL: Readonly<Record<SpellSchool, string>> = {
  healer: '⚕ Heiler',
  mage:   '🔥 Magier',
};

const SCHOOLS: readonly SpellSchool[] = ['healer', 'mage'];

@Component({
  selector: 'app-spellbook',
  standalone: true,
  templateUrl: './spellbook.component.html',
  styleUrl: './spellbook.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpellbookComponent {
  private readonly state = inject(GameStateService);

  readonly schools = SCHOOLS.map((s) => ({ id: s, label: SCHOOL_LABEL[s] }));
  readonly visible = signal<boolean>(false);
  readonly school = signal<SpellSchool>('healer');
  readonly selectedDetail = signal<DetailRow | null>(null);

  readonly tiles = computed<readonly SpellTile[]>(() => {
    const spells = this.state.spells();
    const magicLvl = this._magicLevel();
    const cur = this.school();
    return spells.catalog
      .filter((s) => s.school === cur)
      .map((s) => {
        const learned = spells.learned.includes(s.id);
        const meetsReq = magicLvl >= (s.skill_req ?? 0);
        return {
          id: s.id,
          name: s.name,
          icon: s.icon_path ?? null,
          skillReq: s.skill_req ?? 0,
          learned,
          meetsReq,
          locked: !learned || !meetsReq,
          entry: s,
        };
      });
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'p' || ev.key === 'P') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  selectSchool(s: SpellSchool): void {
    this.school.set(s);
    this.selectedDetail.set(null);
  }

  pickTile(tile: SpellTile): void {
    const e = tile.entry;
    const cast = ((e.cast_time_ms ?? 0) / 1000).toFixed(1);
    const cd = ((e.cooldown_ms ?? 0) / 1000).toFixed(1);
    this.selectedDetail.set({
      title: e.name,
      description: e.description ?? '',
      meta: `Mana ${e.mana_cost ?? 0} · Cast ${cast}s · Abklingzeit ${cd}s · Magie-Level ${e.skill_req ?? 0}`,
    });
  }

  private _magicLevel(): number {
    const p = this.state.player();
    return p?.skills?.['magic']?.level ?? 0;
  }
}
