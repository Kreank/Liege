// ItemTooltipComponent — der globale, an die Maus geheftete Item-Tooltip.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 146 (`#item-tooltip`).
//   • Renderer:   `app.js` `showItemTooltip` (Z. 4225-4280).
//   • Styles:     `style.css` Z. 380-415.
//
// Liest `TooltipService.active`. Position wird auf den letzten gespeicherten
// (x,y) gesetzt; wir clampen rechts/oben analog zum Legacy.
//
// Inhalt: Name (Qualitäts-Farbe), Qualität, Kategorie. Stat-/Affix-/
// Flavor-Inhalte wie im Legacy sind reine Tooltip-Erweiterungen und können
// in F-final ergänzt werden — der entscheidende Architektur-Schritt war
// das Anker-Service-Pattern.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';

import { ITEM } from '../../core/data/items';
import { WEAPON_STATS, WEAPON_RANGE } from '../../core/data/weapons';
import { ARMOR_STATS } from '../../core/data/armor';
import { TooltipService } from '../../core/services/tooltip.service';

/** Eine Stat-Zeile im Tooltip (z. B. „Schaden: 12–18"). */
export interface StatLine {
  readonly label: string;
  readonly value: string;
}

/** Klartext-Labels für gängige Affix-Stat-Keys (Backend-Slugs). Fallback ist
 *  der humanisierte Slug. `pct` markiert Prozent-Werte. */
// Welle 53: Schmuck-Basis-Stats (Spiegel von backend item_stats.JEWELRY_STATS).
const JEWELRY_STATS: Readonly<Record<string, {
  hp_bonus?: number; mana_bonus?: number; magic_bonus?: number; regen_bonus?: number;
}>> = {
  ring:   { mana_bonus: 10, magic_bonus: 0.05 },
  amulet: { hp_bonus: 15, regen_bonus: 0.05 },
};

const AFFIX_LABEL: Readonly<Record<string, { label: string; pct?: boolean }>> = {
  damage_pct:       { label: 'Schaden',          pct: true },
  speed_pct:        { label: 'Angriffstempo',    pct: true },
  crit_chance_pct:  { label: 'Krit-Chance',      pct: true },
  defense_flat:     { label: 'Verteidigung' },
  hp_flat:          { label: 'Leben' },
  mana_flat:        { label: 'Mana' },
  fire_damage:      { label: 'Feuerschaden' },
  ice_damage:       { label: 'Eisschaden' },
  lightning_damage: { label: 'Blitzschaden' },
  necrotic_damage:  { label: 'Nekrotischer Schaden' },
  lifesteal_pct:    { label: 'Lebensraub',       pct: true },
  armor_pen_pct:    { label: 'Rüstungsdurchschlag', pct: true },
  fire_resist:      { label: 'Feuerresistenz',   pct: true },
  ice_resist:       { label: 'Eisresistenz',     pct: true },
  lightning_resist: { label: 'Blitzresistenz',   pct: true },
  magic_resist:     { label: 'Magieresistenz',   pct: true },
};

const QUALITY_COLOR: Readonly<Record<string, string>> = {
  rough:      '#888e91',
  normal:     '#4fab58',
  fine:       '#4581e0',
  masterwork: '#e7c44b',
  legendary:  '#ee772b',
};

const QUALITY_DE: Readonly<Record<string, string>> = {
  rough: 'roh', normal: 'normal', fine: 'fein',
  masterwork: 'meisterhaft', legendary: 'legendär',
};

const CATEGORY_DE: Readonly<Record<string, string>> = {
  weapon: 'Waffe', armor: 'Rüstung', jewelry: 'Schmuck',
  consumable: 'Verbrauch', food: 'Speise', magic: 'Magie',
  tool: 'Werkzeug', resource: 'Rohstoff',
};

