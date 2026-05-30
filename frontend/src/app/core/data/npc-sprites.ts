// NPC-Sprite-Map — portiert aus frontend/legacy/app.js Z. 1284-1494.
import type { NpcSprite, PresetWalkConfig } from '../models/npc.model';

/** Visualisierungs-Map pro NPC-Kind. */
export const NPC_SPRITE: Readonly<Record<string, NpcSprite>> = {
  // ─── Friendly NPCs ──────────────────────────────────────────────────────
  wanderer:    { sprite: 'npc_villager',         tint: 0xffffff, label: 'Wanderer' },
  villager:    { sprite: 'npc_villager',         tint: 0xffffff, label: 'Dorfbewohner' },
  merchant:    { sprite: 'npc_merchant',         tint: 0xffffff, label: 'Händler' },
  hermit:      { sprite: 'npc_hermit',           tint: 0xffffff, label: 'Einsiedler' },
  bard:        { sprite: 'npc_bard',             tint: 0xffffff, label: 'Barde' },
  scholar:     { sprite: 'npc_scholar',          tint: 0xffffff, label: 'Gelehrter' },
  soldier:     { sprite: 'npc_guard',            tint: 0xffffff, label: 'Soldat' },
  mage:        { sprite: 'npc_mage',             tint: 0xffffff, label: 'Magier' },
  farmer:      { sprite: 'npc_farmer',           tint: 0xffffff, label: 'Bauer' },
  guard:       { sprite: 'npc_guard',            tint: 0xffffff, label: 'Wache' },
  healer:      { sprite: 'npc_healer',           tint: 0xffffff, label: 'Heiler' },
  blacksmith:  { sprite: 'npc_blacksmith',       tint: 0xffffff, label: 'Schmied' },
  quest_giver: { sprite: 'npc_quest_giver',      tint: 0xffffff, label: 'Auftraggeber' },
  miner:         { sprite: 'npc_miner',          tint: 0xffffff, label: 'Bergmann' },
  village_elder: { sprite: 'npc_village_elder',  tint: 0xffffff, label: 'Dorfältester' },
  watchman:      { sprite: 'npc_watchman_lantern', tint: 0xffffff, label: 'Wächter' },
  cat:           { sprite: 'npc_cat',            tint: 0xffffff, label: 'Katze' },
  dog:           { sprite: 'npc_dog',            tint: 0xffffff, label: 'Hund' },
  child:         { sprite: 'npc_child',          tint: 0xffffff, label: 'Kind' },
  // Asset-Drop 2026-05-27
  baker:       { sprite: 'npc_baker',            tint: 0xffffff, label: 'Bäcker' },
  carpenter:   { sprite: 'npc_carpenter',        tint: 0xffffff, label: 'Zimmermann' },
  fisher:      { sprite: 'npc_fisher',           tint: 0xffffff, label: 'Fischer' },
  hunter:      { sprite: 'npc_hunter',           tint: 0xffffff, label: 'Jäger' },
  innkeeper:   { sprite: 'npc_innkeeper',        tint: 0xffffff, label: 'Wirt' },
  peasant:     { sprite: 'npc_peasant',          tint: 0xffffff, label: 'Landarbeiter' },
  priest:      { sprite: 'npc_priest',           tint: 0xffffff, label: 'Priester' },
  scribe:      { sprite: 'npc_scribe',           tint: 0xffffff, label: 'Schreiber' },
  tailor:      { sprite: 'npc_tailor',           tint: 0xffffff, label: 'Schneider' },
  woodcutter:  { sprite: 'npc_woodcutter',       tint: 0xffffff, label: 'Holzfäller' },
  // ─── Asset-Drop 2026-05-27b: Nutztiere ──────────────────────────────────
  cow:           { sprite: 'animal_cow',            tint: 0xffffff, label: 'Kuh' },
  bull:          { sprite: 'animal_bull',           tint: 0xffffff, label: 'Stier' },
  calf:          { sprite: 'animal_calf',           tint: 0xffffff, label: 'Kalb' },
  ox:            { sprite: 'animal_ox',             tint: 0xffffff, label: 'Ochse' },
  sheep:         { sprite: 'animal_sheep',          tint: 0xffffff, label: 'Schaf' },
  ram:           { sprite: 'animal_ram',            tint: 0xffffff, label: 'Widder' },
  lamb:          { sprite: 'animal_lamb',           tint: 0xffffff, label: 'Lamm' },
  sheared_sheep: { sprite: 'animal_sheared_sheep',  tint: 0xffffff, label: 'Geschorenes Schaf' },
  pig:           { sprite: 'animal_pig',            tint: 0xffffff, label: 'Schwein' },
  piglet:        { sprite: 'animal_piglet',         tint: 0xffffff, label: 'Ferkel' },
  boar_domestic: { sprite: 'animal_boar_domestic',  tint: 0xffffff, label: 'Eber' },
  goat:          { sprite: 'animal_goat',           tint: 0xffffff, label: 'Ziege' },
  buck_goat:     { sprite: 'animal_buck_goat',      tint: 0xffffff, label: 'Ziegenbock' },
  kid_goat:      { sprite: 'animal_kid_goat',       tint: 0xffffff, label: 'Zicklein' },
  horse:         { sprite: 'animal_horse',          tint: 0xffffff, label: 'Pferd' },
  draft_horse:   { sprite: 'animal_draft_horse',    tint: 0xffffff, label: 'Kaltblut' },
  foal:          { sprite: 'animal_foal',           tint: 0xffffff, label: 'Fohlen' },
  donkey:        { sprite: 'animal_donkey',         tint: 0xffffff, label: 'Esel' },
  mule:          { sprite: 'animal_mule',           tint: 0xffffff, label: 'Maultier' },
  // Geflügel
  chicken_hen:   { sprite: 'animal_chicken_hen',    tint: 0xffffff, label: 'Henne' },
  rooster:       { sprite: 'animal_rooster',        tint: 0xffffff, label: 'Hahn' },
  chick:         { sprite: 'animal_chick',          tint: 0xffffff, label: 'Küken' },
  duck:          { sprite: 'animal_duck',           tint: 0xffffff, label: 'Ente' },
  drake:         { sprite: 'animal_drake',          tint: 0xffffff, label: 'Erpel' },
  duckling:      { sprite: 'animal_duckling',       tint: 0xffffff, label: 'Entenküken' },
  goose:         { sprite: 'animal_goose',          tint: 0xffffff, label: 'Gans' },
  gander:        { sprite: 'animal_gander',         tint: 0xffffff, label: 'Ganter' },
  gosling:       { sprite: 'animal_gosling',        tint: 0xffffff, label: 'Gänseküken' },
  // ─── Asset-Drop 2026-05-27c: Karawanen-Wagen (NPC-Kinds) ───────────────
  farm_cart_hay:        { sprite: 'cart_farm_cart_hay',        tint: 0xffffff, label: 'Heuwagen' },
  handcart_empty:       { sprite: 'cart_handcart_empty',       tint: 0xffffff, label: 'Handkarren' },
  horse_cart_single:    { sprite: 'cart_horse_cart_single',    tint: 0xffffff, label: 'Pferdewagen' },
  market_wagon_covered: { sprite: 'cart_market_wagon_covered', tint: 0xffffff, label: 'Marktwagen' },
  // ─── Hostile Humans (Räuber-Typen) ─────────────────────────────────────
  bandit:    { sprite: 'npc_bandit',  tint: 0xffffff, label: 'Bandit' },
  robber:    { sprite: 'npc_robber',  tint: 0xffffff, label: 'Räuber' },
  thief:     { sprite: 'npc_thief',   tint: 0xffffff, label: 'Dieb' },
  // Welle 28: Wald-Tiere
  fox:       { sprite: 'animal_fox',    tint: 0xffffff, label: 'Fuchs' },
  rabbit:    { sprite: 'animal_rabbit', tint: 0xffffff, label: 'Hase' },
  // Welle 29e: Disaster-Mob
  locust_swarm: { sprite: 'mob_locust_swarm_idle_1', tint: 0xffffff, label: 'Heuschreckenschwarm' },
  frog_swarm:   { sprite: 'animal_frog_swarm',       tint: 0xffffff, label: 'Froschschwarm' },
  // Creatures
  goblin:   { sprite: 'monster_goblin',   tint: 0xffffff, label: 'Goblin' },
  wolf:     { sprite: 'monster_wolf',     tint: 0xffffff, label: 'Wolf' },
  skeleton: { sprite: 'monster_skeleton', tint: 0xffffff, label: 'Skelett' },
  spider:   { sprite: 'monster_spider',   tint: 0xffffff, label: 'Spinne' },
  slime:    { sprite: 'monster_slime',    tint: 0xffffff, label: 'Schleim' },
  // Welle 3-Mobs
  rat:      { sprite: 'monster_rat',      tint: 0xffffff, label: 'Ratte' },
  bat:      { sprite: 'monster_bat',      tint: 0xffffff, label: 'Fledermaus' },
  zombie:   { sprite: 'monster_zombie',   tint: 0xffffff, label: 'Zombie' },
  boar:     { sprite: 'monster_boar',     tint: 0xffffff, label: 'Wildschwein' },
  bear:     { sprite: 'monster_bear',     tint: 0xffffff, label: 'Bär' },
  // Bosse
  ogre:         { sprite: 'monster_ogre',         tint: 0xffffff, label: 'Ogre' },
  necromancer:  { sprite: 'monster_necromancer',  tint: 0xffffff, label: 'Nekromant' },
  dragon_whelp: { sprite: 'monster_dragon_whelp', tint: 0xffffff, label: 'Drachling' },
  // Welle 13 — neue Monster
  stag:           { sprite: 'monster_stag',           tint: 0xffffff, label: 'Hirsch' },
  lynx:           { sprite: 'monster_lynx',           tint: 0xffffff, label: 'Luchs' },
  cougar:         { sprite: 'monster_cougar',         tint: 0xffffff, label: 'Puma' },
  wolverine:      { sprite: 'monster_wolverine',      tint: 0xffffff, label: 'Vielfraß' },
  dire_wolf:      { sprite: 'monster_dire_wolf',      tint: 0xffffff, label: 'Schreckenswolf' },
  wolf_alpha:     { sprite: 'monster_wolf_alpha',     tint: 0xffffff, label: 'Alpha-Wolf' },
  cave_bear:      { sprite: 'monster_cave_bear',      tint: 0xffffff, label: 'Höhlenbär' },
  polar_bear:     { sprite: 'monster_polar_bear',     tint: 0xffffff, label: 'Eisbär' },
  crocodile:      { sprite: 'monster_crocodile',      tint: 0xffffff, label: 'Krokodil' },
  cobra:          { sprite: 'monster_cobra',          tint: 0xffffff, label: 'Kobra' },
  slimelet:       { sprite: 'monster_slimelet',       tint: 0xffffff, label: 'Schleimlein' },
  fae_mite:       { sprite: 'monster_fae_mite',       tint: 0xffffff, label: 'Feen-Milbe' },
  gloom_moth:     { sprite: 'monster_gloom_moth',     tint: 0xffffff, label: 'Düstermotte' },
  ember_newt:     { sprite: 'monster_ember_newt',     tint: 0xffffff, label: 'Glutmolch' },
  ember_rat:      { sprite: 'monster_ember_rat',      tint: 0xffffff, label: 'Aschratte' },
  shadow_bat:     { sprite: 'monster_shadow_bat',     tint: 0xffffff, label: 'Schattenfledermaus' },
  thorn_scarab:   { sprite: 'monster_thorn_scarab',   tint: 0xffffff, label: 'Dornenkäfer' },
  crystal_beetle: { sprite: 'monster_crystal_beetle', tint: 0xffffff, label: 'Kristallkäfer' },
  crystal_tick:   { sprite: 'monster_crystal_tick',   tint: 0xffffff, label: 'Kristallzecke' },
  frost_sprite:   { sprite: 'monster_frost_sprite',   tint: 0xffffff, label: 'Frostgeist' },
  fire_imp:       { sprite: 'monster_fire_imp',       tint: 0xffffff, label: 'Feuerteufel' },
  mushroom_imp:   { sprite: 'monster_mushroom_imp',   tint: 0xffffff, label: 'Pilzkobold' },
  thornling:      { sprite: 'monster_thornling',      tint: 0xffffff, label: 'Dornenkind' },
  treant:         { sprite: 'monster_treant',         tint: 0xffffff, label: 'Baumhirte' },
  stone_golem:    { sprite: 'monster_stone_golem',    tint: 0xffffff, label: 'Steingolem' },
  crystal_golem:  { sprite: 'monster_crystal_golem',  tint: 0xffffff, label: 'Kristallgolem' },
  gargoyle:       { sprite: 'monster_gargoyle',       tint: 0xffffff, label: 'Gargoyle' },
  bone_crawler:   { sprite: 'monster_bone_crawler',   tint: 0xffffff, label: 'Knochenkriecher' },
  giant_spider:   { sprite: 'monster_giant_spider',   tint: 0xffffff, label: 'Riesenspinne' },
  minotaur:       { sprite: 'monster_minotaur',       tint: 0xffffff, label: 'Minotaur' },
  harpy:          { sprite: 'monster_harpy',          tint: 0xffffff, label: 'Harpyie' },
  basilisk:       { sprite: 'monster_basilisk',       tint: 0xffffff, label: 'Basilisk' },
  chimera:        { sprite: 'monster_chimera',        tint: 0xffffff, label: 'Chimäre' },
  griffin:        { sprite: 'monster_griffin',        tint: 0xffffff, label: 'Greif' },
  hydra:          { sprite: 'monster_hydra',          tint: 0xffffff, label: 'Hydra' },
  manticore:      { sprite: 'monster_manticore',      tint: 0xffffff, label: 'Mantikor' },
};

