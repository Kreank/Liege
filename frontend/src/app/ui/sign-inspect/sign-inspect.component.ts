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
    return `/assets/props/settlement/signs/professional/masters_512/${a.slug}_sign.png`;
  });

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.visible()) this.close(); }

  close(): void { this.state.closeSignInspect(); }
}
