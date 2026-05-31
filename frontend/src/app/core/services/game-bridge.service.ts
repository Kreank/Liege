// GameBridgeService — die einzige Naht zwischen Phaser und Angular.
//
// Phaser-Scenes leben außerhalb der Angular-Zone (siehe `PhaserGameComponent`
// `ngZone.runOutsideAngular`). Daher dürfen sie KEINE Angular-Services direkt
// injizieren — jeder Signal-`set()` würde Change Detection triggern und die
// Render-Loop könnte stottern.
//
// Stattdessen wird **diese Bridge** in die Scene per `Scene.init(data)`
// durchgereicht. Sie bietet Phaser-seitig:
//   • READ-only Zugriff auf alle Game-State-Signals (über `state` → das
//     GameStateService selbst, das nur read-Methoden anbietet).
//   • `sendIntent()` — delegiert an `WebSocketService.send()`. Strikt typed
//     mit `ClientIntent`.
//
// Bridge wird in `PhaserGameComponent` injiziert (Angular-side) und einmal
// pro `Phaser.Game` an die Scene weitergegeben.

import { Injectable, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';

import type { ClientIntent, ServerMessage } from '../models/ws-message.model';
import { GameStateService } from './game-state.service';
import { ToastService, type ToastKind } from './toast.service';
import { WebSocketService } from './websocket.service';

@Injectable({ providedIn: 'root' })
export class GameBridgeService {
  /** READ-only Game-State (Phaser liest pro Frame Signals via `state.<sig>()`). */
  readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);
  /** Phaser-FX-Code (H2-A) braucht eine schmale Toast-Schiene ohne den
   *  vollen GameStateService anzufassen. */
  private readonly toastSvc = inject(ToastService);

  /** Convenience für die WorldScene: kurzer Toast über die globale Pipeline.
   *  Phaser-Side ruft das aus FX-Handlern (z. B. Trap-Triggered, H2.1). */
  showToast(text: string, kind: ToastKind = 'info', durationMs?: number): void {
    this.toastSvc.show(text, kind, durationMs);
  }

  /**
   * Roher Server-Message-Stream. Wird vom Phaser-Renderer für **transiente**
   * FX abonniert (Damage-Numbers, Hit-Sparks, `visual_effect`-Animationen),
   * die NICHT durch Signal-Updates abgedeckt sind (Signals halten nur den
   * persistenten State — der `dmg`-Wert eines `npc_damaged`-Frames ist nach
   * dem Tick wieder weg).
   */
  readonly messages$: Observable<ServerMessage> = this.ws.messages$;

  // ─── Build-Mode-State (F-extras-3 — Bridge zwischen Phaser-Input und
  // Angular-UI). Phaser-Input (Taste B) ruft `toggleBuildMode()` über die
  // Bridge; die Angular-`BuildBarComponent` reagiert via Signal. Material
  // und Rotation sind ebenfalls Cross-Cutting (Build-Bar wählt sie, Phaser
  // braucht sie beim Place-Click — wenn die Place-Logik in F-final aus
  // dem Stub raus kommt, liest sie hier mit).
  readonly buildMode = signal<boolean>(false);
  readonly selectedStructure = signal<string | null>(null);
  readonly selectedMaterial = signal<'stone' | 'wood' | 'straw'>('stone');
  readonly placeRotation = signal<number>(0);

  toggleBuildMode(): void {
    this.buildMode.update((v) => !v);
  }

  setBuildMode(on: boolean): void {
    this.buildMode.set(on);
  }

  rotatePlacement(): void {
    this.placeRotation.update((deg) => (deg + 90) % 360);
  }

  /**
   * Phaser → Server. Frame muss einen `type`-String haben; alles weitere ist
   * intent-spezifisch. Spiegelt das Legacy-`ws.send(JSON.stringify({...}))`.
   *
   * No-op wenn die WS nicht offen ist — gleiches Verhalten wie Legacy.
   */
  sendIntent(intent: ClientIntent): void {
    this.ws.send(intent);
  }

  // ─── Convenience-Helpers für die häufigsten Intents ──────────────────
  //
  // Die Scene könnte alles direkt über `sendIntent({type:'move',...})`
  // schicken. Wir bieten kleine Wrapper, um Tippfehler im `type`-String zu
  // vermeiden und damit `git grep sendMove` die Aufrufer findet.

  sendMove(x: number, y: number): void {
    this.sendIntent({ type: 'move', x, y });
  }

  sendSprint(on: boolean): void {
    this.sendIntent({ type: 'sprint', on });
  }

  sendAttackNpc(npcId: number): void {
    this.sendIntent({ type: 'attack_npc', npc_id: npcId });
  }

  sendUseStructure(x: number, y: number): void {
    this.sendIntent({ type: 'use_structure', x, y });
  }

  sendPickItem(itemId: number): void {
    this.sendIntent({ type: 'pick_item', item_id: itemId });
  }

  sendTalkToNpc(npcId: number): void {
    this.sendIntent({ type: 'talk_to_npc', npc_id: npcId });
  }

  /**
   * Händler-Trade-Intent. Backend antwortet mit `trade_open {offerings,
   * coins}`, das GameState in `activeTrade` setzt → `<app-trade>` rendert.
   * Click-Routing erkennt Merchant-Kinds (`merchant`, `merchant_female`,
   * siehe world-scene.ts::isMerchantNpc — H1.13).
   */
  sendOpenTrade(npcId: number): void {
    this.sendIntent({ type: 'open_trade', npc_id: npcId });
  }

  sendAttackStructure(x: number, y: number): void {
    this.sendIntent({ type: 'attack_structure', x, y });
  }

  sendPlaceStructure(args: {
    readonly x: number;
    readonly y: number;
    readonly structure_type: string;
    readonly material: 'stone' | 'wood' | 'straw';
    readonly rotation: number;
  }): void {
    this.sendIntent({
      type: 'place_structure',
      x: args.x,
      y: args.y,
      structure_type: args.structure_type,
      material: args.material,
      rotation: args.rotation,
    });
  }

  /**
   * Tür-Toggle (H1.12). Backend mappt `toggle_door {x, y}` auf den
   * Tür-State-Swap und antwortet mit `structure_replaced` (door_open ↔
   * door_closed). Backend-Handler in `backend/ws/structures.py::handle_toggle_door`.
   */
  sendToggleDoor(x: number, y: number): void {
    this.sendIntent({ type: 'toggle_door', x, y });
  }

  /**
   * Dungeon-Truhe öffnen (H1.5). NICHT identisch mit Overworld-`chest_open` —
   * Dungeon-Truhen sind Features im Dungeon-Floor-Payload, das Backend liefert
   * Loot direkt per `inventory_add` + `wallet_update` und feuert
   * `dungeon_chest_opened {x, y}` zur Marker-Aktualisierung (Subagent A).
   * Backend-Handler: `backend/ws/structures.py::handle_dungeon_chest`.
   */
  sendDungeonChest(x: number, y: number): void {
    this.sendIntent({ type: 'dungeon_chest', x, y });
  }
}
