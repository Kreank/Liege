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
import { TooltipService } from '../../core/services/tooltip.service';

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
