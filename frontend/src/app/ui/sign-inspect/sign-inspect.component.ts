// SignInspectComponent — Schild-Lese-Modal (Welle 51).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 318-328.
//   • Renderer: `app.js` `openSignInspect`, `closeSignInspect`
//                 (Z. 6561-6577).
//   • Styles:   `style.css` Z. 666-695.
//
// Backend sendet `sign_inspect { slug, label }` wenn der Spieler ein
// Schild „benutzt" (use_structure auf einem Sign-Tile). GameStateService
// hält den Wert in `activeSignInspect`; die Component rendert das Modal,
// `Esc`/Hintergrund-Klick schließen es.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
} from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';

@Component({
  selector: 'app-sign-inspect',
  standalone: true,
  templateUrl: './sign-inspect.component.html',
  styleUrl: './sign-inspect.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SignInspectComponent {
  private readonly state = inject(GameStateService);

  readonly active = computed(() => this.state.activeSignInspect());
  readonly visible = computed<boolean>(() => this.active() !== null);

  readonly imgSrc = computed<string>(() => {
    const a = this.active();
    if (!a) return '';
    // Master-Version (512) für scharfe Darstellung (Legacy-Pfad).
    // Slug-Normalisierung: trim trailing `_sign` falls Backend ihn bereits
    // mitsendet, damit der Pfad `<slug>_sign.png` nicht zu `..._sign_sign`
    // wird. Backend-Verträge variieren je Sign-Quelle (Welle 51).
    const slug = a.slug.endsWith('_sign') ? a.slug.slice(0, -'_sign'.length) : a.slug;
    return `/assets/props/settlement/signs/professional/masters_512/${slug}_sign.png`;
  });

  /** Fallback-Handler: wenn das Master-Bild nicht existiert, zeige einen
   *  unauffälligen Placeholder-Hinweis statt eines kaputten Image-Icons. */
  onImgError(ev: Event): void {
    const img = ev.target as HTMLImageElement;
    img.style.opacity = '0.25';
    img.alt = 'Schildbild fehlt';
  }

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.visible()) this.close(); }

  close(): void { this.state.closeSignInspect(); }
}
