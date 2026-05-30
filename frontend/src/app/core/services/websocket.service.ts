// WebSocketService — besitzt die WS-Verbindung zum Backend.
//
// Verantwortlich für: Verbindung aufbauen (Cookie-Auth ist im Browser, keine
// expliziten Auth-Frames), Reconnect mit Exponential Backoff (1:1 Spiegelung
// des Legacy-Reconnect-Verhaltens), Outbound-Frames (`send`), Inbound-Frames
// als Observable. Befüllt KEINE Spielzustände — das macht `GameStateService`.
//
// Lifecycle: Service ist `providedIn: 'root'`, läuft also ab dem ersten
// Injection-Punkt. Verbindung wird über `connect()` explizit gestartet
// (Phase F4 ruft das nach Login). In F3 ist `connect()` reine Plumbing —
// noch nichts ruft sie an, das ist okay.

import { Injectable, OnDestroy, signal } from '@angular/core';
import { Observable, Subject } from 'rxjs';

import type {
  ClientIntent,
  ConnectionStatus,
  ServerMessage,
} from '../models/ws-message.model';

const MIN_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 30_000;

/** Codes, die einen Reconnect VERHINDERN (Auth-Failure). */
const NO_RETRY_CLOSE_CODES: ReadonlySet<number> = new Set([1008, 4401]);

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  /** Verbindungs-Status als Signal — UI kann darauf binden. */
  readonly status = signal<ConnectionStatus>('closed');

  /** Subject als Producer; Components abonnieren das `messages$`-Observable. */
  private readonly _messages = new Subject<ServerMessage>();
  readonly messages$: Observable<ServerMessage> = this._messages.asObservable();

  private _ws: WebSocket | null = null;
  private _reconnectAttempt = 0;
  private _reconnectTimer: number | null = null;
  /** Wahr, wenn die App die Verbindung absichtlich getrennt hat. */
  private _intentionallyClosed = false;

  /**
   * Verbindet sich mit `ws(s)://<host>/ws`. Cookies werden vom Browser
   * automatisch mitgesendet (gleicher Origin wie die Angular-App).
   * Mehrfache `connect()`-Aufrufe sind no-ops solange die Verbindung steht.
   */
  connect(): void {
    if (this._ws && this._ws.readyState <= WebSocket.OPEN) {
      // Bereits CONNECTING (0) oder OPEN (1) — nichts zu tun.
      return;
    }
    this._intentionallyClosed = false;
    this._open();
  }

  /**
   * Sendet einen Client-Frame. Stille No-op wenn die Verbindung nicht offen
   * ist (Legacy-Verhalten: WS-send während offline frisst der Browser eh).
   * Backend erwartet JSON-String.
   */
  send(payload: ClientIntent): void {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
      // Spiegelt das Legacy-Verhalten: kein Buffering, kein Error.
      return;
    }
    this._ws.send(JSON.stringify(payload));
  }

  /** Schließt die Verbindung absichtlich (kein Reconnect). */
  disconnect(): void {
    this._intentionallyClosed = true;
    if (this._reconnectTimer !== null) {
      window.clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }
    this.status.set('closed');
  }

  ngOnDestroy(): void {
    this.disconnect();
    this._messages.complete();
  }

  // ─── Private ──────────────────────────────────────────────────────────

  private _open(): void {
    this.status.set(this._reconnectAttempt > 0 ? 'reconnecting' : 'connecting');
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws`;
    const ws = new WebSocket(url);
    this._ws = ws;

    ws.onopen = (): void => {
      this._reconnectAttempt = 0;
      this.status.set('open');
    };

    ws.onerror = (ev): void => {
      // Wir setzen den Status nicht selbst — `onclose` kommt direkt danach
      // und ist autoritativ. Logging hilft beim Debug.
      // eslint-disable-next-line no-console
      console.error('WebSocket error:', ev);
    };

    ws.onclose = (ev): void => {
      this._ws = null;
      if (this._intentionallyClosed) {
        this.status.set('closed');
        return;
      }
      // Auth-Failure: NICHT reconnecten.
      if (NO_RETRY_CLOSE_CODES.has(ev.code)) {
        this.status.set('closed');
        // eslint-disable-next-line no-console
        console.warn(`WebSocket closed with no-retry code ${ev.code} — user must re-auth.`);
        return;
      }
      this._scheduleReconnect();
    };

    ws.onmessage = (ev): void => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(ev.data as string);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Invalid WS message — not JSON:', e, ev.data);
        return;
      }
      if (!parsed || typeof parsed !== 'object' || typeof (parsed as { type?: unknown }).type !== 'string') {
        // eslint-disable-next-line no-console
        console.warn('WS message missing `type` field, dropping:', parsed);
        return;
      }
      // Cast: parsed wurde gerade als Objekt mit string-`type` validiert.
      this._messages.next(parsed as ServerMessage);
    };
  }

  private _scheduleReconnect(): void {
    this._reconnectAttempt += 1;
    const delay = Math.min(
      MAX_BACKOFF_MS,
      MIN_BACKOFF_MS * Math.pow(2, this._reconnectAttempt - 1),
    );
    this.status.set('reconnecting');
    this._reconnectTimer = window.setTimeout(() => {
      this._reconnectTimer = null;
      this._open();
    }, delay);
  }
}
