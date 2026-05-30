// SettingsComponent — Sound-Einstellungs-Modal mit Sliders für
// Master/SFX/Music + Mute-Toggle, persistiert in localStorage.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • Renderer + DOM-Konstruktion: IIFE in `app.js` ab Z. 211 (Settings-
//     Overlay wird komplett zur Laufzeit zusammengebaut, deshalb gibt es
//     KEINEN HTML-Stub in `index.html` für diese Komponente).
//   • Persistenz: `localStorage['liege_sound_settings']`, JSON-Form
//     `{ master, sfx, music, muted }` (siehe app.js Z. 11+60-67).
//
// Bridge zu Audio: Die Werte werden in `localStorage` gespeichert und (wenn
// vorhanden) an `window.SoundManager.setVolume / setMute` weitergereicht.
// Der SoundManager selbst lebt in `frontend/legacy/app.js` und wird in
// F-final entweder portiert oder von einem Angular-AudioService abgelöst —
// die Settings-UI hängt nicht vom Vorhandensein des Managers ab (sie
// persistiert die Werte unabhängig).

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  signal,
} from '@angular/core';

interface SoundSettings {
  master: number;
  sfx: number;
  music: number;
  muted: boolean;
}

interface SoundManagerLike {
  setVolume(channel: 'master' | 'sfx' | 'music', value: number): void;
  setMute(value: boolean): void;
}

interface AppWindow extends Window {
  SoundManager?: SoundManagerLike;
}

const LS_KEY = 'liege_sound_settings';
const DEFAULTS: Readonly<SoundSettings> = {
  master: 0.7, sfx: 0.9, music: 0.5, muted: false,
};

@Component({
  selector: 'app-settings',
  standalone: true,
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {
  readonly visible = signal<boolean>(false);
  readonly master = signal<number>(DEFAULTS.master);
  readonly sfx = signal<number>(DEFAULTS.sfx);
  readonly music = signal<number>(DEFAULTS.music);
  readonly muted = signal<boolean>(DEFAULTS.muted);

  constructor() {
    this._loadFromStorage();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.close();
  }

  open(): void { this.visible.set(true); }
  close(): void { this.visible.set(false); }
  toggle(): void { this.visible.update((v) => !v); }

  /** Slider-Handler. `channel` ist eines unserer drei Signal-Namen. */
  onSliderInput(channel: 'master' | 'sfx' | 'music', ev: Event): void {
    const target = ev.target as HTMLInputElement | null;
    if (!target) return;
    const v = Math.max(0, Math.min(1, Number(target.value) / 100));
    if (channel === 'master') this.master.set(v);
    else if (channel === 'sfx') this.sfx.set(v);
    else this.music.set(v);
    this._persist();
    const mgr = (window as AppWindow).SoundManager;
    if (mgr) mgr.setVolume(channel, v);
  }

  onMuteChange(ev: Event): void {
    const target = ev.target as HTMLInputElement | null;
    if (!target) return;
    this.muted.set(target.checked);
    this._persist();
    const mgr = (window as AppWindow).SoundManager;
    if (mgr) mgr.setMute(target.checked);
  }

  pct(v: number): number { return Math.round(v * 100); }

  private _loadFromStorage(): void {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return;
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return;
      const p = parsed as Partial<SoundSettings>;
      if (typeof p.master === 'number') this.master.set(p.master);
      if (typeof p.sfx === 'number') this.sfx.set(p.sfx);
      if (typeof p.music === 'number') this.music.set(p.music);
      if (typeof p.muted === 'boolean') this.muted.set(p.muted);
    } catch {
      // Ignore — Defaults bleiben.
    }
  }

  private _persist(): void {
    try {
      const payload: SoundSettings = {
        master: this.master(),
        sfx: this.sfx(),
        music: this.music(),
        muted: this.muted(),
      };
      localStorage.setItem(LS_KEY, JSON.stringify(payload));
    } catch {
      // Ignore — Storage Quota / Private Mode.
    }
  }
}
