// CastBarComponent — sichtbar während eines aktiven Casts.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 125-130 (`#cast-bar`).
//   • Renderer: `app.js` `_startCastBar`, `_updateCastBar`, `_endCastBar`
//                 (Z. ~4129-4165) plus `cast_started`/`cast_finished`-
//                 Handler (Z. 5660-5673).
//   • Styles:  `style.css` Z. 295-323.
//
// Backend: `cast_started { spell_id, cast_time_ms }`,
//          `cast_interrupted { reason }`, `cast_finished { spell_id?, cooldown_ms? }`.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';

import type { SpellEntry } from '../../core/models/talent.model';
import { GameStateService } from '../../core/services/game-state.service';

@Component({
  selector: 'app-cast-bar',
  standalone: true,
  templateUrl: './cast-bar.component.html',
  styleUrl: './cast-bar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CastBarComponent {
  private readonly state = inject(GameStateService);

  /** RAF-Tick — bringt die Progress-Bar 60 fps weiterzulaufen. */
  private readonly _tick = signal<number>(Date.now());
  private _rafId: number | null = null;

  readonly cast = computed(() => this.state.activeCast());
  readonly visible = computed<boolean>(() => this.cast() !== null);

  readonly spell = computed<SpellEntry | null>(() => {
    const c = this.cast();
    if (!c) return null;
    const catalog = this.state.spells().catalog;
    return catalog.find((s) => s.id === c.spell_id) ?? null;
  });

  readonly progressPct = computed<number>(() => {
    const c = this.cast();
    if (!c) return 0;
    void this._tick();
    if (c.duration_ms <= 0) return 100;
    const ms = Date.now() - c.started_at_ms;
    return Math.max(0, Math.min(100, (ms / c.duration_ms) * 100));
  });

  readonly iconStyle = computed<string>(() => {
    const path = this.spell()?.icon_path;
    return path ? `url(${path})` : '';
  });

  constructor() {
    effect(() => {
      const c = this.state.activeCast();
      if (c) this._startTick();
      else this._stopTick();
    });
  }

  private _startTick(): void {
    if (this._rafId !== null) return;
    const loop = (): void => {
      this._tick.set(Date.now());
      if (this.state.activeCast()) {
        this._rafId = requestAnimationFrame(loop);
      } else {
        this._rafId = null;
      }
    };
    this._rafId = requestAnimationFrame(loop);
  }

  private _stopTick(): void {
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  }
}
