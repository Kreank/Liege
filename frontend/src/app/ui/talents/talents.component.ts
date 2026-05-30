// TalentsComponent — Talent-Baum-Panel mit Lern-Buttons.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 185-194 (`#talents-overlay`).
//   • Renderer:   `app.js` `toggleTalents`, `renderTalentsTree`,
//                 `learnTalent`.
//   • Styles:     `style.css` Z. 147-195.
//
// Backend liefert `talents`-Signal (TalentTree: learned[], points, tree?).
// Wenn `tree` fehlt, zeigen wir nur die gelernten IDs und die verfügbaren
// Punkte — der Legacy-Tree-Tab-Aufbau (Schulen/Klassen) ist Asset-getrieben
// und kommt mit F-final, wenn ein vom Backend gelieferter Tree-Snapshot
// gefördert wird. Notiert in REFACTOR_NOTES §F8.
//
// Intent:
//   • learn_talent { talent_id }
//
// Tastatur: `T` toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { TalentNode } from '../../core/models/talent.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

interface TalentRow {
  readonly node: TalentNode;
  readonly status: 'learned' | 'available' | 'locked' | 'needs_points';
}

@Component({
  selector: 'app-talents',
  standalone: true,
  templateUrl: './talents.component.html',
  styleUrl: './talents.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TalentsComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);

  readonly visible = signal<boolean>(false);

  readonly points = computed<number>(() => this.state.talents()?.points ?? 0);

  readonly rows = computed<readonly TalentRow[]>(() => {
    const tree = this.state.talents();
    if (!tree) return [];
    const learned = new Set(tree.learned);
    const points = tree.points;
    const nodes = tree.tree ?? [];
    return nodes.map<TalentRow>((node) => {
      if (learned.has(node.id)) return { node, status: 'learned' };
      const reqOk = (node.requires ?? []).every((r) => learned.has(r));
      if (!reqOk) return { node, status: 'locked' };
      if (points < node.cost) return { node, status: 'needs_points' };
      return { node, status: 'available' };
    });
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 't' || ev.key === 'T') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  learn(row: TalentRow): void {
    if (row.status !== 'available') return;
    this.bridge.sendIntent({ type: 'learn_talent', talent_id: row.node.id });
  }
}
