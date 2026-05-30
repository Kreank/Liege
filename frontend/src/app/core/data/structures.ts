// Strukturen-Tabelle — portiert aus frontend/legacy/app.js Z. 586-820.
// 1:1-Spiegel; bei Duplikat-Keys im Legacy (Asset-Drop 2026-05-27b überschreibt
// Welle 24) übernehmen wir die spätere Definition (die in JS auch gewinnt).
import type {
  StructureDef,
  StructureFootprint,
} from '../models/structure.model';
import { SIGN_VARIANTS } from './sign-variants';

// ─── Natürliche Welt-Deko (nicht im Bau-Menü, aber harvest-bar) ───────────
export const NATURAL_STRUCTURE_TYPES: ReadonlySet<string> = new Set([
  'tree_oak','tree_pine','tree_dead','tree_stump','fallen_log',
  'bush','tall_grass','flowers','mushrooms',
  'rock_small','rock_large','rock_mossy',
  'lily_pads','reeds','dock_straight','wooden_bridge','shipwreck',
  'broken_cart','barrel','crate','sack','fence',
  'ruin_pillar','rubble','statue_broken',
  // Welle 11
  'camp_tent','cooking_pot','bones_scatter','gravestone',
  'dock_corner','boat_small','anchor','fishing_net','driftwood',
  // Farming-Drop 2026-05-26 — wilde Sträucher / Pflanzen / Obstbäume
  'strawberry_bush','blueberry_bush','blackberry_bush','raspberry_bush',
  'apple_tree','pear_tree','plum_tree','cherry_tree',
  'carrot_plant','potato_plant','cucumber_plant','tomato_plant',
  'onion_plant','cabbage_plant','pumpkin_plant','corn_plant',
  'wheat_seedling','wheat_grown',
]);

