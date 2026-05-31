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

import type { BodyPart, PlayerAttributes, PlayerStats } from '../../core/models/player.model';
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

/** Body-Part-Row für H3.2 — pre-derived Display-Werte für die HP-Bar.
 *  `pct` ist 0..100 (clamped), `barClass` steuert die Farbe:
 *  grün ≥66 %, gelb 33..65 %, rot <33 %, „crippled" bei hp == 0. */
interface BodyPartRow {
  readonly name: string;
  readonly label: string;
  readonly hp: number;
  readonly maxHp: number;
  readonly pct: number;
  readonly damaged: boolean;
  readonly barClass: 'ok' | 'wound' | 'crit' | 'crippled';
}

/** Mapping Backend-Slug → deutsche UI-Bezeichnung. Backend liefert die
 *  3 Standard-Slugs `legs`/`arms`/`torso` (Welle 28 Body-Damage-System);
 *  Fallback ist die Capitalize-Form, damit unbekannte Parts korrekt rendern. */
const BODY_PART_LABEL: Readonly<Record<string, string>> = {
  legs: '🦵 Beine',
  arms: '💪 Arme',
  torso: '🫁 Torso',
  head: '🧠 Kopf',
};

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

  /** H3.2 — Body-Parts-Section. Liest aus `state.player().body_parts`
   *  (Welle 28-Body-Damage-System). Bei fehlendem Snapshot leerer Array,
   *  damit die Section im Template via @if einfach ausgeblendet wird. */
  readonly bodyParts = computed<readonly BodyPartRow[]>(() => {
    const parts: readonly BodyPart[] | undefined = this.state.player()?.body_parts;
    if (!parts || parts.length === 0) return [];
    return parts.map((bp) => {
      const maxHp = Math.max(0, bp.max_hp);
      const hp = Math.max(0, bp.hp);
      const pct = maxHp > 0 ? Math.min(100, Math.round((hp / maxHp) * 100)) : 0;
      let barClass: BodyPartRow['barClass'];
      if (hp <= 0) barClass = 'crippled';
      else if (pct < 33) barClass = 'crit';
      else if (pct < 66) barClass = 'wound';
      else barClass = 'ok';
      return {
        name: bp.name,
        label: BODY_PART_LABEL[bp.name] ?? bp.name.charAt(0).toUpperCase() + bp.name.slice(1),
        hp,
        maxHp,
        pct,
        damaged: !!bp.damaged || hp < maxHp,
        barClass,
      };
    });
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