/** Kinds die als feindliche Creatures gelten. */
export const CREATURE_KINDS: ReadonlySet<string> = new Set([
  'goblin','wolf','skeleton','spider','slime',
  'rat','bat','zombie','bandit','robber','thief','boar','bear',
  'ogre','necromancer','dragon_whelp',
  // Welle 13
  'stag','lynx','cougar','wolverine','dire_wolf','wolf_alpha',
  'cave_bear','polar_bear','crocodile','cobra',
  'slimelet','fae_mite','gloom_moth','ember_newt','ember_rat',
  'shadow_bat','thorn_scarab','crystal_beetle','crystal_tick',
  'frost_sprite','fire_imp','mushroom_imp','thornling','treant',
  'stone_golem','crystal_golem','gargoyle','bone_crawler','giant_spider',
  'minotaur','harpy','basilisk','chimera','griffin','hydra','manticore',
  'frog_swarm',
  // Welle 14 — professional asset-drop (sync mit backend/npc_worker.CREATURE_KINDS)
  'razorback_vermin','spined_abyss_larva','reed_walker','redland_scavenger',
  'mossback_warden','grave_wraith','serpent_oracle','urtikus_eye_fiend',
  'mantis_chimera','iron_spider','dendroid_guardian','blood_antler_drake',
  'kaiju_thornback','void_eye_brute','frost_rune_boar_prime',
  'magma_shell_devourer','rockshell_colossus',
]);