// ─── Mutable Internal-Aufbau (kein Export) ────────────────────────────────
// Wir bauen die Map über eine `Record<string, StructureDef>`-Funktion auf,
// damit Late-Wins-Semantik (Welle 24 → 2026-05-27b → SIGN_VARIANTS) ohne
// Duplikat-Key-Errors im Object-Literal funktioniert. Das Ergebnis wird als
// `Readonly` exportiert.
function buildStructureMap(): Record<string, StructureDef> {
  const m: Record<string, StructureDef> = {};
  const add = (type: string, def: StructureDef): void => {
    m[type] = def;
  };

  add('wall',        { key: '1', name: 'Mauer',       icon: '🧱', blocking: true,  sprite: 'struct_wall',       hasMaterial: true });
  add('floor',       { key: '2', name: 'Boden',       icon: '▦',  blocking: false, sprite: 'struct_floor',      hasMaterial: true });
  add('campfire',    { key: '3', name: 'Lagerfeuer',  icon: '🔥', blocking: false, sprite: 'struct_campfire' });
  add('marker',      { key: '4', name: 'Marker',      icon: '🚩', blocking: false, sprite: 'struct_marker'   });
  add('chest',       { key: '5', name: 'Truhe',       icon: '📦', blocking: true,  sprite: 'struct_chest'    });
  add('workbench',   { key: '6', name: 'Werkbank',    icon: '🪓', blocking: true,  sprite: 'struct_workbench'});
  add('furnace',     { key: '7', name: 'Schmelze',    icon: '🌋', blocking: true,  sprite: 'struct_furnace'  });
  add('anvil',       { key: '8', name: 'Amboss',      icon: '⚒️', blocking: true,  sprite: 'struct_anvil'    });
  add('bed',         { key: '9', name: 'Bett',        icon: '🛏️', blocking: false, sprite: 'struct_bed'      });
  add('well',        { key: '0', name: 'Brunnen',     icon: '⛲', blocking: true,  sprite: 'struct_well'     });
  add('farm_plot',   { key: '',  name: 'Acker',       icon: '🌱', blocking: false, sprite: 'struct_farm_plot'});
  add('spike_trap',  { key: '',  name: 'Stachelfalle',icon: '🗡️', blocking: false, sprite: 'struct_spike_trap'});
  add('poison_trap', { key: '',  name: 'Giftfalle',   icon: '💀', blocking: false, sprite: 'struct_poison_trap'});
  add('stairs_down', { key: '',  name: 'Treppe nach unten', icon: '🏚️', blocking: false, sprite: 'struct_stairs_down'});

  // Deko: Natur
  add('tree_oak',   { key: '', name: 'Eiche',          icon: '🌳', blocking: true,  sprite: 'prop_tree_oak' });
  add('tree_pine',  { key: '', name: 'Nadelbaum',      icon: '🌲', blocking: true,  sprite: 'prop_tree_pine' });
  add('tree_dead',  { key: '', name: 'Toter Baum',     icon: '🪾', blocking: true,  sprite: 'prop_tree_dead' });
  add('tree_stump', { key: '', name: 'Baumstumpf',     icon: '🪵', blocking: true,  sprite: 'prop_tree_stump' });
  add('fallen_log', { key: '', name: 'Gefällter Stamm',icon: '🪵', blocking: true,  sprite: 'prop_fallen_log' });
  add('bush',       { key: '', name: 'Busch',          icon: '🌿', blocking: false, sprite: 'prop_bush' });
  add('tall_grass', { key: '', name: 'Hohes Gras',     icon: '🌾', blocking: false, sprite: 'prop_tall_grass' });
  add('flowers',    { key: '', name: 'Blumen',         icon: '🌸', blocking: false, sprite: 'prop_flowers' });
  add('mushrooms',  { key: '', name: 'Pilze',          icon: '🍄', blocking: false, sprite: 'prop_mushrooms' });
  add('rock_small', { key: '', name: 'Kleiner Felsen', icon: '🪨', blocking: true,  sprite: 'prop_rock_small' });
  add('rock_large', { key: '', name: 'Großer Felsen',  icon: '🪨', blocking: true,  sprite: 'prop_rock_large' });
  add('rock_mossy', { key: '', name: 'Moosfelsen',     icon: '🪨', blocking: true,  sprite: 'prop_rock_mossy' });

  // Deko: Wasser
  add('lily_pads',     { key: '', name: 'Seerosen',     icon: '🪷', blocking: false, sprite: 'prop_lily_pads' });
  add('reeds',         { key: '', name: 'Schilf',       icon: '🌾', blocking: false, sprite: 'prop_reeds' });
  add('dock_straight', { key: '', name: 'Steg',         icon: '🪵', blocking: false, sprite: 'prop_dock_straight' });
  add('wooden_bridge', { key: '', name: 'Holzbrücke',   icon: '🌉', blocking: false, sprite: 'prop_wooden_bridge' });
  add('shipwreck',     { key: '', name: 'Schiffswrack', icon: '🚢', blocking: true,  sprite: 'prop_shipwreck' });

  // Deko: Siedlung
  add('broken_cart', { key: '', name: 'Karren', icon: '🛒', blocking: true,  sprite: 'prop_broken_cart' });
  add('barrel',      { key: '', name: 'Fass',   icon: '🛢️', blocking: true,  sprite: 'prop_barrel' });
  add('crate',       { key: '', name: 'Kiste',  icon: '📦', blocking: true,  sprite: 'prop_crate' });
  add('sack',        { key: '', name: 'Sack',   icon: '🧺', blocking: false, sprite: 'prop_sack' });
  add('fence',       { key: '', name: 'Zaun',   icon: '🚧', blocking: true,  sprite: 'fence_straight_ns' });
  add('garden_gate_ew_closed', { key: '', name: 'Gartentor ↔', icon: '🚪', blocking: true,  sprite: 'garden_gate_ew_closed' });
  add('garden_gate_ew_open',   { key: '', name: 'Gartentor ↔', icon: '🚪', blocking: false, sprite: 'garden_gate_ew_open',  notBuildable: true });
  add('garden_gate_ns_closed', { key: '', name: 'Gartentor ↕', icon: '🚪', blocking: true,  sprite: 'garden_gate_ns_closed' });
  add('garden_gate_ns_open',   { key: '', name: 'Gartentor ↕', icon: '🚪', blocking: false, sprite: 'garden_gate_ns_open',  notBuildable: true });

  // Türen
  add('door_wood',       { key: '', name: 'Holztür',       icon: '🚪', blocking: true,  sprite: 'door_wood' });
  add('door_wood_open',  { key: '', name: 'Holztür offen', icon: '🚪', blocking: false, sprite: 'door_wood_open',  notBuildable: true });
  add('door_iron',       { key: '', name: 'Eisentür',      icon: '🚪', blocking: true,  sprite: 'door_iron' });
  add('door_iron_open',  { key: '', name: 'Eisentür offen',icon: '🚪', blocking: false, sprite: 'door_iron_open',  notBuildable: true });
  add('door_stone',      { key: '', name: 'Steintür',      icon: '🚪', blocking: true,  sprite: 'door_stone' });
  add('door_stone_open', { key: '', name: 'Steintür offen',icon: '🚪', blocking: false, sprite: 'door_stone_open', notBuildable: true });
  add('door_reinforced', { key: '', name: 'Verstärkte Tür',icon: '🚪', blocking: true,  sprite: 'door_reinforced' });

  // Treppen
  add('stairs_wood_up',    { key: '', name: 'Holztreppe hoch',  icon: '🪜', blocking: false, sprite: 'stairs_wood_up' });
  add('stairs_wood_down',  { key: '', name: 'Holztreppe runter',icon: '🪜', blocking: false, sprite: 'stairs_wood_down' });
  add('stairs_stone_up',   { key: '', name: 'Steintreppe hoch', icon: '🪜', blocking: false, sprite: 'stairs_stone_up' });
  add('stairs_stone_down', { key: '', name: 'Steintreppe runter',icon:'🪜', blocking: false, sprite: 'stairs_stone_down' });

  // Deko: Ruinen
  add('ruin_pillar',   { key: '', name: 'Säule',   icon: '🏛️', blocking: true,  sprite: 'prop_ruin_pillar' });
  add('rubble',        { key: '', name: 'Trümmer', icon: '⛏️', blocking: false, sprite: 'prop_rubble' });
  add('statue_broken', { key: '', name: 'Statue',  icon: '🗿', blocking: true,  sprite: 'prop_statue_broken' });

  // Welle 24 — World-Detail (Schilder + Transport-Wagen, alle notBuildable)
  add('crossroads_signpost', { key: '', name: 'Crossroads Signpost', icon: '🪧', blocking: true, sprite: 'struct_crossroads_signpost', notBuildable: true });
  add('signpost_village', { key: '', name: 'Signpost Village', icon: '🪧', blocking: true, sprite: 'struct_signpost_village', notBuildable: true });
  add('signpost_market',  { key: '', name: 'Signpost Market',  icon: '🪧', blocking: true, sprite: 'struct_signpost_market',  notBuildable: true });
  add('signpost_inn',     { key: '', name: 'Signpost Inn',     icon: '🪧', blocking: true, sprite: 'struct_signpost_inn',     notBuildable: true });
  add('signpost_church',  { key: '', name: 'Signpost Church',  icon: '🪧', blocking: true, sprite: 'struct_signpost_church',  notBuildable: true });
  add('signpost_mill',    { key: '', name: 'Signpost Mill',    icon: '🪧', blocking: true, sprite: 'struct_signpost_mill',    notBuildable: true });
  add('signpost_mine',    { key: '', name: 'Signpost Mine',    icon: '🪧', blocking: true, sprite: 'struct_signpost_mine',    notBuildable: true });
  add('warning_bandits',  { key: '', name: 'Warning Bandits',  icon: '🪧', blocking: true, sprite: 'struct_warning_bandits',  notBuildable: true });
  add('signpost_town',    { key: '', name: 'Signpost Town',    icon: '🪧', blocking: true, sprite: 'struct_signpost_town',    notBuildable: true });
  add('signpost_farm',    { key: '', name: 'Signpost Farm',    icon: '🪧', blocking: true, sprite: 'struct_signpost_farm',    notBuildable: true });
  add('signpost_forest',  { key: '', name: 'Signpost Forest',  icon: '🪧', blocking: true, sprite: 'struct_signpost_forest',  notBuildable: true });
  add('signpost_docks',   { key: '', name: 'Signpost Docks',   icon: '🪧', blocking: true, sprite: 'struct_signpost_docks',   notBuildable: true });
  add('signpost_graveyard', { key: '', name: 'Signpost Graveyard', icon: '🪧', blocking: true, sprite: 'struct_signpost_graveyard', notBuildable: true });
  add('road_marker_stone', { key: '', name: 'Road Marker Stone', icon: '🪧', blocking: true, sprite: 'struct_road_marker_stone', notBuildable: true });
  add('boundary_post',     { key: '', name: 'Boundary Post',     icon: '🪧', blocking: true, sprite: 'struct_boundary_post',     notBuildable: true });
  add('blank_weathered_signpost', { key: '', name: 'Blank Weathered Signpost', icon: '🪧', blocking: true, sprite: 'struct_blank_weathered_signpost', notBuildable: true });
  add('bakery_sign',        { key: '', name: 'Bakery Sign',        icon: '🏪', blocking: true, sprite: 'struct_bakery_sign',        notBuildable: true });
  add('blacksmith_sign',    { key: '', name: 'Blacksmith Sign',    icon: '🏪', blocking: true, sprite: 'struct_blacksmith_sign',    notBuildable: true });
  add('tailor_sign',        { key: '', name: 'Tailor Sign',        icon: '🏪', blocking: true, sprite: 'struct_tailor_sign',        notBuildable: true });
  add('inn_sign',           { key: '', name: 'Inn Sign',           icon: '🏪', blocking: true, sprite: 'struct_inn_sign',           notBuildable: true });
  add('stable_sign',        { key: '', name: 'Stable Sign',        icon: '🏪', blocking: true, sprite: 'struct_stable_sign',        notBuildable: true });
  add('market_sign',        { key: '', name: 'Market Sign',        icon: '🏪', blocking: true, sprite: 'struct_market_sign',        notBuildable: true });
  add('apothecary_sign',    { key: '', name: 'Apothecary Sign',    icon: '🏪', blocking: true, sprite: 'struct_apothecary_sign',    notBuildable: true });
  add('carpenter_sign',     { key: '', name: 'Carpenter Sign',     icon: '🏪', blocking: true, sprite: 'struct_carpenter_sign',     notBuildable: true });
  add('miller_sign',        { key: '', name: 'Miller Sign',        icon: '🏪', blocking: true, sprite: 'struct_miller_sign',        notBuildable: true });
  add('dairy_sign',         { key: '', name: 'Dairy Sign',         icon: '🏪', blocking: true, sprite: 'struct_dairy_sign',         notBuildable: true });
  add('butcher_sign',       { key: '', name: 'Butcher Sign',       icon: '🏪', blocking: true, sprite: 'struct_butcher_sign',       notBuildable: true });
  add('fishmonger_sign',    { key: '', name: 'Fishmonger Sign',    icon: '🏪', blocking: true, sprite: 'struct_fishmonger_sign',    notBuildable: true });
  add('tanner_sign',        { key: '', name: 'Tanner Sign',        icon: '🏪', blocking: true, sprite: 'struct_tanner_sign',        notBuildable: true });
  add('weaver_sign',        { key: '', name: 'Weaver Sign',        icon: '🏪', blocking: true, sprite: 'struct_weaver_sign',        notBuildable: true });
  add('tavern_red_lion_sign', { key: '', name: 'Tavern Red Lion Sign', icon: '🏪', blocking: true, sprite: 'struct_tavern_red_lion_sign', notBuildable: true });
  add('scribe_sign',        { key: '', name: 'Scribe Sign',        icon: '🏪', blocking: true, sprite: 'struct_scribe_sign',        notBuildable: true });
  add('handcart_empty',     { key: '', name: 'Handcart Empty',     icon: '🛒', blocking: true, sprite: 'struct_handcart_empty',     notBuildable: true });
  add('handcart_crates',    { key: '', name: 'Handcart Crates',    icon: '🛒', blocking: true, sprite: 'struct_handcart_crates',    notBuildable: true });
  add('farm_cart_empty',    { key: '', name: 'Farm Cart Empty',    icon: '🛒', blocking: true, sprite: 'struct_farm_cart_empty',    notBuildable: true });
  add('farm_cart_hay',      { key: '', name: 'Farm Cart Hay',      icon: '🛒', blocking: true, sprite: 'struct_farm_cart_hay',      notBuildable: true });
  add('farm_cart_barrels',  { key: '', name: 'Farm Cart Barrels',  icon: '🛒', blocking: true, sprite: 'struct_farm_cart_barrels',  notBuildable: true });
  add('market_wagon_covered', { key: '', name: 'Market Wagon Covered', icon: '🛒', blocking: true, sprite: 'struct_market_wagon_covered', notBuildable: true });
  add('merchant_wagon_closed', { key: '', name: 'Merchant Wagon Closed', icon: '🛒', blocking: true, sprite: 'struct_merchant_wagon_closed', notBuildable: true });
  add('horse_cart_single',  { key: '', name: 'Horse Cart Single',  icon: '🐎', blocking: true, sprite: 'struct_horse_cart_single',  notBuildable: true });
  add('horse_cart_pair',    { key: '', name: 'Horse Cart Pair',    icon: '🐎', blocking: true, sprite: 'struct_horse_cart_pair',    notBuildable: true });
  add('ox_cart',            { key: '', name: 'Ox Cart',            icon: '🐎', blocking: true, sprite: 'struct_ox_cart',            notBuildable: true });
  add('donkey_pack_cart',   { key: '', name: 'Donkey Pack Cart',   icon: '🐎', blocking: true, sprite: 'struct_donkey_pack_cart',   notBuildable: true });
  add('broken_wagon_large', { key: '', name: 'Broken Wagon Large', icon: '🛒', blocking: true, sprite: 'struct_broken_wagon_large', notBuildable: true });
  add('wagon_wheel_loose',  { key: '', name: 'Wagon Wheel Loose',  icon: '🛒', blocking: true, sprite: 'struct_wagon_wheel_loose',  notBuildable: true });
  add('wagon_harness',      { key: '', name: 'Wagon Harness',      icon: '🛒', blocking: true, sprite: 'struct_wagon_harness',      notBuildable: true });
  add('hitching_post',      { key: '', name: 'Hitching Post',      icon: '🛒', blocking: true, sprite: 'struct_hitching_post',      notBuildable: true });
  add('wheelbarrow_tools',  { key: '', name: 'Wheelbarrow Tools',  icon: '🛒', blocking: true, sprite: 'struct_wheelbarrow_tools',  notBuildable: true });

  // Welle 24 Farm-Block (notBuildable, später durch 2026-05-27b ersetzt)
  add('feed_sack',          { key: '', name: 'Feed Sack',          icon: '🪵', blocking: true, sprite: 'struct_feed_sack',          notBuildable: true });
  add('animal_bedding_straw', { key: '', name: 'Animal Bedding Straw', icon: '🪵', blocking: true, sprite: 'struct_animal_bedding_straw', notBuildable: true });
  add('pitchfork',          { key: '', name: 'Pitchfork',          icon: '🪵', blocking: true, sprite: 'struct_pitchfork',          notBuildable: true });
  add('shovel',             { key: '', name: 'Shovel',             icon: '🪵', blocking: true, sprite: 'struct_shovel',             notBuildable: true });
  add('wooden_bucket',      { key: '', name: 'Wooden Bucket',      icon: '🪵', blocking: true, sprite: 'struct_wooden_bucket',      notBuildable: true });
  add('rope_coil',          { key: '', name: 'Rope Coil',          icon: '🪵', blocking: true, sprite: 'struct_rope_coil',          notBuildable: true });

  // Welle 23 — Gilden + Tempel + Quest-Board
  add('mage_guild',     { key: '', name: 'Magiergilde',   icon: '🔮', blocking: true,  sprite: 'struct_mage_guild',     notBuildable: true });
  add('fighters_guild', { key: '', name: 'Kriegergilde',  icon: '⚔️', blocking: true,  sprite: 'struct_fighters_guild', notBuildable: true });
  add('healers_guild',  { key: '', name: 'Heilergilde',   icon: '⚕️', blocking: true,  sprite: 'struct_healers_guild',  notBuildable: true });
  add('thieves_guild',  { key: '', name: 'Diebesgilde',   icon: '🗝️', blocking: true,  sprite: 'struct_thieves_guild',  notBuildable: true });
  add('temple',         { key: '', name: 'Tempel',        icon: '🛐', blocking: true,  sprite: 'struct_temple',         notBuildable: true });
  add('quest_board',    { key: '', name: 'Aufgabentafel', icon: '📜', blocking: true,  sprite: 'struct_quest_board' });

  // Welt-Deko Welle 11
  add('camp_tent',     { key: '', name: 'Zelt',        icon: '⛺', blocking: false, sprite: 'prop_camp_tent' });
  add('cooking_pot',   { key: '', name: 'Kochtopf',    icon: '🍲', blocking: false, sprite: 'prop_cooking_pot' });
  add('bones_scatter', { key: '', name: 'Knochen',     icon: '🦴', blocking: false, sprite: 'prop_bones_scatter' });
  add('gravestone',    { key: '', name: 'Grabstein',   icon: '🪦', blocking: true,  sprite: 'prop_gravestone' });
  add('dock_corner',   { key: '', name: 'Steg-Ecke',   icon: '🪵', blocking: false, sprite: 'prop_dock_corner' });
  add('boat_small',    { key: '', name: 'Boot',        icon: '🛶', blocking: true,  sprite: 'prop_boat_small' });
  add('anchor',        { key: '', name: 'Anker',       icon: '⚓', blocking: false, sprite: 'prop_anchor' });
  add('fishing_net',   { key: '', name: 'Fischernetz', icon: '🎣', blocking: false, sprite: 'prop_fishing_net' });
  add('driftwood',     { key: '', name: 'Treibholz',   icon: '🪵', blocking: false, sprite: 'prop_driftwood' });

  // Farming-Drop 2026-05-26
  add('strawberry_bush',{ key:'', name:'Erdbeerstrauch',  icon:'🍓', blocking:false, sprite:'prop_strawberry_bush' });
  add('blueberry_bush', { key:'', name:'Blaubeerstrauch', icon:'🫐', blocking:false, sprite:'prop_blueberry_bush' });
  add('blackberry_bush',{ key:'', name:'Brombeerstrauch', icon:'🌑', blocking:false, sprite:'prop_blackberry_bush' });
  add('raspberry_bush', { key:'', name:'Himbeerstrauch',  icon:'🌸', blocking:false, sprite:'prop_raspberry_bush' });
  add('apple_tree',     { key:'', name:'Apfelbaum',       icon:'🍎', blocking:true,  sprite:'prop_apple_tree' });
  add('pear_tree',      { key:'', name:'Birnbaum',        icon:'🍐', blocking:true,  sprite:'prop_pear_tree' });
  add('plum_tree',      { key:'', name:'Pflaumenbaum',    icon:'🟣', blocking:true,  sprite:'prop_plum_tree' });
  add('cherry_tree',    { key:'', name:'Kirschbaum',      icon:'🌸', blocking:true,  sprite:'prop_cherry_tree' });
  add('carrot_plant',   { key:'', name:'Karottenfeld',    icon:'🥕', blocking:false, sprite:'prop_carrot_plant' });
  add('potato_plant',   { key:'', name:'Kartoffelfeld',   icon:'🥔', blocking:false, sprite:'prop_potato_plant' });
  add('cucumber_plant', { key:'', name:'Gurkenpflanze',   icon:'🥒', blocking:false, sprite:'prop_cucumber_plant' });
  add('tomato_plant',   { key:'', name:'Tomatenpflanze',  icon:'🍅', blocking:false, sprite:'prop_tomato_plant' });
  add('onion_plant',    { key:'', name:'Zwiebelfeld',     icon:'🧅', blocking:false, sprite:'prop_onion_plant' });
  add('cabbage_plant',  { key:'', name:'Kohlfeld',        icon:'🥬', blocking:false, sprite:'prop_cabbage_plant' });
  add('pumpkin_plant',  { key:'', name:'Kürbisfeld',      icon:'🎃', blocking:false, sprite:'prop_pumpkin_plant' });
  add('corn_plant',     { key:'', name:'Maisfeld',        icon:'🌽', blocking:false, sprite:'prop_corn_plant' });
  add('wheat_seedling', { key:'', name:'Weizenkeimling',  icon:'🌱', blocking:false, sprite:'prop_wheat_seedling' });
  add('wheat_grown',    { key:'', name:'Weizenfeld',      icon:'🌾', blocking:false, sprite:'prop_wheat_grown' });

  // Welle 29e — Waldbrand
  add('fire_tile',         { key:'', name:'Brennender Baum',     icon:'🔥', blocking:false, sprite:'fire_flame_lick',         notBuildable:true });
  add('burned_stump',      { key:'', name:'Verkohlter Stumpf',   icon:'🪨', blocking:true,  sprite:'prop_burned_stump_01',    notBuildable:true });
  add('burned_tree_oak',   { key:'', name:'Verkohlte Eiche',     icon:'🌲', blocking:true,  sprite:'prop_burned_tree_oak',    notBuildable:true });
  add('burned_tree_pine',  { key:'', name:'Verkohlter Nadelbaum',icon:'🌲', blocking:true,  sprite:'prop_burned_tree_pine',   notBuildable:true });
  add('burned_tree_birch', { key:'', name:'Verkohlte Birke',     icon:'🌲', blocking:true,  sprite:'prop_burned_tree_birch',  notBuildable:true });
  add('ash_pile_small',    { key:'', name:'Aschehaufen',         icon:'🌫', blocking:false, sprite:'prop_ash_pile_small',     notBuildable:true });
  add('ash_pile_large',    { key:'', name:'Aschehaufen',         icon:'🌫', blocking:false, sprite:'prop_ash_pile_large',     notBuildable:true });

  // — Asset-Drop 2026-05-27b: Farm-Gebäude (überschreibt frühere Welle-24-Stubs) —
  add('barn_large',           { key:'', name:'Große Scheune',     icon:'🏚️', blocking:true,  sprite:'farm_barn_large' });
  add('barn_small',           { key:'', name:'Kleine Scheune',    icon:'🏚️', blocking:true,  sprite:'farm_barn_small' });
  add('cow_shed',             { key:'', name:'Kuhstall',          icon:'🐄', blocking:true,  sprite:'farm_cow_shed' });
  add('pigsty',               { key:'', name:'Schweinestall',     icon:'🐖', blocking:true,  sprite:'farm_pigsty' });
  add('henhouse',             { key:'', name:'Hühnerstall',       icon:'🐔', blocking:true,  sprite:'farm_henhouse' });
  add('goat_pen',             { key:'', name:'Ziegengehege',      icon:'🐐', blocking:true,  sprite:'farm_goat_pen' });
  add('sheepfold',            { key:'', name:'Schafstall',        icon:'🐑', blocking:true,  sprite:'farm_sheepfold' });
  add('stable',               { key:'', name:'Pferdestall',       icon:'🐎', blocking:true,  sprite:'farm_stable' });
  add('dovecote',             { key:'', name:'Taubenschlag',      icon:'🕊️', blocking:true,  sprite:'farm_dovecote' });
  add('dairy_house',          { key:'', name:'Milchhaus',         icon:'🥛', blocking:true,  sprite:'farm_dairy_house' });
  add('granary',              { key:'', name:'Kornspeicher',      icon:'🌾', blocking:true,  sprite:'farm_granary' });
  add('hayloft',              { key:'', name:'Heuboden',          icon:'🌾', blocking:true,  sprite:'farm_hayloft' });
  add('smokehouse',           { key:'', name:'Räucherhaus',       icon:'💨', blocking:true,  sprite:'farm_smokehouse' });
  add('cart_shed',            { key:'', name:'Wagenschuppen',     icon:'🛒', blocking:true,  sprite:'farm_cart_shed' });
  add('duck_pond',            { key:'', name:'Ententeich',        icon:'🦆', blocking:false, sprite:'farm_duck_pond' });
  add('goose_pasture_marker', { key:'', name:'Gänseweide',        icon:'🪧', blocking:false, sprite:'farm_goose_pasture_marker' });

  // Farm-Props (klein)
  add('feed_trough',          { key:'', name:'Futtertrog',        icon:'🥕', blocking:true,  sprite:'farm_feed_trough' });
  add('water_trough',         { key:'', name:'Wassertrog',        icon:'💧', blocking:true,  sprite:'farm_water_trough' });
  add('hay_bale',             { key:'', name:'Heuballen',         icon:'🌾', blocking:true,  sprite:'farm_hay_bale' });
  add('hay_stack',            { key:'', name:'Heuhaufen',         icon:'🌾', blocking:true,  sprite:'farm_hay_stack' });
  add('straw_bale',           { key:'', name:'Strohballen',       icon:'🌾', blocking:true,  sprite:'farm_straw_bale' });
  add('cheese_press',         { key:'', name:'Käsepresse',        icon:'🧀', blocking:true,  sprite:'farm_cheese_press' });
  add('butter_churn',         { key:'', name:'Butterfass',        icon:'🧈', blocking:true,  sprite:'farm_butter_churn' });
  add('milking_stool',        { key:'', name:'Melkschemel',       icon:'🪑', blocking:false, sprite:'farm_milking_stool' });
  add('nesting_box_egg',      { key:'', name:'Nistkasten',        icon:'🥚', blocking:false, sprite:'farm_nesting_box_egg' });
  add('cheese_rack',          { key:'', name:'Käseregal',         icon:'🧀', blocking:true,  sprite:'farm_cheese_rack' });
  add('wooden_fence_segment', { key:'', name:'Holzzaun-Segment',  icon:'🚧', blocking:true,  sprite:'farm_wooden_fence_segment' });
  add('fence_gate_farm',      { key:'', name:'Farm-Zauntor',      icon:'🚪', blocking:true,  sprite:'farm_fence_gate' });

  // Welle 51 — generierte Sign-Strukturen aus SIGN_VARIANTS
  for (const [slug, label, icon] of SIGN_VARIANTS) {
    m[`sign_${slug}`] = {
      key: '', name: `🪧 ${label}`, icon,
      blocking: false, sprite: `sign_${slug}`,
    };
  }
  return m;
}

