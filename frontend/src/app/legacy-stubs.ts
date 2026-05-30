// Legacy-Stubs — Marker für noch-nicht migrierte UI-/DOM-Stellen aus
// `frontend/legacy/app.js` `WorldScene`. **Diese Datei enthält absichtlich
// KEINEN Funktionscode** — nur Konstanten + Kommentar-Marker.
//
// Regel (Refactor-Plan §F4):
//   • Render-/Input-Teile wandern in `game/world-scene.ts`.
//   • UI-/DOM-/Panel-Teile bleiben vorerst un-migriert und werden hier mit
//     einem `// TODO F5+: <Panel>`-Marker dokumentiert.
//   • Eine Panel-Migration (F5-F15) entfernt den passenden Marker und legt
//     die zugehörige Angular-Component an.
//
// Diese Datei ist die EINZIGE Stelle, an der `// TODO F5+`-Marker stehen
// dürfen (siehe Plan). Sucht der Plan nach offenen UI-Punkten → grep hier.

export const F4_PENDING_UI_PANELS = [
  // TODO F5+: Faktionen-Panel (Rep-Bars, Standing-Labels).
  //          Legacy `toggleFactions`, `renderFactions`.
  'factions',

  // TODO F5+: Party-Frame (4-Slot Member-HUD, Health/Mana pro Member).
  //          Legacy `renderPartyFrame`, `updatePartyMember`.
  'party-frame',

  // TODO F5+: Loot-Roll-Overlay (Need/Greed/Pass-Buttons + Timer).
  //          Legacy `showLootRollOverlay`, `_handleLootRollStarted`.
  'loot-roll',

  // TODO F5+: Raid-Selector-Overlay (Party-Konvertierung zu Raid).
  //          Legacy `openRaidSelector`.
  'raid-selector',

  // TODO F5+: Group-Invite-Overlay (Annehmen/Ablehnen Pop-up).
  //          Legacy `showGroupInvite`.
  'group-invite',

  // TODO F5+: Spellbook + Cast-Bar (Welle 25 — Schulen, Cooldowns).
  //          Legacy `toggleSpellbook`, `_refreshSpellbook`, `_updateCastBar`.
  'spellbook',
  'cast-bar',

  // TODO F5+: Chat-Box (Eingabe + Verlauf, Global/Group/Whisper).
  //          Legacy `setupChatConsole`, `appendChatLine`.
  'chat',

  // TODO F5+: Downed-Overlay (Respawn-Button, Countdown).
  //          Legacy `_showDownedOverlay`, `forceRespawn`.
  'downed-overlay',

  // TODO F5+: Dialog-Panel (NPC-Talk Input + Antworten + Quest-Button).
  //          Legacy `openDialog`, `sendDialog`, `closeDialog`.
  'dialog',

  // TODO F5+: Chest-Panel (Inventar-zu-Truhe-Transfer).
  //          Legacy `openChest`, `closeChest`, `chest_transfer_*`.
  'chest',

  // TODO F5+: Crafting-Panel (Stationen + Hand-Crafting Recipes).
  //          Legacy `openCrafting`, `craft`, `_renderCraftingRecipes`.
  'crafting',

  // TODO F5+: Trade-Panel (NPC-Shop Buy/Sell + Coin-Anzeige).
  //          Legacy `openTrade`, `_renderTrade`, `buyItem`, `sellItem`.
  'trade',

  // TODO F5+: Research-Panel (Tech-Tree-Invest + Pool-Anzeige).
  //          Legacy `toggleResearch`, `renderResearch`.
  'research',

  // TODO F5+: Bills-Panel (Workshop-Aufträge, add/remove Bill).
  //          Legacy `renderBills`, `addBill`, `removeBill`.
  'bills',

  // TODO F5+: Build-Bar + Place-Ghost-Tooltip (Material-Auswahl, Rotation-Label).
  //          Legacy `toggleBuildMode`, `_populatePaletteOnce`,
  //          `_refreshRotationLabel`, `_refreshPlaceGhost`.
  //          Anmerkung: Der **Place-Ghost-Sprite** selbst (Phaser-Image über
  //          dem Cursor) gehört zur Render-Schicht und kommt in F4c mit der
  //          Build-Mode-Input-Logik; nur das DOM-Overlay (Build-Bar, Material-
  //          Toggle) bleibt UI.
  'build-bar',

  // TODO F5+: Bestiary-Overlay (Monster-Grid + Suche).
  //          Legacy `toggleBestiary`, `renderBestiaryGrid`.
  'bestiary',

  // TODO F5+: Item-Tooltip (Hover + Pin per Long-Press/Right-Click).
  //          Legacy `_showItemTooltip`, `pinItemTooltip`, `unpinItemTooltip`.
  'item-tooltip',

  // TODO F5+: Sign-Inspect-Overlay (Welle 51 — Schild-Lese-Modal).
  //          Legacy `openSignInspect`, `closeSignInspect`.
  'sign-inspect',

  // TODO F5+: Minimap (DOM-Canvas, kein Phaser — wird per `drawMinimap`
  //          gemalt). Eventuell als Angular-Component mit `<canvas>`.
  'minimap',

  // TODO F5+: Top-Right-Links (Admin/Logout) — werden Legacy via
  //          `document.body.appendChild` rangehängt; gehört in den App-Shell.
  'top-right-links',

  // TODO F5+: Settings-Overlay (Audio-Sliders Master/SFX/Music + Mute).
  //          Legacy `setupSoundSettings`. Liegt komplett im IIFE oben.
  'settings',

  // TODO F5+: Mobile-Touch-Joystick + Action-Buttons.
  //          Legacy `window.MobileUI`, `window.touchInput`.
  'mobile-controls',
] as const;
