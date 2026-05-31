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
  /** H3.9 — Mehrzeiliger Tooltip-Text mit aktuellem Stand + letztem XP-Gewinn
   *  inkl. Group-Share-Hinweis. Wird ans `title`-Attribut der Progress-Bar
   *  gebunden (native HTML-Tooltip — kein Overlay-Service-Anschluss nötig). */
  readonly tooltipText: string;
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
    // H3.9 — letzten XP-Gewinn pro Skill (mit Group-Share-Info) für Tooltip.
    const recent = this.state.recentSkillXp();
    return Object.entries(skills)
      .map(([kind, e]): SkillRow => {
        const xpNext = Math.max(1, e.xp_next);
        const pct = Math.max(0, Math.min(100, Math.round((e.xp / xpNext) * 100)));
        const tooltipText = this._buildSkillTooltip(kind, e, recent.get(kind));
        return {
          kind,
          icon: SKILL_ICONS[kind] ?? '•',
          label: kind.charAt(0).toUpperCase() + kind.slice(1),
          level: e.level,
          xp: e.xp,
          xpNext,
          pct,
          tooltipText,
        };
      })
      .sort((a, b) => b.level - a.level || a.label.localeCompare(b.label));
  });

  /** Tooltip-Text-Builder für eine Skill-Row (H3.9). Mehrzeilig — `title`
   *  rendert `\n` als Zeilenumbruch. Sektionen:
   *   • Stand: „Stufe X · Y/Z XP"
   *   • Letzter Gewinn: „Letzte XP: +N (vor M s)"
   *   • Group-Share-Hinweis: „mit N-er Gruppe geteilt" wenn partySize > 1
   *
   * Backend liefert KEIN explizites Share-Flag im `skill_xp`-Frame; die
   * „geteilt"-Anzeige ist eine Heuristik aus der aktuellen Party-Größe
   * zum Zeitpunkt des Events (siehe ai_fragen-Eintrag H3.9). */
  private _buildSkillTooltip(
    kind: string,
    entry: SkillEntry,
    recent: ReturnType<typeof this.state.recentSkillXp> extends ReadonlyMap<string, infer V> ? V | undefined : never,
  ): string {
    const lines: string[] = [];
    lines.push(`Stufe ${entry.level} · ${entry.xp}/${Math.max(1, entry.xp_next)} XP`);
    if (recent && recent.amount > 0) {
      const ageSec = Math.max(0, Math.floor((Date.now() - recent.atMs) / 1000));
      const shareNote = recent.partySize > 1
        ? ` (mit ${recent.partySize}er-Gruppe geteilt)`
        : '';
      lines.push(`Letzte XP: +${recent.amount}${shareNote} — vor ${ageSec}s`);
    } else if (recent?.leveledUp) {
      lines.push('Gerade Stufe erreicht!');
    }
    // `kind` als Suffix damit der User die technische Bezeichnung sehen kann.
    lines.push(`(${kind})`);
    return lines.join('\n');
  }

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
