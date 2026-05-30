// TopRightLinksComponent — Admin- + Logout-Links oben rechts.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • Konstruktion: `app.js` Z. 10122-10145 (Links werden imperativ per
//     `document.body.appendChild` angehängt, kein HTML-Stub).
//   • Styles: `style.css` Z. 1283-1294 (`.top-right-link`).
//
// Auth-Endpoint: `GET /auth/me` liefert `{ username, role }`. Bei 401 wird
// im Legacy auf `/login` redirected — wir behalten dasselbe Verhalten,
// damit der App-Shell auf „nicht eingeloggt" reagieren kann. Logout-
// Endpoint: `POST /auth/logout`, danach Redirect.

import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  signal,
} from '@angular/core';

interface AuthMeResponse {
  readonly username?: string;
  readonly role?: string;
}

@Component({
  selector: 'app-top-right-links',
  standalone: true,
  templateUrl: './top-right-links.component.html',
  styleUrl: './top-right-links.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TopRightLinksComponent implements OnInit {
  readonly role = signal<string | null>(null);
  readonly isAdmin = signal<boolean>(false);

  ngOnInit(): void {
    fetch('/auth/me', { credentials: 'same-origin' })
      .then((r) => {
        if (!r.ok) {
          // Legacy redirected hier auf /login — wir tun dasselbe, damit der
          // App-Shell konsistent mit dem altem Bootstrapping bleibt.
          window.location.href = '/login';
          return null;
        }
        return r.json() as Promise<AuthMeResponse>;
      })
      .then((me) => {
        if (!me) return;
        this.role.set(me.role ?? null);
        this.isAdmin.set(me.role === 'admin');
      })
      .catch(() => {
        // Network-Fehler — wir blenden die Links einfach nicht ein.
      });
  }

  async logout(ev: MouseEvent): Promise<void> {
    ev.preventDefault();
    try {
      await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
    } catch {
      // Auch bei Fehler weiter auf /login — Server-State ist evtl. trotzdem clean.
    }
    window.location.href = '/login';
  }
}
