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
  effect,
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

// Deutsche Backend-Slugs (sync mit attributes.py + character-create.component.ts).
// Kern-Attribute zuerst, dann die (weiterhin verteilbaren) abgeleiteten Werte.
const ATTR_META: ReadonlyArray<Omit<AttrRow, 'value'>> = [
  // — Kern-Attribute —
  { key: 'stärke',       label: '💪 Stärke',       desc: 'Physischer Schaden, Abbau-Ertrag, Tragelast' },
  { key: 'geschick',     label: '🎯 Geschick',     desc: 'Krit-Rate, Ausweichen, Crafting, Heimlichkeit' },
  { key: 'vitalität',    label: '❤️ Vitalität',    desc: 'Max. Leben, HP-Regeneration, Körper-Widerstand' },
  { key: 'intelligenz',  label: '🧠 Intelligenz',  desc: 'Max. Mana, Magieschaden, Forschungstempo' },
  { key: 'willenskraft', label: '🔮 Willenskraft', desc: 'Mana-Regen, Status-Resistenz, Heileffizienz' },
  { key: 'charisma',     label: '💬 Charisma',     desc: 'Handelspreise, NPC-Stimmung' },
  // — Abgeleitete Werte —
  { key: 'verteidigung', label: '🛡️ Verteidigung', desc: 'Schadensreduktion gegen Angriffe' },
  { key: 'ausweichen',   label: '💨 Ausweichen',   desc: 'Chance, Angriffe zu negieren' },
  { key: 'krit_rate',    label: '💥 Krit-Rate',    desc: 'Chance auf kritischen Treffer (%)' },
  { key: 'krit_schaden', label: '✨ Krit-Schaden',  desc: 'Schadensbonus bei Krits (%)' },
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

  /** Voriger `visible`-Wert, um die false→true-Flanke im effect zu erkennen
   *  (kein Re-Fire beim Schliessen). */
  private wasVisible = false;

  constructor() {
    // Auto-Refresh: bei jedem Oeffnen (false→true) ein frisches Stat-Sheet
    // anfordern, statt auf veralteten init/equip-Daten zu basieren.
    effect(() => {
      const open = this.visible();
      if (open && !this.wasVisible) {
        this.bridge.sendIntent({ type: 'list_attributes' });
      }
      this.wasVisible = open;
    });
  }

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
