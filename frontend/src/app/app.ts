// App-Root — der Shell-Container. Hostet den Phaser-Renderer (lazy via
// @defer, damit das ~1.2-MB-Phaser-Bundle nicht im Initial-Chunk landet)
// und legt die Angular-UI-Panels (HUD, Hotbar, …) absolute-positioniert
// obendrauf.
//
// Konvention (siehe Refactor-Plan §F4-F15):
//   • <app-phaser-game> als Render-Layer (Defer-Block).
//   • Jede UI-Komponente ist standalone, OnPush, bindet an Signals aus
//     GameStateService. Keine Angular-Routen — die UI ist ein einziger
//     Bildschirm + Overlays.

import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

import { PhaserGameComponent } from './game/phaser-game.component';
import { BestiaryComponent } from './ui/bestiary/bestiary.component';
import { BuildBarComponent } from './ui/build-bar/build-bar.component';
import { CastBarComponent } from './ui/cast-bar/cast-bar.component';
import { CharacterComponent } from './ui/character/character.component';
import { ChatComponent } from './ui/chat/chat.component';
import { ChestComponent } from './ui/chest/chest.component';
import { CraftingComponent } from './ui/crafting/crafting.component';
import { DialogComponent } from './ui/dialog/dialog.component';
import { DownedOverlayComponent } from './ui/downed-overlay/downed-overlay.component';
import { GroupInviteComponent } from './ui/group-invite/group-invite.component';
import { HotbarComponent } from './ui/hotbar/hotbar.component';
import { HudComponent } from './ui/hud/hud.component';
import { FactionsComponent } from './ui/factions/factions.component';
import { InventoryComponent } from './ui/inventory/inventory.component';
import { ItemTooltipComponent } from './ui/item-tooltip/item-tooltip.component';
import { LootRollComponent } from './ui/loot-roll/loot-roll.component';
import { MinimapComponent } from './ui/minimap/minimap.component';
import { MobileControlsComponent } from './ui/mobile-controls/mobile-controls.component';
import { PartyFrameComponent } from './ui/party-frame/party-frame.component';
import { QuestsComponent } from './ui/quests/quests.component';
import { RaidSelectorComponent } from './ui/raid-selector/raid-selector.component';
import { ResearchComponent } from './ui/research/research.component';
import { SettingsComponent } from './ui/settings/settings.component';
import { SignInspectComponent } from './ui/sign-inspect/sign-inspect.component';
import { SkillsComponent } from './ui/skills/skills.component';
import { SpellbookComponent } from './ui/spellbook/spellbook.component';
import { TalentsComponent } from './ui/talents/talents.component';
import { TopRightLinksComponent } from './ui/top-right-links/top-right-links.component';
import { TradeComponent } from './ui/trade/trade.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    PhaserGameComponent,
    HudComponent,
    HotbarComponent,
    InventoryComponent,
    SkillsComponent,
    TalentsComponent,
    CharacterComponent,
    QuestsComponent,
    FactionsComponent,
    PartyFrameComponent,
    LootRollComponent,
    RaidSelectorComponent,
    GroupInviteComponent,
    SpellbookComponent,
    CastBarComponent,
    ChatComponent,
    DownedOverlayComponent,
    DialogComponent,
    ChestComponent,
    CraftingComponent,
    TradeComponent,
    ResearchComponent,
    BuildBarComponent,
    BestiaryComponent,
    SignInspectComponent,
    ItemTooltipComponent,
    MinimapComponent,
    SettingsComponent,
    TopRightLinksComponent,
    MobileControlsComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  /** Visibility-Flag für den Raid-Selector. Wird vom PartyFrame über
   *  `openRaidSelector` gehoben — bleibt im App-Shell, weil der Selector
   *  parteneigen ein eigenes Modal ist und nicht Teil des PartyFrames. */
  readonly raidSelectorVisible = signal<boolean>(false);

  openRaidSelector(): void { this.raidSelectorVisible.set(true); }
  closeRaidSelector(): void { this.raidSelectorVisible.set(false); }
}
