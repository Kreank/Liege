// ResearchComponent — Tech-Tree-Panel mit Pool-Anzeige + Branch-Tabs.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 165-173 (`#research-overlay`).
//   • Renderer:   `app.js` `toggleResearch`, `refreshResearchUI`,
//                 `investResearch` (Z. 7016-7195).
//   • Styles:     `style.css` Z. 109-145.
//
// Tastatur: `R` toggelt das Overlay, `Esc` schließt es.
//
// Backend:
//   • Liest `research`-Signal (Nodes + Pool + Branches + Ages) aus
//     `GameStateService`. Befüllung via `init`-Snapshot bzw. nachträglich
//     via `research_update` / `research_pool_update`.
//   • Sendet `invest_research { node_id, points }` beim +1/+5/+25-Klick.
//
// Side-Effect-Notiz (Legacy hatte Toasts für "nicht genug Pool" / "Forschung
// fertig"): Toasts/Feedback wandern in F-final in einen separaten Toast-
// Service; für F-extras-2 reicht die reine Tree-Anzeige + Pool-Banner.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type {
  ResearchAge,
  ResearchBranch,
  ResearchNode,
} from '../../core/models/research.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

interface NodeCell {
  readonly id: string;
  readonly node: ResearchNode;
  readonly branchColor: string;
  readonly pct: number;
  readonly progressText: string;
  readonly blockedByTechPrint: boolean;
}

interface AgeBlock {
  readonly age: ResearchAge;
  readonly cells: readonly NodeCell[];
}

@Component({
  selector: 'app-research',
  standalone: true,
  templateUrl: './research.component.html',
  styleUrl: './research.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResearchComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly visible = signal<boolean>(false);
  /** Aktiver Branch-Filter — 'all' zeigt alle Branches nebeneinander. */
  readonly activeBranch = signal<string>('all');

  readonly research = computed(() => this.state.research());
  readonly pool = computed<number>(() => this.research().pool);
  readonly branches = computed<readonly ResearchBranch[]>(() => this.research().branches);
  readonly ages = computed<readonly ResearchAge[]>(() => this.research().ages);

  /** Gruppierung: pro Age ein Block mit allen Nodes (gefiltert nach Branch). */
  readonly ageBlocks = computed<readonly AgeBlock[]>(() => {
    const r = this.research();
    const nodes = r.nodes;
    const ages = r.ages;
    const branches = r.branches;
    const activeBranch = this.activeBranch();
    if (Object.keys(nodes).length === 0 || ages.length === 0) return [];
    const activeBranchIds: readonly string[] =
      activeBranch === 'all' ? branches.map((b) => b.id) : [activeBranch];

    const blocks: AgeBlock[] = [];
    for (const age of ages) {
      const cells: NodeCell[] = [];
      for (const [id, n] of Object.entries(nodes)) {
        if (n.age !== age.id) continue;
        if (!activeBranchIds.includes(n.branch)) continue;
        const branchColor = branches.find((b) => b.id === n.branch)?.color ?? '#6e5e3a';
        const pct =
          n.points_max > 0 ? Math.max(0, Math.min(1, n.points / n.points_max)) * 100 : 0;
        cells.push({
          id,
          node: n,
          branchColor,
          pct,
          progressText: n.done ? '✓ erforscht' : `${n.points}/${n.points_max}`,
          blockedByTechPrint: !!n.tech_print && !n.has_tech_print,
        });
      }
      if (cells.length > 0) blocks.push({ age, cells });
    }
    return blocks;
  });

  readonly empty = computed<boolean>(() => {
    const r = this.research();
    return Object.keys(r.nodes).length === 0 || r.branches.length === 0;
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'r' || ev.key === 'R') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  setBranch(branchId: string): void { this.activeBranch.set(branchId); }

  invest(nodeId: string, points: number): void {
    this.ws.send({ type: 'invest_research', node_id: nodeId, points });
  }

  canInvest(cell: NodeCell, points: number): boolean {
    return cell.node.available && !cell.blockedByTechPrint && this.pool() >= points;
  }

  /** Tab-Style berechnet sich aus Active-State + Branch-Farbe. */
  branchTabBg(branchId: string, color: string): string {
    return this.activeBranch() === branchId ? color : '#302418';
  }
}