export const STRUCTURE: Readonly<Record<string, StructureDef>> =
  buildStructureMap();

/** Inverse lookup: hotkey-char → structure-type, wie STRUCTURE_BY_KEY im Legacy. */
export const STRUCTURE_BY_KEY: Readonly<Record<string, string>> =
  Object.fromEntries(
    Object.entries(STRUCTURE).map(([id, s]) => [s.key, id])
  );

// Strukturen, die per Klick **abgebaut** statt benutzt werden sollen
// (Backend-Intent `attack_structure`). Default-Logik: Trees, Stones,
// Ore-Veins, Mauern + Türen + Zäune sowie Plant-Crops.
export const HARVESTABLE_STRUCTURE_PREFIXES: readonly string[] = [
  'tree_', 'stone_', 'ore_', 'rock_',
  'wall', 'fence', 'door_',
  // Crops liefern bei attack_structure ihre Ertrags-Items.
  '_plant', '_bush', '_seedling', '_grown',
];

/** Convenience-Check: matched ein Strukturtyp eines der Harvest-Präfixe? */
export function isHarvestableStructureType(type: string): boolean {
  for (const p of HARVESTABLE_STRUCTURE_PREFIXES) {
    // Präfix-Match (Standardfall) ODER Suffix-Match (für *_plant/_bush/…).
    if (p.startsWith('_')) {
      if (type.endsWith(p)) return true;
    } else if (type.startsWith(p)) {
      return true;
    }
  }
  return false;
}

