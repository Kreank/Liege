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
  effect,
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

  /** Voriger `visible`-Wert, um die false→true-Flanke im effect zu erkennen. */
  private wasVisible = false;

  constructor() {
    // Auto-Refresh: bei jedem Oeffnen (false→true) den Talent-Tree neu
    // anfordern, statt nur den Init-Snapshot zu zeigen.
    effect(() => {
      const open = this.visible();
      if (open && !this.wasVisible) {
        this.bridge.sendIntent({ type: 'list_talents' });
      }
      this.wasVisible = open;
    });
  }

  readonly points = computed<number>(() => this.state.talents()?.points ?? 0);

  /** Liste der gelernten Talent-IDs — auch sichtbar wenn der Tree leer ist,
   *  damit der Spieler seinen Fortschritt sieht (H1.2). */
  readonly learnedList = computed<readonly string[]>(
    () => this.state.talents()?.learned ?? [],
  );

  readonly rows = computed<readonly TalentRow[]>(() => {
    const tree = this.state.talents();
    if (!tree) return [];
    const learned = new Set(tree.learned);
    const points = tree.points;
    const nodes = tree.tree ?? [];
    return nodes.map<TalentRow>((node) => {
      // Bereits gelernt → immer 'learned' (optimistisch, auch vor Tree-Refresh).
      if (learned.has(node.id)) return { node, status: 'learned' };
      // Welle 53: Backend-Status BEVORZUGEN — er berücksichtigt das
      // skill_min-Level-Gate (Tier-2-Talente wie „Vampirisch" brauchen Combat-
      // Level 8). Vorher rechnete die UI nur prereq+Punkte → zeigte „Lernen",
      // das Backend lehnte mit skill_too_low ab (wirkte wie „kaputt").
      if (node.status === 'available' || node.status === 'needs_points'
          || node.status === 'locked' || node.status === 'learned') {
        return { node, status: node.status };
      }
      // Fallback (kein Backend-Status): clientseitig ohne Skill-Gate.
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
