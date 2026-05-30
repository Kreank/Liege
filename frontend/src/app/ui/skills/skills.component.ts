// SkillsComponent — Panel mit Skill-XP-Progress + Level (Welle 8).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 155-163 (`#skills-overlay`).
//   • Renderer:   `app.js` `toggleSkills`, `renderSkills` — liest
//                 `this.player.skills` (Record kind→{level,xp,xp_next}).
//   • Styles:     `style.css` Z. 82-106 (.skill-row etc.).
//
// Backend ist die Quelle: das `skills`-Map aus `PlayerSnapshot` wird hier
// gerendert. Read-only — keine Intents.
//
// Tastatur: `K` toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { SkillEntry } from '../../core/models/player.model';
import { GameStateService } from '../../core/services/game-state.service';

const SKILL_ICONS: Readonly<Record<string, string>> = {
  melee: '⚔️',
  ranged: '🏹',
  magic: '✨',
  defense: '🛡️',
  mining: '⛏️',
  woodcutting: '🪓',
  cooking: '🍳',
  fishing: '🎣',
  farming: '🌾',
  crafting: '🔨',
  alchemy: '🧪',
};

interface SkillRow {
  readonly kind: string;
  readonly icon: string;
  readonly label: string;
  readonly level: number;
  readonly xp: number;
  readonly xpNext: number;
  readonly pct: number;
}

@Component({
  selector: 'app-skills',
  standalone: true,
  templateUrl: './skills.component.html',
  styleUrl: './skills.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkillsComponent {
  private readonly state = inject(GameStateService);

  readonly visible = signal<boolean>(false);

  readonly rows = computed<readonly SkillRow[]>(() => {
    const player = this.state.player();
    const skills: Readonly<Record<string, SkillEntry>> = player?.skills ?? {};
    return Object.entries(skills)
      .map(([kind, e]): SkillRow => {
        const xpNext = Math.max(1, e.xp_next);
        const pct = Math.max(0, Math.min(100, Math.round((e.xp / xpNext) * 100)));
        return {
          kind,
          icon: SKILL_ICONS[kind] ?? '•',
          label: kind.charAt(0).toUpperCase() + kind.slice(1),
          level: e.level,
          xp: e.xp,
          xpNext,
          pct,
        };
      })
      .sort((a, b) => b.level - a.level || a.label.localeCompare(b.label));
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'k' || ev.key === 'K') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }
}
