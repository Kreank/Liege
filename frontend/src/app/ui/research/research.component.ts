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
  DestroyRef,
  HostListener,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import type {
  ResearchAge,
  ResearchBranch,
  ResearchNode,
} from '../../core/models/research.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

/** H3.13 — Dauer der grünen Glow-Animation am abgeschlossenen Knoten. Nach
 *  Ablauf wird der Eintrag aus dem `recentlyCompleted`-Set entfernt, damit
 *  das Pulse aufhört (und beim nächsten Öffnen des Panels nicht nochmal
 *  aufflackert). 3 s reicht visuell für 4-5 Sinus-Pulses bei 1.2 s-Periode. */
const COMPLETE_ANIM_DURATION_MS = 3000;

interface NodeCell {
  readonly id: string;
  readonly node: ResearchNode;
  readonly branchColor: string;
  readonly pct: number;
  readonly progressText: string;
  readonly blockedByTechPrint: boolean;
  /** H3.13 — true wenn der Knoten gerade frisch abgeschlossen wurde und die
   *  grüne Glow-Animation läuft. Template zieht eine CSS-Klasse `.node-card.complete-anim`. */
  readonly completeAnim: boolean;
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
export class ResearchComponent implements OnInit {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);
  private readonly bridge = inject(GameBridgeService);
  private readonly destroyRef = inject(DestroyRef);

  readonly visible = signal<boolean>(false);
  /** Aktiver Branch-Filter — 'all' zeigt alle Branches nebeneinander. */
  readonly activeBranch = signal<string>('all');

  /** H3.13 — Set der Knoten-IDs, die gerade die Complete-Animation tragen.
   *  Wird beim `research_update {done:true}` befüllt und nach
   *  COMPLETE_ANIM_DURATION_MS wieder geleert. Signal damit `ageBlocks`
   *  bei Add/Remove neu berechnet. */
  private readonly _animatedComplete = signal<ReadonlySet<string>>(new Set());
  private readonly _animTimers = new Map<string, ReturnType<typeof setTimeout>>();

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
    const animated = this._animatedComplete();
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
          completeAnim: animated.has(id),
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

  ngOnInit(): void {
    // H3.13 — Research-Complete-Animation. Wir lesen aus dem rohen WS-Stream,
    // weil GameState.research-Signal nur den Endzustand führt (die Information
    // „dieser Knoten ist GERADE eben fertig geworden" ist sonst weg).
    this.bridge.messages$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((msg) => {
        if (msg.type !== 'research_update') return;
        const done = (msg as { done?: unknown }).done;
        if (done !== true) return;
        const nodeId = (msg as { node_id?: unknown }).node_id;
        if (typeof nodeId !== 'string' || nodeId.length === 0) return;
        this._triggerCompleteAnim(nodeId);
      });
    this.destroyRef.onDestroy(() => {
      for (const t of this._animTimers.values()) clearTimeout(t);
      this._animTimers.clear();
    });
  }

  private _triggerCompleteAnim(nodeId: string): void {
    // Falls schon ein laufender Timer für diesen Knoten existiert, resetten —
    // sonst wäre ein zweiter „done"-Frame stumm.
    const prev = this._animTimers.get(nodeId);
    if (prev) clearTimeout(prev);
    const next = new Set(this._animatedComplete());
    next.add(nodeId);
    this._animatedComplete.set(next);
    const handle = setTimeout(() => {
      this._animTimers.delete(nodeId);
      const cur = new Set(this._animatedComplete());
      cur.delete(nodeId);
      this._animatedComplete.set(cur);
    }, COMPLETE_ANIM_DURATION_MS);
    this._animTimers.set(nodeId, handle);
  }

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