/** NPCs/Monsters mit 10-Frame Walk-Animation. */
export const ANIMATED_NPC_KINDS: readonly string[] = [
  // Welle 23 — Front-View character-Animations.
  'bandit', 'blacksmith', 'farmer', 'guard', 'healer',
  'mage', 'merchant', 'quest_giver', 'soldier', 'villager',
  // Welle 29d
  'bard', 'hermit', 'miner', 'scholar', 'village_elder',
  'watchman', 'villager_female',
  // Welle 29e — Main (16 von 30)
  'baker', 'carpenter', 'child', 'fisher', 'hunter',
  'innkeeper', 'peasant', 'priest', 'robber', 'scribe',
  'tailor', 'thief', 'wanderer', 'woodcutter',
  // Female (5 von 6)
  'farmer_female', 'guard_female', 'healer_female', 'mage_female', 'merchant_female',
  // Equip-Variants
  'bandit_axe', 'bandit_bow', 'bandit_dagger', 'bandit_spear',
  'miner_pickaxe',
  'soldier_axe', 'soldier_spear', 'soldier_sword_shield',
  'watchman_crossbow', 'watchman_lantern',
];

/** Kinds bei denen walk_left/walk_right invertiert geliefert wurden (Audit Welle 29e). */
export const NPC_FLIP_LR_KINDS: ReadonlySet<string> = new Set([
  'baker', 'bandit_bow', 'bandit_spear', 'bard',
  'healer', 'healer_female', 'mage', 'mage_female',
  'soldier_axe', 'soldier_spear', 'soldier_sword_shield',
  'villager_female', 'woodcutter',
]);

