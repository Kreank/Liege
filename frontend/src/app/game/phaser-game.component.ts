// PhaserGameComponent — mountet eine Phaser-Game-Instanz in einen
// `<div>`-Host und reicht die `GameBridgeService` an die `WorldScene`
// durch.
//
// Lifecycle:
//   • `ngAfterViewInit`: Game starten in `ngZone.runOutsideAngular`. Phaser
//     macht 60-FPS-Ticks via `requestAnimationFrame`; in der Angular-Zone
//     würde das die Change Detection bei jedem Frame anwerfen — daher
//     außerhalb.
//   • `ngOnDestroy`: `game.destroy(true)` räumt Canvas + Loop ab.
//
// Resizing: wir starten Phaser mit `Phaser.Scale.RESIZE` und nutzen die
// Host-Element-Größe. Das spiegelt den Legacy-Default (`mode: RESIZE,
// parent: body`).
//
// WS-Connect: wir rufen hier `WebSocketService.connect()` auf, damit die
// Verbindung beim Mount des Spiels steht. (In F5+ kommt eventuell ein
// separater Login-Flow davor — dann wandert der Connect-Call dort hin.)

import {
  AfterViewInit,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild,
  effect,
  inject,
} from '@angular/core';
import Phaser from 'phaser';

import { GameBridgeService } from '../core/services/game-bridge.service';
import { TooltipService } from '../core/services/tooltip.service';
import { WebSocketService } from '../core/services/websocket.service';
import type { ConnectionStatus } from '../core/models/ws-message.model';
import { AssetLoaderService } from './asset-loader.service';
import { EffectAnimationsService } from './effect-animations.service';
import { MobHoverController } from './mob-hover';
import { WalkAnimationsService } from './walk-animations.service';
import { WorldScene, type WorldSceneInitData } from './world-scene';

@Component({
  selector: 'app-phaser-game',
  standalone: true,
  template: `<div #phaserHost class="phaser-host"></div>`,
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        height: 100%;
      }
      .phaser-host {
        width: 100%;
        height: 100%;
        background: #0a0a0f;
      }
    `,
  ],
})
export class PhaserGameComponent implements AfterViewInit, OnDestroy {
  @ViewChild('phaserHost', { static: true })
  private host!: ElementRef<HTMLDivElement>;

  private readonly ngZone = inject(NgZone);
  private readonly bridge = inject(GameBridgeService);
  private readonly ws = inject(WebSocketService);
  private readonly assetLoader = inject(AssetLoaderService);
  private readonly walkAnimations = inject(WalkAnimationsService);
  private readonly effectAnimations = inject(EffectAnimationsService);
  private readonly tooltip = inject(TooltipService);

  private game: Phaser.Game | null = null;

  /**
   * Letzter beobachteter WS-Status. Dient als Flanken-Detektor, damit der
   * Gruppen-Resync (`group_refresh`) nur beim ÜBERGANG nach `'open'` feuert
   * und nicht bei jedem Re-Read des Signals. So gibt es nach Login UND nach
   * jedem Reconnect (Exponential-Backoff) genau EIN `group_refresh`.
   */
  private lastWsStatus: ConnectionStatus = 'closed';

  constructor() {
    // Auto-Resync der Gruppe: Sobald die WS-Verbindung (neu) offen ist,
    // einmalig `group_refresh` senden. Das Backend antwortet mit genau einem
    // `group_state`-Frame (Snapshot | null), den GameStateService bereits in
    // `this.party` schreibt — so steht das permanent sichtbare PartyFrame
    // nach einem Reconnect nicht mit veraltetem/leerem Stand da.
    effect(() => {
      const status = this.ws.status();
      if (status === 'open' && this.lastWsStatus !== 'open') {
        this.ws.send({ type: 'group_refresh' });
      }
      this.lastWsStatus = status;
    });
  }

  ngAfterViewInit(): void {
    this.ngZone.runOutsideAngular(() => {
      const host = this.host.nativeElement;
      const config: Phaser.Types.Core.GameConfig = {
        type: Phaser.AUTO,
        parent: host,
        backgroundColor: '#0a0a0f',
        scale: {
          mode: Phaser.Scale.RESIZE,
          parent: host,
          width: host.clientWidth || 800,
          height: host.clientHeight || 600,
        },
        render: {
          pixelArt: true,
          antialias: false,
        },
        scene: [WorldScene],
      };
      this.game = new Phaser.Game(config);
      // Scene-Init-Daten: Bridge + Render-Foundation-Services weiterreichen.
      // H3.8: `tooltip` ist optional im WorldSceneInitData (für interne Hover-
      // Detection in der Scene); wir reichen es trotzdem rein, damit beide
      // Wege (Scene-intern + extern MobHoverController) funktionieren.
      const initData: WorldSceneInitData = {
        bridge: this.bridge,
        assetLoader: this.assetLoader,
        walkAnimations: this.walkAnimations,
        effectAnimations: this.effectAnimations,
        tooltip: this.tooltip,
      };
      this.game.scene.start('WorldScene', initData);
      // H3.8 — Externer Mob-Hover-Tooltip als Sicherheits-Anker. Falls die
      // WorldScene-interne Hover-Detection von einer parallelen Subagent-
      // Edit überschrieben wird, übernimmt dieser Controller das Wiring.
      // Doppel-Hover ist no-op (beide schreiben dasselbe TooltipService-
      // Signal). Wir warten auf Phaser-READY (Scene-Manager hat dann den
      // WorldScene-Eintrag instanziiert) und danach auf das Scene-CREATE.
      const game = this.game;
      game.events.once(Phaser.Core.Events.READY, () => {
        const scene = game.scene.getScene('WorldScene');
        if (!scene) return;  // defensiv: Scene konnte nicht geladen werden
        scene.events.once(Phaser.Scenes.Events.CREATE, () => {
          new MobHoverController(scene, this.bridge, this.tooltip).attach();
        });
      });
    });

    // WS außerhalb der Zone öffnen — der WebSocket-Stream pumpt sonst pro
    // Inbound-Frame eine Change-Detection-Runde (ist aktuell noch ok, weil
    // keine UI gebunden ist; wir bleiben aus Hygiene-Gründen draußen).
    this.ngZone.runOutsideAngular(() => {
      this.ws.connect();
    });
  }

  ngOnDestroy(): void {
    if (this.game) {
      this.game.destroy(true);
      this.game = null;
    }
    this.ws.disconnect();
  }
}