// Welle 25 — Strukturen mit Interakt-Effekt (use_structure).
export const USABLE_STRUCTURE_TYPES: ReadonlySet<string> = new Set([
  'bed', 'well', 'chest', 'workbench', 'furnace', 'anvil', 'farm_plot',
  'campfire', 'cooking_pot', 'quest_board',
  // Dungeon-Eingang: Klick → use_structure (Eintritt), NICHT attack.
  'stairs_down',
  // Farm-Stationen
  'cheese_press', 'butter_churn', 'milking_stool', 'nesting_box_egg',
  'feed_trough', 'water_trough',
]);

// Strukturen mit HP (sync mit backend/structures.STRUCTURE_MAX_HP).
export const COMBAT_STRUCTURE_TYPES: ReadonlySet<string> = new Set([
  'wall', 'floor',
  'door_wood', 'door_iron', 'door_stone', 'door_reinforced',
  'door_wood_open', 'door_iron_open', 'door_stone_open',
  'garden_gate_ew_closed', 'garden_gate_ew_open',
  'garden_gate_ns_closed', 'garden_gate_ns_open',
  'fence', 'wooden_fence_segment', 'fence_gate_farm',
  'chest', 'workbench', 'furnace', 'anvil', 'bed', 'well', 'campfire',
  'barrel', 'crate', 'sack', 'marker', 'spike_trap', 'poison_trap',
  'stairs_down', 'stairs_wood_up', 'stairs_wood_down',
  'stairs_stone_up', 'stairs_stone_down',
  'camp_tent', 'cooking_pot', 'ruin_pillar', 'rubble', 'statue_broken',
  'gravestone', 'dock_corner', 'dock_straight', 'wooden_bridge',
  'boat_small', 'shipwreck', 'anchor', 'fishing_net', 'driftwood', 'broken_cart',
  // Farm-Gebäude
  'barn_large', 'barn_small', 'cow_shed', 'pigsty', 'henhouse',
  'goat_pen', 'sheepfold', 'stable', 'dovecote', 'dairy_house',
  'granary', 'hayloft', 'smokehouse', 'cart_shed',
  'feed_trough', 'water_trough', 'hay_bale', 'hay_stack', 'straw_bale',
  'cheese_press', 'butter_churn', 'milking_stool', 'nesting_box_egg',
  'cheese_rack', 'quest_board',
]);