/** Preset-Walk-Config pro Player-Preset (anti-Flicker, Welle 2026-05-29). */
export const PRESET_WALK_CFG: Readonly<Record<string, PresetWalkConfig>> = {
  ember_mage:     { srcDir: 'left',  baseFacing: 'left',  flip2: false },
  iron_delver:    { srcDir: 'left',  baseFacing: 'left',  flip2: false },
  knife_runner:   { srcDir: 'left',  baseFacing: 'right', flip2: true  },
  shieldbearer:   { srcDir: 'left',  baseFacing: 'left',  flip2: false },
  wanderer_cloak: { srcDir: 'left',  baseFacing: 'left',  flip2: false },
  wild_ranger:    { srcDir: 'right', baseFacing: 'right', flip2: false },
};

/** Monster-Kinds mit Walk-Animation. */
export const ANIMATED_MONSTER_KINDS: readonly string[] = [
  // bandit raus — nutzt characters/bandit/ via ANIMATED_NPC_KINDS für Stil-Konsistenz
  'basilisk','bat','bear','boar','bone_crawler',
  'cave_bear','chimera','cobra','cougar','crocodile',
  'crystal_beetle','crystal_golem','crystal_tick',
  'dire_wolf','dragon_whelp','ember_newt','ember_rat',
  'fae_mite','fire_imp','frost_sprite','gargoyle',
  'giant_spider','gloom_moth','goblin','griffin','harpy',
  'hydra','lynx','manticore','minotaur','mushroom_imp',
  'necromancer','ogre','polar_bear','rat','shadow_bat',
  'skeleton','slime','slimelet','spider','stag',
  'stone_golem','thornling','thorn_scarab','treant',
  'wolf','wolf_alpha','wolverine','zombie',
];
