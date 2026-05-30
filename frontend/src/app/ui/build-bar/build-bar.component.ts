// BuildBarComponent — Bau-Menü (Tabs + Subtabs + Palette + Material/Rotation).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 234-254 (`#build-bar` mit Tabs/Subtabs/
//                Palette/Footer).
//   • Renderer: `app.js` `toggleBuildMode`, `_populatePaletteOnce`,
//                `_selectBuildCategory`, `_selectBuildSubcategory`,
//                `_renderPaletteForTypes`, `selectStructure`,
//                `_refreshRotationLabel` (Z. 3404-3560).
//   • Styles:   `style.css` Z. 594-724.
//
// Sichtbarkeits-Quelle: Phaser-Input sendet beim Drücken von `B` über
// `GameBridgeService.toggleBuildMode()`. Diese Component liest
// `bridge.buildMode()` und blendet sich entsprechend ein. Sie selbst
// schickt KEINE Hotkeys (sonst doppelt mit Phaser).
//
// Material/Rotation werden in der Bridge gepflegt — der Place-Click selbst
// liegt im Renderer und ist nicht Teil dieser Phase (siehe F-final-TODO
// in `world-scene.ts`).

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';

import { BUILD_CATEGORIES } from '../../core/data/build-categories';
import { NATURAL_STRUCTURE_TYPES, STRUCTURE } from '../../core/data/structures';
import type {
  BuildCategory,
  BuildSubcategory,
} from '../../core/models/structure.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';

interface PaletteEntry {
  readonly type: string;
  readonly name: string;
  readonly icon: string;
  readonly key: string;
  readonly isSign: boolean;
  readonly signSlug: string | null;
}

const MATERIALS: readonly ('stone' | 'wood' | 'straw')[] = ['stone', 'wood', 'straw'];
const MATERIAL_LABEL: Readonly<Record<string, string>> = {
  stone: 'Stein',
  wood: 'Holz',
  straw: 'Stroh',
};

@Component({
  selector: 'app-build-bar',
  standalone: true,
  templateUrl: './build-bar.component.html',
  styleUrl: './build-bar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BuildBarComponent {
  private readonly bridge = inject(GameBridgeService);

  readonly visible = computed<boolean>(() => this.bridge.buildMode());
  readonly categories: readonly BuildCategory[] = BUILD_CATEGORIES;
  readonly materials = MATERIALS;
  readonly materialLabel = MATERIAL_LABEL;

  /** Aktive Top-Level-Kategorie. */
  readonly activeCategoryId = signal<string>(BUILD_CATEGORIES[0]?.id ?? '');
  /** Aktive Sub-Kategorie (nur relevant bei Kategorien mit `subcategories`). */
  readonly activeSubcategoryId = signal<string | null>(null);

  readonly activeCategory = computed<BuildCategory | undefined>(() => {
    const id = this.activeCategoryId();
    return this.categories.find((c) => c.id === id);
  });

  readonly subcategories = computed<readonly BuildSubcategory[]>(() =>
    this.activeCategory()?.subcategories ?? [],
  );

  readonly activeSubcategory = computed<BuildSubcategory | undefined>(() => {
    const subId = this.activeSubcategoryId();
    const subs = this.subcategories();
    return subId ? subs.find((s) => s.id === subId) : subs[0];
  });

  /** Tiles, die aktuell in der Palette gezeigt werden. */
  readonly paletteTypes = computed<readonly string[]>(() => {
    const cat = this.activeCategory();
    if (!cat) return [];
    if (cat.subcategories && cat.subcategories.length > 0) {
      return this.activeSubcategory()?.types ?? [];
    }
    return cat.types ?? [];
  });

  readonly paletteEntries = computed<readonly PaletteEntry[]>(() => {
    const out: PaletteEntry[] = [];
    for (const type of this.paletteTypes()) {
      const cfg = STRUCTURE[type];
      if (!cfg) continue;
      if (cfg.notBuildable) continue;
      if (NATURAL_STRUCTURE_TYPES.has(type)) continue;
      const isSign = type.startsWith('sign_');
      out.push({
        type,
        name: cfg.name.replace(/^🪧 /, ''),
        icon: cfg.icon ?? '•',
        key: cfg.key ?? '',
        isSign,
        signSlug: isSign ? type.slice(5) : null,
      });
    }
    return out;
  });

  readonly selectedStruct = computed<string | null>(() => this.bridge.selectedStructure());
  readonly selectedName = computed<string>(() => {
    const t = this.selectedStruct();
    if (!t) return '–';
    return STRUCTURE[t]?.name ?? t;
  });
  readonly rotation = computed<number>(() => this.bridge.placeRotation());
  readonly material = computed<string>(() => this.bridge.selectedMaterial());

  selectCategory(catId: string): void {
    this.activeCategoryId.set(catId);
    const cat = this.categories.find((c) => c.id === catId);
    if (cat?.subcategories && cat.subcategories.length > 0) {
      this.activeSubcategoryId.set(cat.subcategories[0]?.id ?? null);
    } else {
      this.activeSubcategoryId.set(null);
    }
  }

  selectSubcategory(subId: string): void {
    this.activeSubcategoryId.set(subId);
  }

  selectStructure(type: string): void {
    this.bridge.selectedStructure.set(type);
  }

  setMaterial(m: string): void {
    if (m === 'stone' || m === 'wood' || m === 'straw') {
      this.bridge.selectedMaterial.set(m);
    }
  }

  /** Click-Handler für Material-Select (`<select>` gibt einen string raus). */
  onMaterialChange(ev: Event): void {
    const target = ev.target as HTMLSelectElement | null;
    if (target) this.setMaterial(target.value);
  }

  rotate(): void { this.bridge.rotatePlacement(); }

  close(): void { this.bridge.setBuildMode(false); }

  signIconUrl(slug: string): string {
    return `/assets/props/settlement/signs/professional/icons_64/${slug}_sign.png`;
  }

  paletteTitle(entry: PaletteEntry): string {
    return entry.name + (entry.key ? ` (Taste ${entry.key})` : '');
  }
}
