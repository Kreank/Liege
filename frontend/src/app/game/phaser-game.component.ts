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
  inject,
} from '@angular/core';
import Phaser from 'phaser';

import { GameBridgeService } from '../core/services/game-bridge.service';
import { WebSocketService } from '../core/services/websocket.service';
import { AssetLoaderService } from './asset-loader.service';
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

  private game: Phaser.Game | null = null;

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
      const initData: WorldSceneInitData = {
        bridge: this.bridge,
        assetLoader: this.assetLoader,
        walkAnimations: this.walkAnimations,
      };
      this.game.scene.start('WorldScene', initData);
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
