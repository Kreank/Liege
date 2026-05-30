// CharacterComponent — Attribute-Allocation + Stat-Sheet.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 175-183 (`#attributes-overlay`).
//   • Renderer:   `app.js` `toggleAttributes`, `renderAttributes`,
//                 `_buildStatSheetSection`.
//   • Styles:     `style.css` Z. 198-224.
//
// Backend liefert:
//   • `attributes`-Signal (PlayerAttributes: strength, dexterity, ...,
//     unspent?).
//   • `stats`-Signal (PlayerStats: damage, defense, ...) — sekundär,
//     hier nur read-only angezeigt.
//
// Intent:
//   • allocate_attr { attr, n }   — n=+1 oder -1
//
// Tastatur: `C` toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { PlayerAttributes, PlayerStats } from '../../core/models/player.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

interface AttrRow {
  readonly key: keyof PlayerAttributes;
  readonly label: string;
  readonly desc: string;
  readonly value: number;
}

interface StatRow {
  readonly key: keyof PlayerStats;
  readonly label: string;
  readonly value: number | undefined;
}

const ATTR_META: ReadonlyArray<Omit<AttrRow, 'value'>> = [
  { key: 'strength',     label: '💪 Stärke',       desc: 'Schaden + Tragelast' },
  { key: 'dexterity',    label: '🎯 Geschick',     desc: 'Crit + Angriffstempo' },
  { key: 'intelligence', label: '🧠 Intelligenz',  desc: 'Manapool + Zauber' },
  { key: 'constitution', label: '❤️ Konstitution', desc: 'HP + Ausdauer' },
  { key: 'wisdom',       label: '🕯️ Weisheit',     desc: 'Mana-Regen + Resistenzen' },
  { key: 'charisma',     label: '🎭 Charisma',     desc: 'Preise + Quests' },
];

const STAT_META: ReadonlyArray<Omit<StatRow, 'value'>> = [
  { key: 'damage',       label: 'Schaden' },
  { key: 'defense',      label: 'Verteidigung' },
  { key: 'crit_chance',  label: 'Crit-Chance %' },
  { key: 'crit_damage',  label: 'Crit-Schaden %' },
  { key: 'attack_speed', label: 'Angriffstempo' },
  { key: 'move_speed',   label: 'Bewegungstempo' },
  { key: 'carry_weight', label: 'Tragelast' },
  { key: 'mana_regen',   label: 'Mana-Regen' },
  { key: 'hp_regen',     label: 'HP-Regen' },
];

@Component({
  selector: 'app-character',
  standalone: true,
  templateUrl: './character.component.html',
  styleUrl: './character.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);

  readonly visible = signal<boolean>(false);

  readonly attrs = computed<readonly AttrRow[]>(() => {
    const a: PlayerAttributes | null = this.state.attributes() ?? this.state.player()?.attributes ?? null;
    if (!a) return [];
    return ATTR_META.map((m) => ({ ...m, value: a[m.key] as number ?? 0 }));
  });

  readonly unspent = computed<number>(() => {
    const a = this.state.attributes() ?? this.state.player()?.attributes;
    return a?.unspent ?? 0;
  });

  readonly stats = computed<readonly StatRow[]>(() => {
    const s = this.state.stats() ?? this.state.player()?.stats ?? null;
    if (!s) return [];
    return STAT_META.map((m) => ({ ...m, value: s[m.key] as number | undefined }));
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'c' || ev.key === 'C') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  allocate(row: AttrRow, n: number): void {
    if (n > 0 && this.unspent() <= 0) return;
    this.bridge.sendIntent({ type: 'allocate_attr', attr: row.key, n });
  }
}
