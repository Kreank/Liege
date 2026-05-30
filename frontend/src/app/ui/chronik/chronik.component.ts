// ChronikComponent — Welt-Chronik / Event-Log (H1.15).
//
// Backend feuert `event {event:{id,kind,tier?,title?,description?,ts?,x?,y?}}`
// und `world_event {…}` Frames. GameState pflegt `events`-Signal als Ring-
// Buffer (limitiert in `_handleEvent` auf ~50 letzte Einträge).
//
// Hier rendern wir die letzten N Events als scrollbare Liste. Toggle via
// Hotkey `J` (Journal) — wir haben uns gegen `H` entschieden, weil `H` für
// Hand-Crafting reserviert ist (Roadmap-Punkt H2.19). `C` ist Character.
// `J` ist im Legacy frei und intuitiv (Journal/Chronik).

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { WorldEvent } from '../../core/models/chunk.model';
import { GameStateService } from '../../core/services/game-state.service';

/** Maximum sichtbare Einträge (Signal selbst limitiert auf ~50 Server-seitig). */
const MAX_ROWS = 50;

interface ChronikRow {
  readonly id: number | string;
  readonly icon: string;
  readonly title: string;
  readonly description?: string;
  readonly ts?: string;
  readonly severityClass: 'minor' | 'normal' | 'major';
}

/** Kind → Icon + Severity-Hint. Erweiterbar; unknown-Kinds fallen auf 📜 /
 *  normal zurück. Source: backend/event_worker.py + storyteller-Slugs. */
const KIND_META: Readonly<Record<string, { icon: string; sev?: 'minor' | 'major' }>> = {
  // Disaster
  bloodmoon:        { icon: '🌑', sev: 'major' },
  dying_sun:        { icon: '☀️', sev: 'major' },
  thunderstorm:     { icon: '⛈️', sev: 'minor' },
  scorching_heat:   { icon: '🔥', sev: 'minor' },
  ash_rain:         { icon: '🌫️', sev: 'minor' },
  wildfire:         { icon: '🔥', sev: 'major' },
  pestilence:       { icon: '☠️', sev: 'major' },
  locust_swarm:     { icon: '🦗', sev: 'major' },
  // Raids
  raid_start:       { icon: '⚔', sev: 'major' },
  raid_started:     { icon: '⚔', sev: 'major' },
  raid_ended:       { icon: '🛡', sev: 'minor' },
  // Storyteller-Lore
  storyteller:      { icon: '📖' },
  lore:             { icon: '📖' },
  dungeon_spawned:  { icon: '🏰' },
  dungeon_collapsed:{ icon: '💥', sev: 'minor' },
  npc_death:        { icon: '💀' },
  faction:          { icon: '🛡' },
  trade:            { icon: '💰' },
};

@Component({
  selector: 'app-chronik',
  standalone: true,
  templateUrl: './chronik.component.html',
  styleUrl: './chronik.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChronikComponent {
  private readonly state = inject(GameStateService);

  readonly visible = signal<boolean>(false);

  /** Rohe Events — neueste zuletzt im Signal; wir invertieren für Anzeige. */
  readonly rows = computed<readonly ChronikRow[]>(() => {
    const events = this.state.events();
    const lastN = events.slice(-MAX_ROWS).reverse();
    return lastN.map((ev) => this._toRow(ev));
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'j' || ev.key === 'J') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  private _toRow(ev: WorldEvent): ChronikRow {
    const meta = KIND_META[ev.kind] ?? { icon: '📜' };
    const severity = (ev.tier === 'major' || meta.sev === 'major')
      ? 'major'
      : (ev.tier === 'minor' || meta.sev === 'minor') ? 'minor' : 'normal';
    // Server hat optional `title` und `description`; sonst Kind als Fallback.
    const title = ev.title ?? this._humanizeKind(ev.kind);
    return {
      id: ev.id,
      icon: meta.icon,
      title,
      description: ev.description,
      ts: ev.ts,
      severityClass: severity,
    };
  }

  private _humanizeKind(kind: string): string {
    return kind.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