// Display-Größe pro Struktur-Typ relativ zu TILE_SIZE. Default 1.0.
export const STRUCTURE_DISPLAY_SCALE: Readonly<Record<string, number>> = {
  camp_tent:     1.5,
  shipwreck:     1.7,
  boat_small:    1.3,
  broken_cart:   1.3,
  ruin_pillar:   1.4,
  statue_broken: 1.3,
  gravestone:    1.2,
  tree_oak:      1.4,
  tree_pine:     1.4,
  palm_tree:     1.5,
  treant:        1.5,
  well:          1.3,
  anvil:         1.2,
  furnace:       1.3,
  workbench:     1.2,
  // Proportions-Pass 2026-05-29
  bed:           1.6,
  campfire:      1.0,
  cooking_pot:   0.7,
  chest:         0.85,
  barrel:        0.7,
  crate:         0.8,
  sack:          0.6,
  hay_bale:      0.95,
  torch:         0.7,
  brazier:       0.8,
};

// Welle 25: Multi-Tile-Footprint (mirror of backend STRUCTURE_FOOTPRINT).
export const STRUCTURE_FOOTPRINT: Readonly<Record<string, StructureFootprint>> = {
  barn_large:           [4, 4],
  barn_small:           [3, 3],
  stable:               [4, 3],
  granary:              [3, 3],
  cow_shed:             [3, 2],
  sheepfold:            [3, 2],
  goat_pen:             [3, 2],
  pigsty:               [2, 2],
  henhouse:             [2, 2],
  dovecote:             [2, 2],
  dairy_house:          [3, 2],
  hayloft:              [3, 2],
  smokehouse:           [2, 2],
  cart_shed:            [3, 2],
  duck_pond:            [3, 3],
  goose_pasture_marker: [2, 2],
  mage_guild:           [4, 4],
  fighters_guild:       [4, 4],
  healers_guild:        [4, 4],
  thieves_guild:        [4, 4],
  temple:               [5, 5],
};

// Material-Auswahl für Wände/Böden.
export const MATERIALS = ['stone', 'wood', 'straw'] as const;
export type MaterialKey = (typeof MATERIALS)[number];
export const MATERIAL_LABELS: Readonly<Record<MaterialKey, string>> = {
  stone: 'Stein',
  wood: 'Holz',
  straw: 'Stroh',
};

// Wand-Auto-Tiling Bitmask N=1 E=2 S=4 W=8 → Sprite-Variante.
export const WALL_MASK_TO_VARIANT: Readonly<Record<number, string>> = {
  0:  'straight_ns',
  1:  'end_s',
  2:  'end_w',
  3:  'corner_ne',
  4:  'end_n',
  5:  'straight_ns',
  6:  'corner_es',
  7:  'straight_ns',
  8:  'end_e',
  9:  'corner_wn',
  10: 'straight_ew',
  11: 'straight_ew',
  12: 'corner_sw',
  13: 'straight_ns',
  14: 'straight_ew',
  15: 'straight_ew',
};
