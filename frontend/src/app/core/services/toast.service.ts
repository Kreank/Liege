// ToastService — kurzlebige UI-Notifications (H1.20).
//
// Backend sendet >150 verschiedene `toast`-Frames für Erfolg-/Fehler-Feedback
// (Stamina-Mangel, Tool-Hinweis, Quest-Limit, Faction-Toast, …). Bisher landete
// `case 'toast': break;` in GameState — d. h. ~70 % aller User-Aktionen blieben
// ohne Rückmeldung. Dieser Service ist der zentrale Eintritt für sowohl
// Backend-Toasts (über GameState-Dispatch H1.22) als auch Cross-Domain-
// Triggers (H1.23, z. B. `group_error` → eigener Toast aus dem State).
//
// Architektur:
//   • Signal `toasts: readonly Toast[]` — die ToastContainer-Component
//     iteriert und rendert.
//   • Auto-Remove via setTimeout pro Toast — kein zentraler Sweeper-Timer,
//     weil pro Toast die Duration variieren kann (`6000` für Warn-Disaster,
//     `3000` für Info-Quest-Progress).
//   • Defensive ID-Generierung: zur Build-Time darf `Date.now()` nicht
//     evaluiert werden (Tree-Shake-Issues mit reinen Constants); deshalb
//     wird die ID NUR innerhalb `show()` zur Runtime erzeugt.
//   • Stack-Limit: max 6 sichtbare Toasts; ältere werden verdrängt
//     (FIFO). Das vermeidet Toast-Overflow bei Burst-Events.
//
// Verwendung (Component):
//   toast.show('Quest abgeschlossen!', 'success');
//   toast.show('Falle ausgelöst (12 Schaden)', 'warn', 5000);

import { Injectable, signal } from '@angular/core';

/** Toast-Kind steuert Farbe/Icon im ToastContainer. */
export type ToastKind = 'info' | 'success' | 'warn' | 'error';

/** Ein einzelner Toast-Eintrag im Signal-Array. */
export interface Toast {
  readonly id: string;
  readonly text: string;
  readonly kind: ToastKind;
  /** Wall-Clock-ms, ab dem der Toast verschwindet (für UI-Countdown). */
  readonly expiresAt: number;
}

/** Default-Duration pro Kind (ms). Warn/Error bleiben länger, weil Lesefokus. */
const DEFAULT_DURATION_MS: Readonly<Record<ToastKind, number>> = {
  info: 4000,
  success: 4000,
  warn: 6000,
  error: 6000,
};

/** Stack-Limit — ältere Toasts werden bei Überlauf abgeschnitten. */
const MAX_STACK = 6;

@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly _toasts = signal<readonly Toast[]>([]);
  readonly toasts = this._toasts.asReadonly();

  /** Zähler für ID-Eindeutigkeit auch bei gleicher ms-Zeit (Burst). */
  private _seq = 0;

  /**
   * Zeigt einen Toast. `durationMs` überschreibt die Kind-Default-Dauer.
   * No-op wenn `text` leer ist (defensiv — Backend sendet manchmal Frames
   * ohne `text`-Feld, das wäre eine sinnlose leere Bubble).
   */
  show(text: string, kind: ToastKind = 'info', durationMs?: number): void {
    if (!text || typeof text !== 'string') return;
    const now = Date.now();
    const duration = durationMs ?? DEFAULT_DURATION_MS[kind];
    const id = `t${now}_${this._seq++}`;
    const toast: Toast = {
      id,
      text,
      kind,
      expiresAt: now + duration,
    };
    this._toasts.update((arr) => {
      const next = [...arr, toast];
      // FIFO-Drop bei Overflow — neueste behalten, älteste raus.
      if (next.length > MAX_STACK) {
        return next.slice(next.length - MAX_STACK);
      }
      return next;
    });
    setTimeout(() => {
      this._toasts.update((arr) => arr.filter((t) => t.id !== id));
    }, duration);
  }

  /** Manuelles Dismiss (Klick auf X im Toast). */
  dismiss(id: string): void {
    this._toasts.update((arr) => arr.filter((t) => t.id !== id));
  }

  /** Räumt alle Toasts (z. B. bei Reconnect/Re-Init). */
  clear(): void {
    this._toasts.set([]);
  }
}
