// ToastContainerComponent — rendert die kurzlebigen UI-Notifications
// aus dem `ToastService` (H1.21).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 252-260 (`#toast-container`).
//   • Renderer:   `app.js` `showToast`, `_dismissToast` (Z. ~4500-4570) —
//                 legacy hatte oben-mittig; wir packen es unten-mittig, weil
//                 oben mittlerweile mit Disaster-Icons belegt ist (H1.16).
//
// Architektur:
//   • Read-only von `ToastService.toasts()` — der Service kümmert sich um
//     Lebenszeit (`setTimeout`-basiert) und Stack-Limit (FIFO).
//   • Klick auf einen Toast → `dismiss(id)` (manuell wegklicken).
//   • Stack rendert von unten nach oben mit `flex-column-reverse` — neuester
//     Toast erscheint oben über den älteren, alte schieben sich nach unten.
//   • Kein Animation-Library nötig: CSS-Transition auf `transform` + `opacity`
//     leistet das Slide-In, das Auto-Remove durch den Service handled das
//     Slide-Out implizit (Element verschwindet aus dem DOM → kein Fade-Out
//     dafür, das wäre die nächste Iteration).
//
// Position: unten-mittig, mit 120px Abstand zur Hotbar (~60px hoch + 60px
// Padding), max-width 480px für lange Backend-Toasts ("🥵 Zu erschöpft …").
//
// Ai-Entscheidung 2026-05-31: Position unten-Mitte (siehe ai_fragen.md).

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';

import { ToastService } from '../../core/services/toast.service';
import type { ToastKind } from '../../core/services/toast.service';

/** Kind → Emoji-Icon (Fallback wenn der Toast-Text selbst keins enthält). */
const KIND_ICON: Readonly<Record<ToastKind, string>> = {
  info: 'ℹ️',
  success: '✓',
  warn: '⚠️',
  error: '✗',
};

@Component({
  selector: 'app-toast-container',
  standalone: true,
  templateUrl: './toast-container.component.html',
  styleUrl: './toast-container.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ToastContainerComponent {
  private readonly svc = inject(ToastService);

  /** Stack der sichtbaren Toasts (max 6, ServiceState). */
  readonly toasts = this.svc.toasts;

  /** Visible nur wenn mindestens einer da ist — vermeidet leeren DIV im DOM. */
  readonly visible = computed<boolean>(() => this.toasts().length > 0);

  /** Bestimmt das Lead-Icon für einen Toast — bevorzugt ein Emoji am
   *  Text-Anfang (Backend setzt häufig 🥵 / 🎲 / ⚒️ vor), sonst Kind-Default. */
  iconFor(text: string, kind: ToastKind): string {
    // Erstes Codepoint (kein "char" — Emojis sind oft Surrogate-Paare).
    const first = [...text][0] ?? '';
    // Heuristik: alles ausserhalb ASCII zählen wir als „Icon vorhanden".
    if (first && first.charCodeAt(0) > 127) return ''; // schon im Text
    return KIND_ICON[kind] ?? '';
  }

  dismiss(id: string, event: MouseEvent): void {
    event.stopPropagation();
    this.svc.dismiss(id);
  }

  /** Track-by-Id für `@for` — vermeidet Re-Render bei Stack-Updates. */
  trackById(_idx: number, t: { readonly id: string }): string {
    return t.id;
  }
}
