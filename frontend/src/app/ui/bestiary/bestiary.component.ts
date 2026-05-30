// BestiaryComponent — Monster-Grid + Detail-Sidebar mit Suchfeld.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 217-229.
//   • Renderer: `app.js` `toggleBestiary`, `loadBestiaryData`,
//                `renderBestiaryGrid`, `showBestiaryDetail` (Z. 7309-7395).
//   • Styles:   `style.css` Z. 454-517.
//
// Datenquelle: das Backend bedient `/assets/monsters/generated_longlist/
// manifest.json` (statisches Manifest, vom Asset-Generator gepflegt).
// Diese Datei ist nicht die Liste in `frontend/legacy/monsters_longlist_
// data.js` (das war eine reine `window.LONGLIST_MONSTERS`-Sprite-Liste
// für den Renderer). Wir laden das Manifest beim ersten Open via `fetch`
// und cachen es in einer Instance-Property — wie der Legacy.
//
// Tastatur: `P` (Pedia) toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  effect,
  signal,
} from '@angular/core';

interface ManifestAsset {
  readonly slug?: string;
  readonly name?: string;
  readonly tier?: string | number;
  readonly source_columns?: readonly string[];
  readonly cell_file?: string;
}

interface ManifestSection {
  readonly section_title?: string;
  readonly assets?: readonly ManifestAsset[];
}

interface ManifestRoot {
  readonly sections?: readonly ManifestSection[];
}

/** Normalisierte Bestiarium-Einträge (1 pro Monster). */
interface BeastEntry {
  readonly slug: string;
  readonly name: string;
  readonly tier: string;
  readonly section: string;
  readonly cell: string;
  readonly cols: readonly string[];
}

@Component({
  selector: 'app-bestiary',
  standalone: true,
  templateUrl: './bestiary.component.html',
  styleUrl: './bestiary.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BestiaryComponent {
  readonly visible = signal<boolean>(false);
  readonly data = signal<readonly BeastEntry[]>([]);
  readonly filter = signal<string>('');
  readonly selected = signal<BeastEntry | null>(null);
  private loadStarted = false;

  readonly filtered = computed<readonly BeastEntry[]>(() => {
    const q = this.filter().toLowerCase().trim();
    const list = this.data();
    if (!q) return list;
    return list.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.section.toLowerCase().includes(q) ||
        e.slug.toLowerCase().includes(q),
    );
  });

  constructor() {
    // Beim ersten Öffnen lazily laden + cachen, und „erstes Monster
    // automatisch im Detail" (Legacy `_bestiaryDetailShown`).
    effect(() => {
      if (!this.visible()) return;
      if (!this.loadStarted) {
        this.loadStarted = true;
        this._loadManifest();
      }
      if (!this.selected()) {
        const first = this.filtered()[0];
        if (first) this.selected.set(first);
      }
    });
  }

  private _loadManifest(): void {
    // Wir nutzen das Browser-`fetch` direkt — HttpClient ist (noch) nicht
    // im Projekt provided, und diese eine JSON-Datei rechtfertigt das nicht.
    fetch('/assets/monsters/generated_longlist/manifest.json')
      .then((res) => res.json() as Promise<ManifestRoot>)
      .then((mf) => this.data.set(this._normalize(mf)))
      .catch((err: unknown) => {
        console.warn('Bestiarium-Manifest laden fehlgeschlagen', err);
        this.data.set([]);
      });
  }

  private _normalize(mf: ManifestRoot): readonly BeastEntry[] {
    const out: BeastEntry[] = [];
    for (const sec of mf.sections ?? []) {
      for (const a of sec.assets ?? []) {
        if (!a.slug) continue;
        const cols = (a.source_columns ?? [])
          .map((c) => (c ?? '').trim())
          .filter((c) => c && c !== '?' && c !== '—' && c !== '-');
        const cellRaw = a.cell_file ?? '';
        out.push({
          slug: a.slug,
          name: a.name ?? a.slug,
          tier: String(a.tier ?? '?'),
          section: sec.section_title ?? '',
          cell: '/' + cellRaw.replace(/^\//, ''),
          cols,
        });
      }
    }
    return out;
  }

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      // Wenn der Such-Input fokussiert ist, Escape schließt — sonst ignorieren.
      if (ev.key === 'Escape' && this.visible()) {
        this.visible.set(false);
        ev.preventDefault();
      }
      return;
    }
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    // Bestiary auf Y (bestiarY) — P kollidiert mit Spellbook.
    if (ev.key === 'y' || ev.key === 'Y') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  setFilter(ev: Event): void {
    const target = ev.target as HTMLInputElement | null;
    this.filter.set(target?.value ?? '');
  }

  select(entry: BeastEntry): void { this.selected.set(entry); }
}