@Component({
  selector: 'app-item-tooltip',
  standalone: true,
  templateUrl: './item-tooltip.component.html',
  styleUrl: './item-tooltip.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ItemTooltipComponent {
  private readonly tooltip = inject(TooltipService);

  // H3.8: TooltipService kann jetzt sowohl Item- als auch Mob-Tooltips halten.
  // Wir lesen NUR den Item-Mode (separate `<app-mob-tooltip>` rendert die
  // Mob-Variante). `activeItem` ist null wenn entweder gar nichts aktiv oder
  // gerade ein Mob-Tooltip läuft.
  readonly payload = computed(() => this.tooltip.activeItem());
  readonly visible = computed<boolean>(() => this.payload() !== null);
  readonly pinned = computed<boolean>(() => this.payload()?.pinned ?? false);

  readonly displayName = computed<string>(() => {
    const p = this.payload();
    if (!p) return '';
    const def = ITEM[p.item.kind];
    return p.item.unique_name ?? p.item.name ?? def?.name ?? p.item.kind;
  });

  readonly nameColor = computed<string>(() => {
    const q = this.payload()?.item.quality;
    return q ? QUALITY_COLOR[q] ?? '#ccc' : '#ccc';
  });

  readonly qualityLabel = computed<string | null>(() => {
    const q = this.payload()?.item.quality;
    return q ? QUALITY_DE[q] ?? q : null;
  });

  readonly categoryLabel = computed<string | null>(() => {
    const c = this.payload()?.item.category;
    return c ? CATEGORY_DE[c] ?? c : null;
  });

  /** Waffen-/Rüstungs-Stats. Bevorzugt die per-Instanz `rolled_stats` (Welle 23),
   *  fällt sonst auf die Basis-Werte aus WEAPON_STATS/ARMOR_STATS (per `kind`)
   *  zurück. Leer für Items ohne Kampf-Stats (Rohstoffe, Speisen …). */
  readonly statLines = computed<readonly StatLine[]>(() => {
    const it = this.payload()?.item;
    if (!it) return [];
    const rs = it.rolled_stats;
    const lines: StatLine[] = [];
    const pct = (v: number): string => `${Math.round(v * 100)} %`;

    const w = WEAPON_STATS[it.kind];
    if (w || (rs && rs.damage_max != null)) {
      const dmgMin = rs?.damage_min;
      const dmgMax = rs?.damage_max;
      if (dmgMin != null && dmgMax != null) {
        lines.push({ label: '⚔️ Schaden', value: `${dmgMin}–${dmgMax}` });
      } else if (w) {
        lines.push({ label: '⚔️ Schaden', value: `${w.dmg}` });
      }
      const speed = rs?.speed ?? w?.speed;
      if (speed != null) lines.push({ label: 'Tempo', value: `${speed.toFixed(2)}/s` });
      const crit = rs?.crit ?? w?.crit;
      if (crit != null) lines.push({ label: 'Krit-Chance', value: pct(crit) });
      if (w?.crit_mult != null) lines.push({ label: 'Krit-Schaden', value: `×${w.crit_mult}` });
      const ap = rs?.armor_pen ?? w?.armor_pen;
      if (ap) lines.push({ label: 'Rüstungsdurchschlag', value: pct(ap) });
      const range = rs?.range ?? w?.range ?? WEAPON_RANGE[it.kind];
      if (range != null) lines.push({ label: 'Reichweite', value: `${range}` });
      if (rs?.cleave ?? w?.cleave) lines.push({ label: 'Spaltschlag', value: 'ja' });
    }

    const a = ARMOR_STATS[it.kind];
    if (a || (rs && rs.defense != null)) {
      const def = rs?.defense ?? a?.defense;
      if (def != null) lines.push({ label: '🛡 Verteidigung', value: `${def}` });
      const block = rs?.block_chance ?? a?.block_chance;
      if (block) lines.push({ label: 'Block-Chance', value: pct(block) });
      const sb = rs?.speed_bonus ?? a?.speed_bonus;
      if (sb) lines.push({ label: 'Tempo-Bonus', value: pct(sb) });
      const ccb = rs?.crit_chance_bonus ?? a?.crit_chance_bonus;
      if (ccb) lines.push({ label: 'Krit-Bonus', value: pct(ccb) });
      if (rs?.weight ?? a?.weight) {
        lines.push({ label: 'Gewicht', value: `${rs?.weight ?? a?.weight}` });
      }
    }

    // Welle 53: Schmuck (Ring/Amulett). Vorher zeigte der Tooltip dafür GAR
    // nichts. Werte = Basis aus JEWELRY_STATS (Backend wendet sie ebenso an).
    const j = JEWELRY_STATS[it.kind];
    if (j) {
      if (j.hp_bonus)    lines.push({ label: '❤️ Leben', value: `+${j.hp_bonus}` });
      if (j.mana_bonus)  lines.push({ label: '💧 Mana', value: `+${j.mana_bonus}` });
      if (j.magic_bonus) lines.push({ label: '✨ Magieschaden', value: `+${pct(j.magic_bonus)}` });
      if (j.regen_bonus) lines.push({ label: '🔮 Regeneration', value: `+${pct(j.regen_bonus)}` });
    }
    return lines;
  });

  /** Affix-Boni (Prefix/Suffix) als lesbare Zeilen — z. B. „+15 % Schaden". */
  readonly affixLines = computed<readonly StatLine[]>(() => {
    const affixes = this.payload()?.item.affixes;
    if (!affixes?.length) return [];
    const lines: StatLine[] = [];
    for (const af of affixes) {
      for (const [key, val] of Object.entries(af.stats ?? {})) {
        const meta = AFFIX_LABEL[key];
        const label = meta?.label ?? this._humanize(key);
        const value = meta?.pct ? `+${val} %` : `+${val}`;
        lines.push({ label, value });
      }
    }
    return lines;
  });

  private _humanize(slug: string): string {
    return slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  readonly positionStyle = computed<{ left: string; top: string }>(() => {
    const p = this.payload();
    if (!p) return { left: '-9999px', top: '-9999px' };
    const winW = typeof window !== 'undefined' ? window.innerWidth : 1024;
    const left = Math.min(winW - 300, p.x + 14);
    const top = Math.max(10, p.y - 8);
    return { left: left + 'px', top: top + 'px' };
  });

  closePinned(): void { this.tooltip.unpin(); }
}
