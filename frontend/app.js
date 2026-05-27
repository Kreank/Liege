// === MobileUI: single source of truth für Mobile/Orientation-State ===
// Setzt body-Klassen (is-mobile/is-portrait/is-landscape/is-narrow) die CSS-Regeln
// ansprechen können. Reagiert auf resize + orientationchange.
window.MobileUI = (function () {
  const state = { isMobile: false, isPortrait: false, isLandscape: false, isNarrow: false };
  function compute() {
    const isTouch = ('ontouchstart' in window) ||
                    (navigator.maxTouchPoints > 0) ||
                    window.matchMedia('(pointer: coarse)').matches;
    const w = window.innerWidth;
    const h = window.innerHeight;
    state.isMobile   = isTouch && Math.min(w, h) <= 900;  // Mobile oder kleines Tablet
    state.isPortrait = state.isMobile && h >= w;
    state.isLandscape= state.isMobile && w > h;
    state.isNarrow   = w < 380;
    const b = document.body;
    b.classList.toggle('is-mobile',    state.isMobile);
    b.classList.toggle('is-portrait',  state.isPortrait);
    b.classList.toggle('is-landscape', state.isLandscape);
    b.classList.toggle('is-narrow',    state.isNarrow);
  }
  compute();
  window.addEventListener('resize', compute);
  window.addEventListener('orientationchange', () => setTimeout(compute, 200));
  return state;
})();

// === build-bar touch buttons (close × und rotate ↻) — funktioniert auf allen Geräten ===
(function () {
  const closeBtn = document.getElementById('bb-close-btn');
  const rotBtn   = document.getElementById('bb-rotate-btn');
  function getScene() {
    if (!window._gameInstance) return null;
    return window._gameInstance.scene.getScene('WorldScene') || null;
  }
  function withRetry(fn) {
    const sc = getScene();
    if (sc) fn(sc); else setTimeout(() => withRetry(fn), 200);
  }
  function bind(btn, handler) {
    if (!btn) return;
    const tap = (ev) => { ev.preventDefault(); ev.stopPropagation(); handler(); };
    btn.addEventListener('click', tap);
    btn.addEventListener('touchend', tap, { passive: false });
  }
  bind(closeBtn, () => withRetry((sc) => { if (sc.buildMode) sc.toggleBuildMode(); }));
  bind(rotBtn, () => withRetry((sc) => {
    if (!sc.buildMode) return;
    sc.placeRotation = ((sc.placeRotation || 0) + 90) % 360;
    if (typeof sc._refreshPlaceGhost === 'function')   sc._refreshPlaceGhost();
    if (typeof sc._refreshRotationLabel === 'function') sc._refreshRotationLabel();
  }));
})();

// === minimap-toggle (Mobile: Karte einklappen → 36×36 Icon, ausklappen → volle Map) ===
(function () {
  const map = document.getElementById('minimap');
  const btn = document.getElementById('minimap-toggle');
  if (!map || !btn) return;
  function positionToggle() {
    // Toggle-Button oben rechts auf der Map platzieren — folgt der Map-Größe
    const r = map.getBoundingClientRect();
    btn.style.top  = (r.top - 2) + 'px';
    btn.style.left = (r.right - 22) + 'px';
  }
  function toggle(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    map.classList.toggle('collapsed');
    btn.textContent = map.classList.contains('collapsed') ? '🗺' : '×';
    setTimeout(positionToggle, 50);
  }
  btn.addEventListener('click', toggle);
  btn.addEventListener('touchend', toggle, { passive: false });
  window.addEventListener('resize', positionToggle);
  window.addEventListener('orientationchange', () => setTimeout(positionToggle, 250));
  // Initial: nach Layout-Settle positionieren + erste Map-Größenwahl
  setTimeout(positionToggle, 100);
  setTimeout(positionToggle, 500);
})();

// === chronik-toggle (was inline IIFE) ===
  // Chronik-Toggle: robust für Mouse + Touch (kein onclick-Attribut wegen Touch-Quirks
  // auf manchen Mobile-Browsern, und +/− Indikator soll mitwechseln).
  (function () {
    const root = document.getElementById('chronik');
    const head = document.getElementById('chronik-header');
    const tog  = document.getElementById('chronik-toggle');
    const apply = () => { tog.textContent = root.classList.contains('collapsed') ? '+' : '−'; };
    const toggle = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      root.classList.toggle('collapsed');
      apply();
    };
    head.addEventListener('click', toggle);
    head.addEventListener('touchend', toggle, { passive: false });
    // Auf schmalen Screens default-eingeklappt damit's nicht den halben Bildschirm frisst
    if (window.matchMedia('(max-width: 720px)').matches) {
      root.classList.add('collapsed');
    }
    apply();
  })();

// === main app (was main <script>) ===
// ─── Tile-Konfiguration ───────────────────────────────────────────────────────
const TILE = {
  WATER:    { id: 0, name: 'Wasser',   sprite: 'tile_water',    miniColor: '#1a4a7a' },
  SAND:     { id: 1, name: 'Strand',   sprite: 'tile_sand',     miniColor: '#c8a85a' },
  GRASS:    { id: 2, name: 'Grasland', sprite: 'tile_grass',    miniColor: '#3d7a3a' },
  FOREST:   { id: 3, name: 'Wald',     sprite: 'tile_forest',   miniColor: '#1a4a1a' },
  MOUNTAIN: { id: 4, name: 'Gebirge',  sprite: 'tile_mountain', miniColor: '#7a6a5a' },
  DESERT:   { id: 5, name: 'Wüste',    sprite: 'tile_desert',   miniColor: '#d4a865' },
  JUNGLE:   { id: 6, name: 'Dschungel',sprite: 'tile_jungle',   miniColor: '#1f5f1f' },
  LAVA:     { id: 7, name: 'Lava',     sprite: 'tile_lava',     miniColor: '#c83820' },
  SNOW:     { id: 8, name: 'Schnee',   sprite: 'tile_snow',     miniColor: '#e8f0f8' },
  SWAMP:    { id: 9, name: 'Sumpf',    sprite: 'tile_swamp',    miniColor: '#4a5a3a' },
};
const TILE_BY_ID = {};
for (const t of Object.values(TILE)) TILE_BY_ID[t.id] = t;
const TILE_SIZE  = 64;
const CHUNK_SIZE = 32;
// IDs die nicht walkbar sind (Frontend-Prediction, sollte mit Backend WALKABLE übereinstimmen)
const NON_WALKABLE_TILES = new Set([0, 4, 7]);  // Wasser, Berg, Lava

// ─── Natürliche Welt-Deko (nicht im Bau-Menü, aber harvest-bar) ─────────────
// RimWorld-Style: Bauten gruppiert nach Funktion. Tabs in der Reihenfolge unten.
// Welle 51 — Settlement-Schilder: 36 Gebäude-Schilder. Slug muss zu
// assets/props/settlement/signs/professional/manifest.json passen, Backend
// structures.py SIGN_SLUGS muss identisch sein.
const SIGN_VARIANTS = [
  ['schmiede',         'Schmiede',          '⚒️'],
  ['gasthaus',         'Gasthaus',          '🍺'],
  ['wohnhaus',         'Wohnhaus',          '🏠'],
  ['baeckerei',        'Bäckerei',          '🍞'],
  ['marktstand',       'Marktstand',        '⚖️'],
  ['lagerhaus',        'Lagerhaus',         '📦'],
  ['apotheke_heiler',  'Apotheke / Heiler', '⚕️'],
  ['stall',            'Stall',             '🐴'],
  ['wache',            'Wache',             '🛡️'],
  ['kaserne',          'Kaserne',           '⚔️'],
  ['rathaus',          'Rathaus',           '👑'],
  ['bergwerk',         'Bergwerk',          '⛏️'],
  ['saegewerk',        'Sägewerk',          '🪚'],
  ['holzfaeller',      'Holzfäller',        '🪓'],
  ['bauernhof',        'Bauernhof',         '🌾'],
  ['muehle',           'Mühle',             '🌬️'],
  ['fischerhuette',    'Fischerhütte',      '🐟'],
  ['taverne_brauerei', 'Taverne / Brauerei','🍻'],
  ['schneiderei',      'Schneiderei',       '🧵'],
  ['gerberei',         'Gerberei',          '🦌'],
  ['jaegerhuette',     'Jägerhütte',        '🏹'],
  ['alchemie',         'Alchemie',          '⚗️'],
  ['magierturm',       'Magierturm',        '🪄'],
  ['kapelle',          'Kapelle',           '⛪'],
  ['friedhof',         'Friedhof',          '🪦'],
  ['bibliothek',       'Bibliothek',        '📚'],
  ['schule',           'Schule',            '📝'],
  ['goldschmied',      'Goldschmied',       '💍'],
  ['waffenladen',      'Waffenladen',       '🗡️'],
  ['ruestungsschmied', 'Rüstungsschmied',   '🪖'],
  ['hafen',            'Hafen',             '⚓'],
  ['brunnen',          'Brunnen-Schild',    '⛲'],
  ['ritualplatz',      'Ritualplatz',       '🌀'],
  ['portalraum',       'Portalraum',        '🌌'],
  ['verzauberer',      'Verzauberer',       '✨'],
  ['drachenstall',     'Drachenstall',      '🐉'],
];

const BUILD_CATEGORIES = [
  { id: 'structures', icon: '🧱', label: 'Struktur',
    types: ['wall', 'floor', 'fence'] },
  { id: 'doors',      icon: '🚪', label: 'Türen',
    types: ['door_wood', 'door_iron', 'door_stone', 'door_reinforced',
            'garden_gate_ew_closed', 'garden_gate_ns_closed'] },
  { id: 'furniture',  icon: '🛏', label: 'Möbel',
    types: ['bed', 'campfire', 'well'] },
  { id: 'storage',    icon: '📦', label: 'Lager',
    types: ['chest', 'barrel', 'crate', 'sack'] },
  { id: 'production', icon: '⚒️', label: 'Produktion',
    types: ['workbench', 'anvil', 'furnace', 'farm_plot'] },
  // Asset-Drop 2026-05-27b: Farm-Gebäude + Farm-Props
  { id: 'farm',       icon: '🌾', label: 'Farm',
    subcategories: [
      { id: 'farm_buildings', icon: '🏚', label: 'Gebäude',
        types: ['barn_large','barn_small','stable','cow_shed','pigsty','henhouse',
                'goat_pen','sheepfold','dovecote','dairy_house','granary','hayloft',
                'smokehouse','cart_shed','duck_pond','goose_pasture_marker'] },
      { id: 'farm_props',     icon: '🧺', label: 'Props',
        types: ['feed_trough','water_trough','hay_bale','hay_stack','straw_bale',
                'cheese_press','butter_churn','milking_stool','nesting_box_egg',
                'cheese_rack','wooden_fence_segment','fence_gate_farm'] },
    ],
  },
  { id: 'stairs',     icon: '🪜', label: 'Treppen',
    types: ['stairs_down', 'stairs_wood_up', 'stairs_wood_down',
            'stairs_stone_up', 'stairs_stone_down'] },
  { id: 'traps',      icon: '⚠️', label: 'Fallen',
    types: ['spike_trap', 'poison_trap'] },
  { id: 'decor',      icon: '🚩', label: 'Deko',
    types: ['marker'] },
  // Welle 51: Settlement-Schilder. RimWorld-Stil mit Unterkategorien.
  { id: 'signs',      icon: '🪧', label: 'Schilder',
    subcategories: [
      { id: 'sign_admin',       icon: '🏛', label: 'Verwaltung',
        types: ['sign_rathaus','sign_wache','sign_kaserne','sign_schule'] },
      { id: 'sign_trade',       icon: '🏪', label: 'Handel',
        types: ['sign_marktstand','sign_lagerhaus','sign_gasthaus','sign_taverne_brauerei'] },
      { id: 'sign_craft',       icon: '⚒', label: 'Handwerk',
        types: ['sign_schmiede','sign_goldschmied','sign_waffenladen','sign_ruestungsschmied',
                'sign_schneiderei','sign_gerberei','sign_baeckerei','sign_apotheke_heiler'] },
      { id: 'sign_resource',    icon: '🏭', label: 'Rohstoffe',
        types: ['sign_bergwerk','sign_holzfaeller','sign_saegewerk','sign_bauernhof',
                'sign_muehle','sign_fischerhuette','sign_jaegerhuette','sign_stall'] },
      { id: 'sign_magic',       icon: '🔮', label: 'Magie',
        types: ['sign_magierturm','sign_alchemie','sign_verzauberer','sign_ritualplatz','sign_portalraum'] },
      { id: 'sign_religion',    icon: '⛪', label: 'Religion',
        types: ['sign_kapelle','sign_friedhof'] },
      { id: 'sign_residential', icon: '🏠', label: 'Wohnen',
        types: ['sign_wohnhaus','sign_brunnen'] },
      { id: 'sign_education',   icon: '📚', label: 'Bildung',
        types: ['sign_bibliothek'] },
      { id: 'sign_other',       icon: '🐉', label: 'Sonstiges',
        types: ['sign_drachenstall','sign_hafen'] },
    ],
  },
];

// Helper: alle types einer Kategorie (auch wenn sie Unterkategorien hat)
function _allTypesInCat(cat) {
  if (cat.types) return cat.types;
  if (cat.subcategories) return cat.subcategories.flatMap(s => s.types || []);
  return [];
}

const NATURAL_STRUCTURE_TYPES = new Set([
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

// ─── Strukturen-Konfiguration ─────────────────────────────────────────────────
const STRUCTURE = {
  wall:        { key: '1', name: 'Mauer',       icon: '🧱', blocking: true,  sprite: 'struct_wall',       hasMaterial: true },
  floor:       { key: '2', name: 'Boden',       icon: '▦',  blocking: false, sprite: 'struct_floor',      hasMaterial: true },
  campfire:    { key: '3', name: 'Lagerfeuer',  icon: '🔥', blocking: false, sprite: 'struct_campfire' },
  marker:      { key: '4', name: 'Marker',      icon: '🚩', blocking: false, sprite: 'struct_marker'   },
  chest:       { key: '5', name: 'Truhe',       icon: '📦', blocking: true,  sprite: 'struct_chest'    },
  workbench:   { key: '6', name: 'Werkbank',    icon: '🪓', blocking: true,  sprite: 'struct_workbench'},
  furnace:     { key: '7', name: 'Schmelze',    icon: '🌋', blocking: true,  sprite: 'struct_furnace'  },
  anvil:       { key: '8', name: 'Amboss',      icon: '⚒️', blocking: true,  sprite: 'struct_anvil'    },
  bed:         { key: '9', name: 'Bett',        icon: '🛏️', blocking: false, sprite: 'struct_bed'      },
  well:        { key: '0', name: 'Brunnen',     icon: '⛲', blocking: true,  sprite: 'struct_well'     },
  farm_plot:   { key: '',  name: 'Acker',       icon: '🌱', blocking: false, sprite: 'struct_farm_plot'},
  spike_trap:  { key: '',  name: 'Stachelfalle',icon: '🗡️', blocking: false, sprite: 'struct_spike_trap'},
  poison_trap: { key: '',  name: 'Giftfalle',   icon: '💀', blocking: false, sprite: 'struct_poison_trap'},
  stairs_down: { key: '',  name: 'Treppe nach unten',icon: '🏚️', blocking: false, sprite: 'struct_stairs_down'},
  // Deko: Natur
  tree_oak:    { key: '', name: 'Eiche',         icon: '🌳', blocking: true,  sprite: 'prop_tree_oak' },
  tree_pine:   { key: '', name: 'Nadelbaum',     icon: '🌲', blocking: true,  sprite: 'prop_tree_pine' },
  tree_dead:   { key: '', name: 'Toter Baum',    icon: '🪾', blocking: true,  sprite: 'prop_tree_dead' },
  tree_stump:  { key: '', name: 'Baumstumpf',    icon: '🪵', blocking: true,  sprite: 'prop_tree_stump' },
  fallen_log:  { key: '', name: 'Gefällter Stamm',icon: '🪵', blocking: true,  sprite: 'prop_fallen_log' },
  bush:        { key: '', name: 'Busch',         icon: '🌿', blocking: false, sprite: 'prop_bush' },
  tall_grass:  { key: '', name: 'Hohes Gras',    icon: '🌾', blocking: false, sprite: 'prop_tall_grass' },
  flowers:     { key: '', name: 'Blumen',        icon: '🌸', blocking: false, sprite: 'prop_flowers' },
  mushrooms:   { key: '', name: 'Pilze',         icon: '🍄', blocking: false, sprite: 'prop_mushrooms' },
  rock_small:  { key: '', name: 'Kleiner Felsen',icon: '🪨', blocking: true,  sprite: 'prop_rock_small' },
  rock_large:  { key: '', name: 'Großer Felsen', icon: '🪨', blocking: true,  sprite: 'prop_rock_large' },
  rock_mossy:  { key: '', name: 'Moosfelsen',    icon: '🪨', blocking: true,  sprite: 'prop_rock_mossy' },
  // Deko: Wasser
  lily_pads:     { key: '', name: 'Seerosen',    icon: '🪷', blocking: false, sprite: 'prop_lily_pads' },
  reeds:         { key: '', name: 'Schilf',      icon: '🌾', blocking: false, sprite: 'prop_reeds' },
  dock_straight: { key: '', name: 'Steg',        icon: '🪵', blocking: false, sprite: 'prop_dock_straight' },
  wooden_bridge: { key: '', name: 'Holzbrücke',  icon: '🌉', blocking: false, sprite: 'prop_wooden_bridge' },
  shipwreck:     { key: '', name: 'Schiffswrack',icon: '🚢', blocking: true,  sprite: 'prop_shipwreck' },
  // Deko: Siedlung
  broken_cart: { key: '', name: 'Karren',        icon: '🛒', blocking: true,  sprite: 'prop_broken_cart' },
  barrel:      { key: '', name: 'Fass',          icon: '🛢️', blocking: true,  sprite: 'prop_barrel' },
  crate:       { key: '', name: 'Kiste',         icon: '📦', blocking: true,  sprite: 'prop_crate' },
  sack:        { key: '', name: 'Sack',          icon: '🧺', blocking: false, sprite: 'prop_sack' },
  fence:       { key: '', name: 'Zaun',          icon: '🚧', blocking: true,  sprite: 'fence_straight_ns' },
  garden_gate_ew_closed: { key: '', name: 'Gartentor ↔', icon: '🚪', blocking: true,  sprite: 'garden_gate_ew_closed' },
  garden_gate_ew_open:   { key: '', name: 'Gartentor ↔', icon: '🚪', blocking: false, sprite: 'garden_gate_ew_open',  notBuildable: true },
  garden_gate_ns_closed: { key: '', name: 'Gartentor ↕', icon: '🚪', blocking: true,  sprite: 'garden_gate_ns_closed' },
  garden_gate_ns_open:   { key: '', name: 'Gartentor ↕', icon: '🚪', blocking: false, sprite: 'garden_gate_ns_open',  notBuildable: true },
  // Türen — closed-Varianten sind baubar, _open-Varianten sind nur Render-States
  door_wood:        { key: '', name: 'Holztür',         icon: '🚪', blocking: true,  sprite: 'door_wood' },
  door_wood_open:   { key: '', name: 'Holztür offen',   icon: '🚪', blocking: false, sprite: 'door_wood_open',  notBuildable: true },
  door_iron:        { key: '', name: 'Eisentür',        icon: '🚪', blocking: true,  sprite: 'door_iron' },
  door_iron_open:   { key: '', name: 'Eisentür offen',  icon: '🚪', blocking: false, sprite: 'door_iron_open',  notBuildable: true },
  door_stone:       { key: '', name: 'Steintür',        icon: '🚪', blocking: true,  sprite: 'door_stone' },
  door_stone_open:  { key: '', name: 'Steintür offen',  icon: '🚪', blocking: false, sprite: 'door_stone_open', notBuildable: true },
  door_reinforced:  { key: '', name: 'Verstärkte Tür',  icon: '🚪', blocking: true,  sprite: 'door_reinforced' },
  // Treppen
  stairs_wood_up:    { key: '', name: 'Holztreppe hoch',  icon: '🪜', blocking: false, sprite: 'stairs_wood_up' },
  stairs_wood_down:  { key: '', name: 'Holztreppe runter',icon: '🪜', blocking: false, sprite: 'stairs_wood_down' },
  stairs_stone_up:   { key: '', name: 'Steintreppe hoch', icon: '🪜', blocking: false, sprite: 'stairs_stone_up' },
  stairs_stone_down: { key: '', name: 'Steintreppe runter',icon: '🪜', blocking: false, sprite: 'stairs_stone_down' },
  // Deko: Ruinen
  ruin_pillar:   { key: '', name: 'Säule',       icon: '🏛️', blocking: true,  sprite: 'prop_ruin_pillar' },
  rubble:        { key: '', name: 'Trümmer',     icon: '⛏️', blocking: false, sprite: 'prop_rubble' },
  statue_broken: { key: '', name: 'Statue',      icon: '🗿', blocking: true,  sprite: 'prop_statue_broken' },
  // Welle 24 — World-Detail Asset-Drop (sign/transport/farm)
  crossroads_signpost: { key: '', name: 'Crossroads Signpost', icon: '🪧', blocking: true, sprite: 'struct_crossroads_signpost', notBuildable: true },
  signpost_village: { key: '', name: 'Signpost Village', icon: '🪧', blocking: true, sprite: 'struct_signpost_village', notBuildable: true },
  signpost_market: { key: '', name: 'Signpost Market', icon: '🪧', blocking: true, sprite: 'struct_signpost_market', notBuildable: true },
  signpost_inn: { key: '', name: 'Signpost Inn', icon: '🪧', blocking: true, sprite: 'struct_signpost_inn', notBuildable: true },
  signpost_church: { key: '', name: 'Signpost Church', icon: '🪧', blocking: true, sprite: 'struct_signpost_church', notBuildable: true },
  signpost_mill: { key: '', name: 'Signpost Mill', icon: '🪧', blocking: true, sprite: 'struct_signpost_mill', notBuildable: true },
  signpost_mine: { key: '', name: 'Signpost Mine', icon: '🪧', blocking: true, sprite: 'struct_signpost_mine', notBuildable: true },
  warning_bandits: { key: '', name: 'Warning Bandits', icon: '🪧', blocking: true, sprite: 'struct_warning_bandits', notBuildable: true },
  signpost_town: { key: '', name: 'Signpost Town', icon: '🪧', blocking: true, sprite: 'struct_signpost_town', notBuildable: true },
  signpost_farm: { key: '', name: 'Signpost Farm', icon: '🪧', blocking: true, sprite: 'struct_signpost_farm', notBuildable: true },
  signpost_forest: { key: '', name: 'Signpost Forest', icon: '🪧', blocking: true, sprite: 'struct_signpost_forest', notBuildable: true },
  signpost_docks: { key: '', name: 'Signpost Docks', icon: '🪧', blocking: true, sprite: 'struct_signpost_docks', notBuildable: true },
  signpost_graveyard: { key: '', name: 'Signpost Graveyard', icon: '🪧', blocking: true, sprite: 'struct_signpost_graveyard', notBuildable: true },
  road_marker_stone: { key: '', name: 'Road Marker Stone', icon: '🪧', blocking: true, sprite: 'struct_road_marker_stone', notBuildable: true },
  boundary_post: { key: '', name: 'Boundary Post', icon: '🪧', blocking: true, sprite: 'struct_boundary_post', notBuildable: true },
  blank_weathered_signpost: { key: '', name: 'Blank Weathered Signpost', icon: '🪧', blocking: true, sprite: 'struct_blank_weathered_signpost', notBuildable: true },
  bakery_sign: { key: '', name: 'Bakery Sign', icon: '🏪', blocking: true, sprite: 'struct_bakery_sign', notBuildable: true },
  blacksmith_sign: { key: '', name: 'Blacksmith Sign', icon: '🏪', blocking: true, sprite: 'struct_blacksmith_sign', notBuildable: true },
  tailor_sign: { key: '', name: 'Tailor Sign', icon: '🏪', blocking: true, sprite: 'struct_tailor_sign', notBuildable: true },
  inn_sign: { key: '', name: 'Inn Sign', icon: '🏪', blocking: true, sprite: 'struct_inn_sign', notBuildable: true },
  stable_sign: { key: '', name: 'Stable Sign', icon: '🏪', blocking: true, sprite: 'struct_stable_sign', notBuildable: true },
  market_sign: { key: '', name: 'Market Sign', icon: '🏪', blocking: true, sprite: 'struct_market_sign', notBuildable: true },
  apothecary_sign: { key: '', name: 'Apothecary Sign', icon: '🏪', blocking: true, sprite: 'struct_apothecary_sign', notBuildable: true },
  carpenter_sign: { key: '', name: 'Carpenter Sign', icon: '🏪', blocking: true, sprite: 'struct_carpenter_sign', notBuildable: true },
  miller_sign: { key: '', name: 'Miller Sign', icon: '🏪', blocking: true, sprite: 'struct_miller_sign', notBuildable: true },
  dairy_sign: { key: '', name: 'Dairy Sign', icon: '🏪', blocking: true, sprite: 'struct_dairy_sign', notBuildable: true },
  butcher_sign: { key: '', name: 'Butcher Sign', icon: '🏪', blocking: true, sprite: 'struct_butcher_sign', notBuildable: true },
  fishmonger_sign: { key: '', name: 'Fishmonger Sign', icon: '🏪', blocking: true, sprite: 'struct_fishmonger_sign', notBuildable: true },
  tanner_sign: { key: '', name: 'Tanner Sign', icon: '🏪', blocking: true, sprite: 'struct_tanner_sign', notBuildable: true },
  weaver_sign: { key: '', name: 'Weaver Sign', icon: '🏪', blocking: true, sprite: 'struct_weaver_sign', notBuildable: true },
  tavern_red_lion_sign: { key: '', name: 'Tavern Red Lion Sign', icon: '🏪', blocking: true, sprite: 'struct_tavern_red_lion_sign', notBuildable: true },
  scribe_sign: { key: '', name: 'Scribe Sign', icon: '🏪', blocking: true, sprite: 'struct_scribe_sign', notBuildable: true },
  handcart_empty: { key: '', name: 'Handcart Empty', icon: '🛒', blocking: true, sprite: 'struct_handcart_empty', notBuildable: true },
  handcart_crates: { key: '', name: 'Handcart Crates', icon: '🛒', blocking: true, sprite: 'struct_handcart_crates', notBuildable: true },
  farm_cart_empty: { key: '', name: 'Farm Cart Empty', icon: '🛒', blocking: true, sprite: 'struct_farm_cart_empty', notBuildable: true },
  farm_cart_hay: { key: '', name: 'Farm Cart Hay', icon: '🛒', blocking: true, sprite: 'struct_farm_cart_hay', notBuildable: true },
  farm_cart_barrels: { key: '', name: 'Farm Cart Barrels', icon: '🛒', blocking: true, sprite: 'struct_farm_cart_barrels', notBuildable: true },
  market_wagon_covered: { key: '', name: 'Market Wagon Covered', icon: '🛒', blocking: true, sprite: 'struct_market_wagon_covered', notBuildable: true },
  merchant_wagon_closed: { key: '', name: 'Merchant Wagon Closed', icon: '🛒', blocking: true, sprite: 'struct_merchant_wagon_closed', notBuildable: true },
  horse_cart_single: { key: '', name: 'Horse Cart Single', icon: '🐎', blocking: true, sprite: 'struct_horse_cart_single', notBuildable: true },
  horse_cart_pair: { key: '', name: 'Horse Cart Pair', icon: '🐎', blocking: true, sprite: 'struct_horse_cart_pair', notBuildable: true },
  ox_cart: { key: '', name: 'Ox Cart', icon: '🐎', blocking: true, sprite: 'struct_ox_cart', notBuildable: true },
  donkey_pack_cart: { key: '', name: 'Donkey Pack Cart', icon: '🐎', blocking: true, sprite: 'struct_donkey_pack_cart', notBuildable: true },
  broken_wagon_large: { key: '', name: 'Broken Wagon Large', icon: '🛒', blocking: true, sprite: 'struct_broken_wagon_large', notBuildable: true },
  wagon_wheel_loose: { key: '', name: 'Wagon Wheel Loose', icon: '🛒', blocking: true, sprite: 'struct_wagon_wheel_loose', notBuildable: true },
  wagon_harness: { key: '', name: 'Wagon Harness', icon: '🛒', blocking: true, sprite: 'struct_wagon_harness', notBuildable: true },
  hitching_post: { key: '', name: 'Hitching Post', icon: '🛒', blocking: true, sprite: 'struct_hitching_post', notBuildable: true },
  wheelbarrow_tools: { key: '', name: 'Wheelbarrow Tools', icon: '🛒', blocking: true, sprite: 'struct_wheelbarrow_tools', notBuildable: true },
  barn_small: { key: '', name: 'Barn Small', icon: '🏚️', blocking: true, sprite: 'struct_barn_small', notBuildable: true },
  barn_large: { key: '', name: 'Barn Large', icon: '🏚️', blocking: true, sprite: 'struct_barn_large', notBuildable: true },
  stable: { key: '', name: 'Stable', icon: '🏚️', blocking: true, sprite: 'struct_stable', notBuildable: true },
  cow_shed: { key: '', name: 'Cow Shed', icon: '🏚️', blocking: true, sprite: 'struct_cow_shed', notBuildable: true },
  sheepfold: { key: '', name: 'Sheepfold', icon: '🏚️', blocking: true, sprite: 'struct_sheepfold', notBuildable: true },
  goat_pen: { key: '', name: 'Goat Pen', icon: '🏚️', blocking: true, sprite: 'struct_goat_pen', notBuildable: true },
  pigsty: { key: '', name: 'Pigsty', icon: '🏚️', blocking: true, sprite: 'struct_pigsty', notBuildable: true },
  henhouse: { key: '', name: 'Henhouse', icon: '🏚️', blocking: true, sprite: 'struct_henhouse', notBuildable: true },
  duck_pond: { key: '', name: 'Duck Pond', icon: '🏚️', blocking: true, sprite: 'struct_duck_pond', notBuildable: true },
  goose_pasture_marker: { key: '', name: 'Goose Pasture Marker', icon: '🏚️', blocking: true, sprite: 'struct_goose_pasture_marker', notBuildable: true },
  dovecote: { key: '', name: 'Dovecote', icon: '🏚️', blocking: true, sprite: 'struct_dovecote', notBuildable: true },
  cart_shed: { key: '', name: 'Cart Shed', icon: '🏚️', blocking: true, sprite: 'struct_cart_shed', notBuildable: true },
  dairy_house: { key: '', name: 'Dairy House', icon: '🏚️', blocking: true, sprite: 'struct_dairy_house', notBuildable: true },
  smokehouse: { key: '', name: 'Smokehouse', icon: '🏚️', blocking: true, sprite: 'struct_smokehouse', notBuildable: true },
  hayloft: { key: '', name: 'Hayloft', icon: '🏚️', blocking: true, sprite: 'struct_hayloft', notBuildable: true },
  granary: { key: '', name: 'Granary', icon: '🏚️', blocking: true, sprite: 'struct_granary', notBuildable: true },
  water_trough: { key: '', name: 'Water Trough', icon: '🪵', blocking: true, sprite: 'struct_water_trough', notBuildable: true },
  feed_trough: { key: '', name: 'Feed Trough', icon: '🪵', blocking: true, sprite: 'struct_feed_trough', notBuildable: true },
  hay_bale: { key: '', name: 'Hay Bale', icon: '🪵', blocking: true, sprite: 'struct_hay_bale', notBuildable: true },
  hay_stack: { key: '', name: 'Hay Stack', icon: '🪵', blocking: true, sprite: 'struct_hay_stack', notBuildable: true },
  straw_bale: { key: '', name: 'Straw Bale', icon: '🪵', blocking: true, sprite: 'struct_straw_bale', notBuildable: true },
  feed_sack: { key: '', name: 'Feed Sack', icon: '🪵', blocking: true, sprite: 'struct_feed_sack', notBuildable: true },
  fence_gate_farm: { key: '', name: 'Fence Gate Farm', icon: '🪵', blocking: true, sprite: 'struct_fence_gate_farm', notBuildable: true },
  wooden_fence_segment: { key: '', name: 'Wooden Fence Segment', icon: '🪵', blocking: true, sprite: 'struct_wooden_fence_segment', notBuildable: true },
  milking_stool: { key: '', name: 'Milking Stool', icon: '🪵', blocking: true, sprite: 'struct_milking_stool', notBuildable: true },
  cheese_press: { key: '', name: 'Cheese Press', icon: '🪵', blocking: true, sprite: 'struct_cheese_press', notBuildable: true },
  nesting_box_egg: { key: '', name: 'Nesting Box Egg', icon: '🪵', blocking: true, sprite: 'struct_nesting_box_egg', notBuildable: true },
  animal_bedding_straw: { key: '', name: 'Animal Bedding Straw', icon: '🪵', blocking: true, sprite: 'struct_animal_bedding_straw', notBuildable: true },
  pitchfork: { key: '', name: 'Pitchfork', icon: '🪵', blocking: true, sprite: 'struct_pitchfork', notBuildable: true },
  shovel: { key: '', name: 'Shovel', icon: '🪵', blocking: true, sprite: 'struct_shovel', notBuildable: true },
  wooden_bucket: { key: '', name: 'Wooden Bucket', icon: '🪵', blocking: true, sprite: 'struct_wooden_bucket', notBuildable: true },
  rope_coil: { key: '', name: 'Rope Coil', icon: '🪵', blocking: true, sprite: 'struct_rope_coil', notBuildable: true },
  // Welle 23 — Gilden + Tempel + Quest-Board (Capital/Town-Distrikte)
  mage_guild:     { key: '', name: 'Magiergilde',    icon: '🔮', blocking: true,  sprite: 'struct_mage_guild',     notBuildable: true },
  fighters_guild: { key: '', name: 'Kriegergilde',   icon: '⚔️', blocking: true,  sprite: 'struct_fighters_guild', notBuildable: true },
  healers_guild:  { key: '', name: 'Heilergilde',    icon: '⚕️', blocking: true,  sprite: 'struct_healers_guild',  notBuildable: true },
  thieves_guild:  { key: '', name: 'Diebesgilde',    icon: '🗝️', blocking: true,  sprite: 'struct_thieves_guild',  notBuildable: true },
  temple:         { key: '', name: 'Tempel',         icon: '🛐', blocking: true,  sprite: 'struct_temple',         notBuildable: true },
  quest_board:    { key: '', name: 'Aufgabentafel',  icon: '📜', blocking: true,  sprite: 'struct_quest_board' },
  // Neue Welt-Deko (Welle 11)
  camp_tent:     { key: '', name: 'Zelt',        icon: '⛺', blocking: false, sprite: 'prop_camp_tent' },
  cooking_pot:   { key: '', name: 'Kochtopf',    icon: '🍲', blocking: false, sprite: 'prop_cooking_pot' },
  bones_scatter: { key: '', name: 'Knochen',     icon: '🦴', blocking: false, sprite: 'prop_bones_scatter' },
  gravestone:    { key: '', name: 'Grabstein',   icon: '🪦', blocking: true,  sprite: 'prop_gravestone' },
  dock_corner:   { key: '', name: 'Steg-Ecke',   icon: '🪵', blocking: false, sprite: 'prop_dock_corner' },
  boat_small:    { key: '', name: 'Boot',        icon: '🛶', blocking: true,  sprite: 'prop_boat_small' },
  anchor:        { key: '', name: 'Anker',       icon: '⚓', blocking: false, sprite: 'prop_anchor' },
  fishing_net:   { key: '', name: 'Fischernetz', icon: '🎣', blocking: false, sprite: 'prop_fishing_net' },
  driftwood:     { key: '', name: 'Treibholz',   icon: '🪵', blocking: false, sprite: 'prop_driftwood' },
  // Farming-Drop 2026-05-26 — wilde Sträucher / Pflanzen / Obstbäume
  strawberry_bush:{ key:'', name:'Erdbeerstrauch',  icon:'🍓', blocking:false, sprite:'prop_strawberry_bush' },
  blueberry_bush: { key:'', name:'Blaubeerstrauch', icon:'🫐', blocking:false, sprite:'prop_blueberry_bush' },
  blackberry_bush:{ key:'', name:'Brombeerstrauch', icon:'🌑', blocking:false, sprite:'prop_blackberry_bush' },
  raspberry_bush: { key:'', name:'Himbeerstrauch',  icon:'🌸', blocking:false, sprite:'prop_raspberry_bush' },
  apple_tree:     { key:'', name:'Apfelbaum',       icon:'🍎', blocking:true,  sprite:'prop_apple_tree' },
  pear_tree:      { key:'', name:'Birnbaum',        icon:'🍐', blocking:true,  sprite:'prop_pear_tree' },
  plum_tree:      { key:'', name:'Pflaumenbaum',    icon:'🟣', blocking:true,  sprite:'prop_plum_tree' },
  cherry_tree:    { key:'', name:'Kirschbaum',      icon:'🌸', blocking:true,  sprite:'prop_cherry_tree' },
  carrot_plant:   { key:'', name:'Karottenfeld',    icon:'🥕', blocking:false, sprite:'prop_carrot_plant' },
  potato_plant:   { key:'', name:'Kartoffelfeld',   icon:'🥔', blocking:false, sprite:'prop_potato_plant' },
  cucumber_plant: { key:'', name:'Gurkenpflanze',   icon:'🥒', blocking:false, sprite:'prop_cucumber_plant' },
  tomato_plant:   { key:'', name:'Tomatenpflanze',  icon:'🍅', blocking:false, sprite:'prop_tomato_plant' },
  onion_plant:    { key:'', name:'Zwiebelfeld',     icon:'🧅', blocking:false, sprite:'prop_onion_plant' },
  cabbage_plant:  { key:'', name:'Kohlfeld',        icon:'🥬', blocking:false, sprite:'prop_cabbage_plant' },
  pumpkin_plant:  { key:'', name:'Kürbisfeld',      icon:'🎃', blocking:false, sprite:'prop_pumpkin_plant' },
  corn_plant:     { key:'', name:'Maisfeld',        icon:'🌽', blocking:false, sprite:'prop_corn_plant' },
  wheat_seedling: { key:'', name:'Weizenkeimling',  icon:'🌱', blocking:false, sprite:'prop_wheat_seedling' },
  wheat_grown:    { key:'', name:'Weizenfeld',      icon:'🌾', blocking:false, sprite:'prop_wheat_grown' },
  // — Asset-Drop 2026-05-27b: Farm-Gebäude (groß, baubar) —
  barn_large:           { key:'', name:'Große Scheune',     icon:'🏚️', blocking:true,  sprite:'farm_barn_large' },
  barn_small:           { key:'', name:'Kleine Scheune',    icon:'🏚️', blocking:true,  sprite:'farm_barn_small' },
  cow_shed:             { key:'', name:'Kuhstall',          icon:'🐄', blocking:true,  sprite:'farm_cow_shed' },
  pigsty:               { key:'', name:'Schweinestall',     icon:'🐖', blocking:true,  sprite:'farm_pigsty' },
  henhouse:             { key:'', name:'Hühnerstall',       icon:'🐔', blocking:true,  sprite:'farm_henhouse' },
  goat_pen:             { key:'', name:'Ziegengehege',      icon:'🐐', blocking:true,  sprite:'farm_goat_pen' },
  sheepfold:            { key:'', name:'Schafstall',        icon:'🐑', blocking:true,  sprite:'farm_sheepfold' },
  stable:               { key:'', name:'Pferdestall',       icon:'🐎', blocking:true,  sprite:'farm_stable' },
  dovecote:             { key:'', name:'Taubenschlag',      icon:'🕊️', blocking:true,  sprite:'farm_dovecote' },
  dairy_house:          { key:'', name:'Milchhaus',         icon:'🥛', blocking:true,  sprite:'farm_dairy_house' },
  granary:              { key:'', name:'Kornspeicher',      icon:'🌾', blocking:true,  sprite:'farm_granary' },
  hayloft:              { key:'', name:'Heuboden',          icon:'🌾', blocking:true,  sprite:'farm_hayloft' },
  smokehouse:           { key:'', name:'Räucherhaus',       icon:'💨', blocking:true,  sprite:'farm_smokehouse' },
  cart_shed:             { key:'', name:'Wagenschuppen',     icon:'🛒', blocking:true,  sprite:'farm_cart_shed' },
  duck_pond:            { key:'', name:'Ententeich',        icon:'🦆', blocking:false, sprite:'farm_duck_pond' },
  goose_pasture_marker: { key:'', name:'Gänseweide',        icon:'🪧', blocking:false, sprite:'farm_goose_pasture_marker' },
  // Farm-Props (klein)
  feed_trough:          { key:'', name:'Futtertrog',        icon:'🥕', blocking:true,  sprite:'farm_feed_trough' },
  water_trough:         { key:'', name:'Wassertrog',        icon:'💧', blocking:true,  sprite:'farm_water_trough' },
  hay_bale:             { key:'', name:'Heuballen',         icon:'🌾', blocking:true,  sprite:'farm_hay_bale' },
  hay_stack:            { key:'', name:'Heuhaufen',         icon:'🌾', blocking:true,  sprite:'farm_hay_stack' },
  straw_bale:           { key:'', name:'Strohballen',       icon:'🌾', blocking:true,  sprite:'farm_straw_bale' },
  cheese_press:         { key:'', name:'Käsepresse',        icon:'🧀', blocking:true,  sprite:'farm_cheese_press' },
  butter_churn:         { key:'', name:'Butterfass',        icon:'🧈', blocking:true,  sprite:'farm_butter_churn' },
  milking_stool:        { key:'', name:'Melkschemel',       icon:'🪑', blocking:false, sprite:'farm_milking_stool' },
  nesting_box_egg:      { key:'', name:'Nistkasten',        icon:'🥚', blocking:false, sprite:'farm_nesting_box_egg' },
  cheese_rack:          { key:'', name:'Käseregal',         icon:'🧀', blocking:true,  sprite:'farm_cheese_rack' },
  wooden_fence_segment: { key:'', name:'Holzzaun-Segment',  icon:'🚧', blocking:true,  sprite:'farm_wooden_fence_segment' },
  fence_gate_farm:      { key:'', name:'Farm-Zauntor',      icon:'🚪', blocking:true,  sprite:'farm_fence_gate' },
};
// Welle 51 — Sign-Strukturen generiert aus SIGN_VARIANTS, damit die UI sie
// als reguläre baubare Strukturen behandelt (selectStructure → place_structure).
for (const [slug, label, icon] of SIGN_VARIANTS) {
  STRUCTURE[`sign_${slug}`] = {
    key: '', name: `🪧 ${label}`, icon,
    blocking: false, sprite: `sign_${slug}`,
  };
}

const STRUCTURE_BY_KEY = Object.fromEntries(
  Object.entries(STRUCTURE).map(([id, s]) => [s.key, id])
);

// Welle 25 — Strukturen die einen Interakt-Effekt haben (Bed/Well/Chest/etc.).
// Click darauf → use_structure (kein attack).
const USABLE_STRUCTURE_TYPES = new Set([
  'bed', 'well', 'chest', 'workbench', 'furnace', 'anvil', 'farm_plot',
  'campfire', 'cooking_pot', 'quest_board',
  // Farm-Stationen
  'cheese_press', 'butter_churn', 'milking_stool', 'nesting_box_egg',
  'feed_trough', 'water_trough',
]);

// Strukturen die HP haben und angegriffen werden können (sync mit
// backend/structures.STRUCTURE_MAX_HP). Trees/Pflanzen/Felsen sind harvest-only
// und nicht hier drin.
const COMBAT_STRUCTURE_TYPES = new Set([
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

// Display-Größe pro Struktur-Typ relativ zu TILE_SIZE.
// Default 1.0; größere "Bauten" wirken sonst klein gegen Charaktere (32px).
const STRUCTURE_DISPLAY_SCALE = {
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
};

// ─── Event-Konfiguration ──────────────────────────────────────────────────────
const EVENT_ICON = {
  // Welle 20: Tiered Event-System — Icon pro Tier
  atmosphere:  '🌫',
  encounter:   '🌿',
  catastrophe: '🔥',
  boss:        '💀',
  cataclysm:   '🌑',
  // Legacy kinds (für alte Chronik-Einträge in der DB)
  weather:   '☁️',
  creature:  '🐉',
  discovery: '✨',
  faction:   '⚔️',
  natural:   '🌍',
  rumor:     '💬',
};

// Tier → CSS-Klasse für visuelle Hervorhebung in der Chronik
const TIER_CLASS = {
  atmosphere:  'ev-tier-atmosphere',
  encounter:   'ev-tier-encounter',
  catastrophe: 'ev-tier-catastrophe',
  boss:        'ev-tier-boss',
  cataclysm:   'ev-tier-cataclysm',
};

function relativeTime(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'gerade eben';
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} h`;
  return `vor ${Math.floor(diff / 86400)} Tagen`;
}

// ─── NPC-Konfiguration ────────────────────────────────────────────────────────
// Item-Beschreibungen (für Tooltips)
const ITEM_DESC = {
  // Waffen
  sword:         'Eine ausgewogene Klinge. Zuverlässig im Nahkampf.',
  axe:           'Bauernkriegsaxt. Hart auf Holz, härter auf Gegner.',
  bow:           'Langbogen mit Hanfsehne. Trifft auf 5 Felder.',
  staff:         'Magisches Holz, mit Runen verziert. Verstärkt Zauber.',
  wand:          'Kurzer Zauberstab — schneller als ein Stab, weniger Wucht.',
  greatsword:    'Zweihänder. Träge, aber jeder Treffer sitzt.',
  spear:         'Reichweiten-Waffe. Hält Bestien auf Distanz.',
  crossbow:      'Aufwendig gespannt, präzise — 6 Felder Reichweite.',
  throwing_knife:'Mehrere kleine Klingen zum Werfen. Hohe Krit-Chance.',
  mace:          'Stumpfe Wucht — durchschlägt Rüstung leichter.',
  scythe:        'Sense — eigentlich Bauernwerkzeug, in der Schlacht tödlich.',
  dagger:        'Kurze, scharfe Klinge. Sehr schnell, sehr kritisch.',
  // Rüstung
  helmet:        'Schützt den Kopf vor stumpfen Schlägen.',
  chestplate:    'Brustpanzer — schwer, aber rettet Leben.',
  shield:        'Holz- oder Eisenschild. Erhöht Defense.',
  boots:         'Stiefel — leichter Schutz, bisschen mehr Tempo.',
  ring:          'Schmuckstück mit verborgener Macht.',
  amulet:        'Anhänger gegen das Böse — oder zumindest verspricht es das.',
  // Werkzeug
  pickaxe:       'Spitzhacke — beschleunigt Bergbau enorm.',
  shovel:        'Schaufel — gut zum Sammeln und Buddeln.',
  hammer:        'Schmiedehammer — beschleunigt das Bauen.',
  hoe:           'Hacke — für die Landwirtschaft.',
  // Verbrauchsgegenstände
  health_potion: 'Heilkraut + Kristall. Stellt 30 HP wieder her.',
  mana_potion:   'Bläuliche Flüssigkeit. Füllt 30 Mana auf.',
  herb:          'Frisches Kraut — kann gegessen oder gebraut werden.',
  torch:         'Fackel — leuchtet in dunklen Höhlen und Dungeons.',
  food_ration:   'Trockenfleisch + Brot in einem Paket. Sehr haltbar.',
  // Nahrung
  apple:         'Knackiger Apfel. Etwas Sättigung.',
  berries:       'Süße Waldbeeren. Schnelle Energie.',
  wheat:         'Roher Weizen — verarbeitet ergibt Brot.',
  bread:         'Frisch gebackenes Brot. Sättigt sehr lange.',
  raw_meat:      'Rohes Fleisch — besser kochen, sonst Bauchweh.',
  cooked_meat:   'Gebratenes Fleisch. Heilt und sättigt zugleich.',
  fish:          'Frischer Fisch. Gegart noch besser.',
  mushroom_food: 'Pilz-Mahl — solide Sättigung, lange haltbar.',
  // Magie
  spell_book:    'Buch mit Feuerball-Zauber. Beim Lernen wird es Teil von dir.',
  scroll:        'Schriftrolle mit "Magisches Geschoss". Lernbar.',
  rune_stone:    'Stein mit Heilrune. Lernbar — gibt blessed-Status.',
  // Rohstoffe
  wood:          'Allzweck-Holz aus Bäumen. Stapelbar bis 500.',
  stone:         'Bruchstein vom Bergbau. Stapelbar bis 500.',
  iron_ore:      'Eisenerz — am Amboss zu Stahl schmiedbar.',
  gold_ore:      'Goldnugget. Funktioniert als Währung beim Händler.',
  silver_ore:    'Silbererz — wertvoll, magisch leitend.',
  mythril_ore:   'Sagenhaftes Mythril. Sehr selten.',
  steel_ingot:   'Stahlbarren — Hauptmaterial für hochwertige Waffen.',
  crystal:       'Kristall mit arkanen Eigenschaften.',
  bone:          'Knochen — Material für rituelle Arbeiten.',
  cloth:         'Stoff — für Kleidung und Sackware.',
  leather:       'Gegerbtes Leder — robust, aber leicht.',
};

// Deutsche Übersetzung für Item-Kategorien (Issue: Deutsche Konsistenz)
const CATEGORY_DE = {
  weapon: 'Waffe', armor: 'Rüstung', jewelry: 'Schmuck',
  consumable: 'Verbrauchsgegenstand', food: 'Nahrung', magic: 'Magie',
  tool: 'Werkzeug', resource: 'Rohstoff',
};
const QUALITY_DE = {
  rough: 'grob', normal: 'normal', fine: 'fein',
  masterwork: 'meisterhaft', legendary: 'legendär',
};
const QUALITY_ICONS = { fine:'✨', masterwork:'🌟', legendary:'👑', rough:'⚠️' };

// Welle 33: Waffen-Reichweite (Tiles), spiegelt backend/item_stats.WEAPON_STATS
const WEAPON_RANGE = {
  sword: 1, axe: 1, mace: 1, dagger: 1, scythe: 1, greatsword: 1,
  spear: 2,
  bow: 5, crossbow: 6, throwing_knife: 3,
  staff: 4, wand: 4,
};
// Welle 35: Volle Waffen-Stats für Tooltips
// Welle 19 — Spiegel von backend/item_stats.py WEAPON_STATS (Stat-Rebalance)
const WEAPON_STATS = {
  dagger:        { dmg: 6,  speed: 1.8,  crit: 0.22, crit_mult: 2.5, range: 1, two_h: false },
  sword:         { dmg: 11, speed: 1.0,  crit: 0.06, crit_mult: 1.5, range: 1, two_h: false },
  axe:           { dmg: 15, speed: 0.85, crit: 0.05, crit_mult: 1.7, range: 1, two_h: false, armor_pen: 0.10 },
  mace:          { dmg: 13, speed: 0.80, crit: 0.03, crit_mult: 1.6, range: 1, two_h: false, armor_pen: 0.35 },
  throwing_knife:{ dmg: 6,  speed: 1.6,  crit: 0.15, crit_mult: 2.0, range: 3, two_h: false },
  wand:          { dmg: 7,  speed: 1.3,  crit: 0.10, crit_mult: 1.5, range: 4, two_h: false },
  greatsword:    { dmg: 26, speed: 0.65, crit: 0.07, crit_mult: 1.9, range: 1, two_h: true },
  spear:         { dmg: 13, speed: 1.0,  crit: 0.08, crit_mult: 1.6, range: 2, two_h: true },
  scythe:        { dmg: 18, speed: 0.70, crit: 0.08, crit_mult: 1.9, range: 1, two_h: true, cleave: true },
  bow:           { dmg: 10, speed: 1.0,  crit: 0.10, crit_mult: 1.6, range: 5, two_h: true },
  crossbow:      { dmg: 22, speed: 0.50, crit: 0.15, crit_mult: 1.9, range: 6, two_h: true, armor_pen: 0.30 },
  staff:         { dmg: 9,  speed: 1.0,  crit: 0.08, crit_mult: 1.5, range: 4, two_h: true },
};
const ARMOR_STATS = {
  helmet:     { defense: 8,  weight: 3 },
  chestplate: { defense: 22, weight: 8 },
  gloves:     { defense: 4,  weight: 1, crit_chance_bonus: 0.01 },
  shield:     { defense: 15, weight: 5, block_chance: 0.15 },
  boots:      { defense: 6,  weight: 2, speed_bonus: 0.05 },
};

// Welle 21: Gewicht pro Item-Kategorie (Default-Fallback per Item-Kind möglich)
// Stacks: Gewicht × quantity.  Equipment hat eigene weight-Felder (ARMOR_STATS),
// die werden bevorzugt.
const ITEM_WEIGHT_BY_CATEGORY = {
  resource:   0.5,
  food:       0.3,
  consumable: 0.4,
  magic:      0.8,
  jewelry:    0.2,
  weapon:     4.0,    // Default für Waffen ohne weight-Override
  armor:      5.0,    // Default für Rüstung ohne weight-Override
  tool:       2.0,
};

const ITEM_WEIGHT_OVERRIDES = {
  copper_coin: 0.02, silver_coin: 0.02, gold_coin: 0.02,
  herb: 0.1, plant_fiber: 0.15,
  bone: 0.4, cloth: 0.2, leather: 0.4, wood: 0.6, stone: 1.0,
  iron_ore: 1.2, silver_ore: 1.2, gold_ore: 1.5, mythril_ore: 1.0, crystal: 0.8,
  steel_ingot: 1.5, iron_ingot: 1.3, copper_ingot: 1.2, silver_ingot: 1.4,
  gold_ingot: 1.8, mithril_ingot: 1.0, adamant_ingot: 2.0,
  platinum_ingot: 1.6, tungsten_ingot: 2.2, crystal_ingot: 1.0,
  // Waffen — leichter/schwerer als Default
  dagger: 1.5, throwing_knife: 0.8, wand: 1.0, sword: 4.0,
  axe: 5.5, mace: 6.0, spear: 3.5, greatsword: 9.0, scythe: 7.0,
  bow: 2.5, crossbow: 6.0, staff: 3.0,
  // Container
  wooden_bucket: 2.5, iron_bucket: 4.0, leather_waterskin: 1.5,
  wooden_watering_can: 3.0, iron_watering_can: 5.0,
};

function itemWeight(item) {
  if (!item) return 0;
  let unit = ITEM_WEIGHT_OVERRIDES[item.kind];
  if (unit == null) {
    const cfg = ITEM[item.kind];
    if (cfg) {
      if (cfg.category === 'armor' && ARMOR_STATS[item.kind]) {
        unit = ARMOR_STATS[item.kind].weight;
      } else {
        unit = ITEM_WEIGHT_BY_CATEGORY[cfg.category] ?? 0.5;
      }
    } else {
      unit = 0.5;
    }
  }
  return unit * (item.quantity || 1);
}

// Affix-Stat-Keys → deutsche Labels mit Suffix (%, flat oder dmg)
const AFFIX_STAT_LABELS = {
  damage_pct:       { de: 'Schaden',         suffix: '%' },
  speed_pct:        { de: 'Angriffsgeschw.', suffix: '%' },
  crit_chance_pct:  { de: 'Krit-Chance',     suffix: '%' },
  crit_damage_pct:  { de: 'Krit-Schaden',    suffix: '%' },
  defense_flat:     { de: 'Defense',         suffix: '' },
  hp_flat:          { de: 'HP',              suffix: '' },
  mana_flat:        { de: 'Mana',            suffix: '' },
  fire_damage:      { de: '🔥 Feuerschaden',  suffix: '' },
  ice_damage:       { de: '❄️ Eisschaden',    suffix: '' },
  lightning_damage: { de: '⚡ Blitzschaden',  suffix: '' },
  necrotic_damage:  { de: '☠️ Nekrotisch',    suffix: '' },
  lifesteal_pct:    { de: 'Lebenssaug',      suffix: '%' },
  armor_pen_pct:    { de: 'Rüstungsdurchdr.', suffix: '%' },
  regen_pct:        { de: 'Regeneration',    suffix: '%' },
  magic_resist_pct: { de: 'Magieresistenz',  suffix: '%' },
  fire_resist_pct:  { de: '🔥 Feuerresist',   suffix: '%' },
  ice_resist_pct:   { de: '❄️ Eisresist',     suffix: '%' },
  lightning_resist_pct: { de: '⚡ Blitzresist', suffix: '%' },
};

const QUALITY_MULT_FE = { rough:0.75, normal:1.0, fine:1.15, masterwork:1.3, legendary:1.5 };

// Welle 17 — Container-Kapazitäten (mirror von items.py WATER_CONTAINER_CAPACITY)
const WATER_CONTAINER_CAPACITY = {
  wooden_bucket:       1,
  iron_bucket:         2,
  leather_waterskin:   3,
  wooden_watering_can: 4,
  iron_watering_can:   6,
};
const WATER_CONTAINER_KINDS = new Set(Object.keys(WATER_CONTAINER_CAPACITY));
function isWaterContainer(kind) { return WATER_CONTAINER_KINDS.has(kind); }
function containerCapacity(kind) { return WATER_CONTAINER_CAPACITY[kind] || 0; }

function _qualityMult(q) { return QUALITY_MULT_FE[q] || 1.0; }

function buildItemStatsHtml(item, opts = {}) {
  // Liefert alle Stats + Affixe als HTML-Snippet. `opts.equipped` ist optional
  // ein bereits-ausgerüstetes Item im selben Slot — wenn gegeben, werden
  // Delta-Vergleiche (grün/rot) angezeigt.
  const lines = [];
  const w = WEAPON_STATS[item.kind];
  const a = ARMOR_STATS[item.kind];
  const eq = opts.equipped;
  const qm = _qualityMult(item.quality);
  const eqQm = eq ? _qualityMult(eq.quality) : 1.0;
  const delta = (cur, prev, isPct = false) => {
    if (!eq) return '';
    const d = cur - prev;
    if (Math.abs(d) < 0.01) return '';
    const sign = d > 0 ? '+' : '';
    const col = d > 0 ? '#7aad6a' : '#e85040';
    const v = isPct ? d.toFixed(1) : Math.round(d * 10) / 10;
    return ` <span style="color:${col};font-size:10px">(${sign}${v})</span>`;
  };
  // Welle 23: rolled_stats (per-instance Variance) hat Vorrang vor base+quality.
  // Damage als Range (8-12), nicht als einzelner Wert.
  const rs = item.rolled_stats;
  const eqRs = eq && eq.rolled_stats;
  if (w) {
    if (rs && rs.damage_min !== undefined) {
      const lo = rs.damage_min, hi = rs.damage_max;
      const mid = (lo + hi) / 2;
      const eqMid = eqRs && eqRs.damage_min !== undefined
        ? (eqRs.damage_min + eqRs.damage_max) / 2
        : (eq ? (WEAPON_STATS[eq.kind]?.dmg || 0) * eqQm : 0);
      lines.push(`⚔️ Schaden: ${lo}-${hi}${eq ? delta(mid, eqMid) : ''}`);
      lines.push(`⚡ Speed: ${rs.speed.toFixed(2)}×${eq ? delta(rs.speed, eqRs?.speed ?? (WEAPON_STATS[eq.kind]?.speed || 1)) : ''}`);
      lines.push(`💥 Crit: ${(rs.crit*100).toFixed(1)}%${eq ? delta(rs.crit*100, (eqRs?.crit ?? (WEAPON_STATS[eq.kind]?.crit || 0))*100, true) : ''}`);
      lines.push(`🎯 Reichweite: ${rs.range} Tiles`);
      if (rs.armor_pen) lines.push(`🪓 Panzerbrechend: ${(rs.armor_pen*100).toFixed(0)}%`);
      if (rs.two_handed) lines.push(`🤲 Zweihändig`);
      if (rs.cleave) lines.push(`🌀 Spaltschlag`);
    } else {
      const dmg = w.dmg * qm;
      const eqW = eq ? WEAPON_STATS[eq.kind] : null;
      const eqDmg = eqW ? eqW.dmg * eqQm : 0;
      lines.push(`⚔️ Schaden: ${Math.round(dmg)}${eqW ? delta(dmg, eqDmg) : ''}`);
      lines.push(`⚡ Speed: ${w.speed.toFixed(2)}×${eqW ? delta(w.speed, eqW.speed) : ''}`);
      lines.push(`💥 Crit: ${(w.crit*100).toFixed(0)}%${eqW ? delta(w.crit*100, eqW.crit*100, true) : ''}`);
      lines.push(`🎯 Reichweite: ${w.range} Tiles${eqW ? delta(w.range, eqW.range) : ''}`);
      if (w.two_h) lines.push(`🤲 Zweihändig`);
    }
  } else if (a) {
    if (rs && rs.defense !== undefined) {
      const eqDef = eqRs?.defense ?? (eq ? (ARMOR_STATS[eq.kind]?.defense || 0) * eqQm : 0);
      lines.push(`🛡️ Defense: ${rs.defense}${eq ? delta(rs.defense, eqDef) : ''}`);
      if (rs.weight !== undefined) lines.push(`⚖️ Gewicht: ${rs.weight}`);
      if (rs.block_chance) lines.push(`🛡️ Blockchance: ${(rs.block_chance*100).toFixed(0)}%`);
      if (rs.speed_bonus) lines.push(`👟 Bewegungsbonus: +${(rs.speed_bonus*100).toFixed(0)}%`);
      if (rs.crit_chance_bonus) lines.push(`💥 Crit-Bonus: +${(rs.crit_chance_bonus*100).toFixed(1)}%`);
    } else {
      const def = a.defense * qm;
      const eqA = eq ? ARMOR_STATS[eq.kind] : null;
      const eqDef = eqA ? eqA.defense * eqQm : 0;
      lines.push(`🛡️ Defense: ${Math.round(def)}${eqA ? delta(def, eqDef) : ''}`);
      lines.push(`⚖️ Gewicht: ${a.weight}${eqA ? delta(a.weight, eqA.weight) : ''}`);
      if (a.block_chance) lines.push(`🛡️ Blockchance: ${(a.block_chance*100).toFixed(0)}%`);
      if (a.speed_bonus) lines.push(`👟 Bewegungsbonus: +${(a.speed_bonus*100).toFixed(0)}%`);
    }
  }
  let html = '';
  if (lines.length > 0) {
    html += `<div class="tt-stats">${lines.map(s => `<div>${s}</div>`).join('')}</div>`;
  }
  // Affixe mit konkreten Werten
  if (item.affixes && item.affixes.length > 0) {
    const affixLines = item.affixes.map(af => {
      const stats = af.stats || {};
      const statTexts = Object.entries(stats).map(([k, v]) => {
        const lab = AFFIX_STAT_LABELS[k] || { de: k, suffix: '' };
        const sign = v > 0 ? '+' : '';
        return `${sign}${v}${lab.suffix} ${lab.de}`;
      });
      const kindIcon = af.kind === 'prefix' ? '◀' : '▶';
      return `<div class="tt-affix-row">${kindIcon} <b>${af.name_part}</b> <span style="opacity:0.6">T${af.tier}</span><br>` +
             `<span style="margin-left:14px;color:#9fc890">${statTexts.join(' · ')}</span></div>`;
    });
    html += `<div class="tt-affix">${affixLines.join('')}</div>`;
  }
  return html;
}

function findEquippedInSlot(inventory, slot) {
  if (!slot) return null;
  return (inventory || []).find(it => it.equipped_slot === slot) || null;
}

const NPC_SPRITE = {
  // ─── Friendly NPCs ──────────────────────────────────────────────────────
  // Jeder Friendly-Kind nutzt sein eigenes npc_<kind>-Sprite aus
  // /assets/characters/npcs/. Recycling nur für Backend-Kinds ohne eigenes
  // Asset (wanderer, soldier) — als Übergangslösung mit Tint.
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
  // Asset-Drop 2026-05-27: neue Handwerks-/Dorf-Rollen
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
  // ─── Asset-Drop 2026-05-27b: Nutztiere (Livestock + Poultry) ───────────
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
  // ─── Asset-Drop 2026-05-27c: Karawanen-Wagen (NPC-Kinds, mit Animation) ─
  farm_cart_hay:       { sprite: 'cart_farm_cart_hay',       tint: 0xffffff, label: 'Heuwagen' },
  handcart_empty:      { sprite: 'cart_handcart_empty',      tint: 0xffffff, label: 'Handkarren' },
  horse_cart_single:   { sprite: 'cart_horse_cart_single',   tint: 0xffffff, label: 'Pferdewagen' },
  market_wagon_covered:{ sprite: 'cart_market_wagon_covered',tint: 0xffffff, label: 'Marktwagen' },
  // ─── Hostile Humans (Räuber-Typen) ─────────────────────────────────────
  // Nutzen Character-Sprites aus /assets/characters/npcs/ (nicht monster_*),
  // weil es Menschen sind. variant kann Waffen-Variante (bandit_axe etc.)
  // überschreiben für visuelle Diversität.
  bandit:    { sprite: 'npc_bandit',  tint: 0xffffff, label: 'Bandit' },
  robber:    { sprite: 'npc_robber',  tint: 0xffffff, label: 'Räuber' },
  thief:     { sprite: 'npc_thief',   tint: 0xffffff, label: 'Dieb' },
  // Creatures — eigenes Sprite, kein Tint
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
  // Bosse — größere Sprites, eigene Optik
  ogre:         { sprite: 'monster_ogre',         tint: 0xffffff, label: 'Ogre' },
  necromancer:  { sprite: 'monster_necromancer',  tint: 0xffffff, label: 'Nekromant' },
  dragon_whelp: { sprite: 'monster_dragon_whelp', tint: 0xffffff, label: 'Drachling' },
  // Welle 13 — neue Monster (asset-drop 2026-05-26)
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
const CREATURE_KINDS = new Set([
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
  // Welle 14 — professional asset-drop (muss mit backend/npc_worker.CREATURE_KINDS sync sein)
  'razorback_vermin','spined_abyss_larva','reed_walker','redland_scavenger',
  'mossback_warden','grave_wraith','serpent_oracle','urtikus_eye_fiend',
  'mantis_chimera','iron_spider','dendroid_guardian','blood_antler_drake',
  'kaiju_thornback','void_eye_brute','frost_rune_boar_prime',
  'magma_shell_devourer','rockshell_colossus',
]);

// ─── Walk-Cycle-Animations (Asset-Drop /assets/animations/) ─────────────────
// NPCs/Monsters in dieser Liste haben in /assets/animations/<characters|monsters>/<kind>/
// einen vollständigen 10-Frame-Pool (idle_1/2, walk_<down|up|left|right>_1/2).
// `_updateWalkFrame` swappt die Texture basierend auf Bewegungsrichtung.
// Nicht enthalten: farmer + merchant (alter Top-Down-Stil, nicht kompatibel mit
// neuem Front-View aus /npcs/), neue Rollen (baker, bard, ...) ohne Animation.
const ANIMATED_NPC_KINDS = [
  // Welle 23 — alle character-Animations die Front-View sind (refreshed
  // im upstream-Commit 4d2af6e). villager_male/_female bleiben raus,
  // weil noch im alten Top-Down-Stil.
  'bandit', 'blacksmith', 'farmer', 'guard', 'healer',
  'mage', 'merchant', 'quest_giver', 'soldier', 'villager',
];
const ANIMATED_MONSTER_KINDS = [
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

// ─── Items ───────────────────────────────────────────────────────────────────
// Default-Icons aus original_pack_2026_05_27 — hand-painted 128×128 Inventar-
// Sprites. Pro-Rarity-Varianten (Welle 19) bleiben via PRO_WEAPON_MAP/
// PRO_ARMOR_MAP separat ansprechbar.
const OP = '/assets/professional/original_pack_2026_05_27/icons_128';
const ITEM = {
  sword:         { name: 'Schwert',       sprite: 'item_sword',         category: 'weapon', slot: 'weapon', path: `${OP}/black_guard_longsword.png` },
  axe:           { name: 'Axt',           sprite: 'item_axe',           category: 'weapon', slot: 'weapon', path: `${OP}/old_execution_axe.png` },
  bow:           { name: 'Bogen',         sprite: 'item_bow',           category: 'weapon', slot: 'weapon', path: `${OP}/ashwood_recurve_bow.png` },
  staff:         { name: 'Stab',          sprite: 'item_staff',         category: 'weapon', slot: 'weapon', path: `${OP}/red_oak_staff.png` },
  wand:          { name: 'Zauberstab',    sprite: 'item_wand',          category: 'weapon', slot: 'weapon', path: `${OP}/red_oak_staff.png` },
  greatsword:    { name: 'Großschwert',   sprite: 'item_greatsword',    category: 'weapon', slot: 'weapon', path: `${OP}/cleaver_greatsword.png` },
  spear:         { name: 'Speer',         sprite: 'item_spear',         category: 'weapon', slot: 'weapon', path: `${OP}/plain_war_spear.png` },
  crossbow:      { name: 'Armbrust',      sprite: 'item_crossbow',      category: 'weapon', slot: 'weapon', path: `${OP}/stormbow_crossbow.png` },
  throwing_knife:{ name: 'Wurfmesser',    sprite: 'item_throwing_knife',category: 'weapon', slot: 'weapon', path: `${OP}/hooked_ritual_dagger.png` },
  mace:          { name: 'Streitkolben',  sprite: 'item_mace',          category: 'weapon', slot: 'weapon', path: `${OP}/iron_mace.png` },
  scythe:        { name: 'Sense',         sprite: 'item_scythe',        category: 'weapon', slot: 'weapon', path: `${OP}/graveyard_scythe.png` },
  dagger:        { name: 'Dolch',         sprite: 'item_dagger',        category: 'weapon', slot: 'weapon', path: `${OP}/hooked_ritual_dagger.png` },
  helmet:        { name: 'Helm',          sprite: 'item_helmet',        category: 'armor',  slot: 'helmet',     path: `${OP}/crested_hoplite_helm.png` },
  chestplate:    { name: 'Brustpanzer',   sprite: 'item_chestplate',    category: 'armor',  slot: 'chestplate', path: `${OP}/wandering_knight_armor.png` },
  gloves:        { name: 'Handschuhe',    sprite: 'item_gloves',        category: 'armor',  slot: 'gloves',     path: `${OP}/thief_buckled_gloves.png` },
  shield:        { name: 'Schild',        sprite: 'item_shield',        category: 'armor',  slot: 'shield',     path: `${OP}/ornate_guard_shield.png` },
  boots:         { name: 'Stiefel',       sprite: 'item_boots',         category: 'armor',  slot: 'boots',      path: `${OP}/dwarven_field_boots.png` },
  ring:          { name: 'Ring',        sprite: 'item_ring',          category: 'jewelry',    slot: 'ring',       path: '/assets/equipment/jewelry/ring.png' },
  amulet:        { name: 'Amulett',     sprite: 'item_amulet',        category: 'jewelry',    slot: 'amulet',     path: '/assets/equipment/jewelry/amulet.png' },
  health_potion:         { name: 'Heiltrank',          sprite: 'item_health_potion',         category: 'consumable', path: `${OP}/health_potion.png` },
  mana_potion:           { name: 'Manatrank',          sprite: 'item_mana_potion',           category: 'consumable', path: `${OP}/mana_potion.png` },
  greater_health_potion: { name: 'Großer Heiltrank',   sprite: 'item_greater_health_potion', category: 'consumable', path: '/assets/consumables/potions/greater_health_potion.png' },
  greater_mana_potion:   { name: 'Großer Manatrank',   sprite: 'item_greater_mana_potion',   category: 'consumable', path: '/assets/consumables/potions/greater_mana_potion.png' },
  antidote_potion:       { name: 'Gegengift',          sprite: 'item_antidote_potion',       category: 'consumable', path: `${OP}/antidote_potion.png` },
  fire_resist_potion:    { name: 'Feuerwiderstand',    sprite: 'item_fire_resist_potion',    category: 'consumable', path: `${OP}/fire_resist_potion.png` },
  frost_resist_potion:   { name: 'Frostwiderstand',    sprite: 'item_frost_resist_potion',   category: 'consumable', path: '/assets/consumables/potions/frost_resist_potion.png' },
  invisibility_potion:   { name: 'Unsichtbarkeit',     sprite: 'item_invisibility_potion',   category: 'consumable', path: '/assets/consumables/potions/invisibility_potion.png' },
  poison_potion:         { name: 'Gifttrank',          sprite: 'item_poison_potion',         category: 'consumable', path: '/assets/consumables/potions/poison_potion.png' },
  speed_potion:          { name: 'Geschwindigkeit',    sprite: 'item_speed_potion',          category: 'consumable', path: '/assets/consumables/potions/speed_potion.png' },
  stamina_potion:        { name: 'Ausdauer',           sprite: 'item_stamina_potion',        category: 'consumable', path: `${OP}/stamina_potion.png` },
  strength_potion:       { name: 'Stärke',             sprite: 'item_strength_potion',       category: 'consumable', path: '/assets/consumables/potions/strength_potion.png' },
  herb:          { name: 'Kraut',       sprite: 'item_herb',          category: 'consumable',                     path: `${OP}/herb_bundle.png` },
  torch:         { name: 'Fackel',      sprite: 'item_torch',         category: 'consumable',                     path: `${OP}/torch.png` },
  food_ration:   { name: 'Proviant',    sprite: 'item_food_ration',   category: 'food',                           path: '/assets/consumables/food_ration.png' },
  apple:         { name: 'Apfel',       sprite: 'item_apple',         category: 'food',                           path: '/assets/food/apple.png' },
  berries:       { name: 'Beeren',      sprite: 'item_berries',       category: 'food',                           path: '/assets/food/berries.png' },
  wheat:         { name: 'Weizen',      sprite: 'item_wheat',         category: 'food',                           path: '/assets/food/wheat.png' },
  bread:         { name: 'Brot',        sprite: 'item_bread',         category: 'food',                           path: `${OP}/bread_loaf.png` },
  raw_meat:      { name: 'Rohes Fleisch',sprite:'item_raw_meat',      category: 'food',                           path: '/assets/food/raw_meat.png' },
  cooked_meat:   { name: 'Gebratenes Fleisch',sprite:'item_cooked_meat',category:'food',                          path: `${OP}/cooked_meat.png` },
  fish:          { name: 'Fisch',       sprite: 'item_fish',          category: 'food',                           path: '/assets/food/fish.png' },
  mushroom_food: { name: 'Pilz-Mahl',   sprite: 'item_mushroom_food', category: 'food',                           path: '/assets/food/mushroom_food.png' },
  // Farming-Drop 2026-05-26
  strawberry:    { name: 'Erdbeere',    sprite: 'item_strawberry',    category: 'food',                           path: '/assets/food/strawberry.png' },
  blueberry:     { name: 'Blaubeere',   sprite: 'item_blueberry',     category: 'food',                           path: '/assets/food/blueberry.png' },
  blackberry:    { name: 'Brombeere',   sprite: 'item_blackberry',    category: 'food',                           path: '/assets/food/blackberry.png' },
  raspberry:     { name: 'Himbeere',    sprite: 'item_raspberry',     category: 'food',                           path: '/assets/food/raspberry.png' },
  pear:          { name: 'Birne',       sprite: 'item_pear',          category: 'food',                           path: '/assets/food/pear.png' },
  plum:          { name: 'Pflaume',     sprite: 'item_plum',          category: 'food',                           path: '/assets/food/plum.png' },
  cherry:        { name: 'Kirsche',     sprite: 'item_cherry',        category: 'food',                           path: '/assets/food/cherry.png' },
  carrot:        { name: 'Karotte',     sprite: 'item_carrot',        category: 'food',                           path: '/assets/food/carrot.png' },
  potato:        { name: 'Kartoffel',   sprite: 'item_potato',        category: 'food',                           path: '/assets/food/potato.png' },
  cucumber:      { name: 'Gurke',       sprite: 'item_cucumber',      category: 'food',                           path: '/assets/food/cucumber.png' },
  tomato:        { name: 'Tomate',      sprite: 'item_tomato',        category: 'food',                           path: '/assets/food/tomato.png' },
  onion:         { name: 'Zwiebel',     sprite: 'item_onion',         category: 'food',                           path: '/assets/food/onion.png' },
  cabbage:       { name: 'Kohl',        sprite: 'item_cabbage',       category: 'food',                           path: '/assets/food/cabbage.png' },
  pumpkin:       { name: 'Kürbis',      sprite: 'item_pumpkin',       category: 'food',                           path: '/assets/food/pumpkin.png' },
  corn:          { name: 'Mais',        sprite: 'item_corn',          category: 'food',                           path: '/assets/food/corn.png' },
  garlic:        { name: 'Knoblauch',   sprite: 'item_garlic',        category: 'food',                           path: '/assets/food/garlic.png' },
  grapes_blue:   { name: 'Blaue Trauben', sprite: 'item_grapes_blue', category: 'food',                           path: '/assets/food/grapes_blue.png' },
  grapes_green:  { name: 'Grüne Trauben',sprite: 'item_grapes_green', category: 'food',                           path: '/assets/food/grapes_green.png' },
  strawberry_seeds:{ name:'Erdbeer-Samen',  sprite:'item_strawberry_seeds', category:'resource', path:'/assets/seeds/strawberry_seeds.png' },
  blueberry_seeds: { name:'Blaubeer-Samen', sprite:'item_blueberry_seeds',  category:'resource', path:'/assets/seeds/blueberry_seeds.png' },
  blackberry_seeds:{ name:'Brombeer-Samen', sprite:'item_blackberry_seeds', category:'resource', path:'/assets/seeds/blackberry_seeds.png' },
  raspberry_seeds: { name:'Himbeer-Samen',  sprite:'item_raspberry_seeds',  category:'resource', path:'/assets/seeds/raspberry_seeds.png' },
  apple_seeds:     { name:'Apfelkerne',     sprite:'item_apple_seeds',      category:'resource', path:'/assets/seeds/apple_seeds.png' },
  pear_seeds:      { name:'Birnenkerne',    sprite:'item_pear_seeds',       category:'resource', path:'/assets/seeds/pear_seeds.png' },
  plum_seeds:      { name:'Pflaumenkerne',  sprite:'item_plum_seeds',       category:'resource', path:'/assets/seeds/plum_seeds.png' },
  cherry_seeds:    { name:'Kirschkerne',    sprite:'item_cherry_seeds',     category:'resource', path:'/assets/seeds/cherry_seeds.png' },
  carrot_seeds:    { name:'Karotten-Samen', sprite:'item_carrot_seeds',     category:'resource', path:'/assets/seeds/carrot_seeds.png' },
  potato_seeds:    { name:'Kartoffel-Saat', sprite:'item_potato_seeds',     category:'resource', path:'/assets/seeds/potato_seeds.png' },
  cucumber_seeds:  { name:'Gurken-Samen',   sprite:'item_cucumber_seeds',   category:'resource', path:'/assets/seeds/cucumber_seeds.png' },
  tomato_seeds:    { name:'Tomaten-Samen',  sprite:'item_tomato_seeds',     category:'resource', path:'/assets/seeds/tomato_seeds.png' },
  onion_seeds:     { name:'Zwiebel-Samen',  sprite:'item_onion_seeds',      category:'resource', path:'/assets/seeds/onion_seeds.png' },
  cabbage_seeds:   { name:'Kohl-Samen',     sprite:'item_cabbage_seeds',    category:'resource', path:'/assets/seeds/cabbage_seeds.png' },
  pumpkin_seeds:   { name:'Kürbis-Samen',   sprite:'item_pumpkin_seeds',    category:'resource', path:'/assets/seeds/pumpkin_seeds.png' },
  corn_seeds:      { name:'Mais-Samen',     sprite:'item_corn_seeds',       category:'resource', path:'/assets/seeds/corn_seeds.png' },
  spell_book:    { name: 'Feuerball-Buch', sprite: 'item_spell_book', category: 'magic',                          path: '/assets/magic/spell_book.png' },
  scroll:        { name: 'Schriftrolle',sprite: 'item_scroll',        category: 'magic',                          path: '/assets/magic/scroll.png' },
  rune_stone:    { name: 'Heilrune',    sprite: 'item_rune_stone',    category: 'magic',                          path: '/assets/magic/rune_stone.png' },
  pickaxe:       { name: 'Spitzhacke',  sprite: 'item_pickaxe',       category: 'tool',       slot: 'tool',       path: '/assets/tools/pickaxe.png' },
  shovel:        { name: 'Schaufel',    sprite: 'item_shovel',        category: 'tool',       slot: 'tool',       path: '/assets/tools/shovel.png' },
  hammer:        { name: 'Hammer',      sprite: 'item_hammer',        category: 'tool',       slot: 'tool',       path: '/assets/tools/hammer.png' },
  hoe:           { name: 'Hacke',       sprite: 'item_hoe',           category: 'tool',       slot: 'tool',       path: '/assets/tools/hoe.png' },
  sickle:        { name: 'Sichel',      sprite: 'item_sickle',        category: 'tool',       slot: 'tool',       path: '/assets/tools/sickle.png' },
  wooden_bucket:       { name: 'Holzeimer',      sprite: 'item_wooden_bucket',       category: 'tool', slot: 'tool', path: '/assets/tools/wooden_bucket.png' },
  iron_bucket:         { name: 'Eisen-Eimer',    sprite: 'item_iron_bucket',         category: 'tool', slot: 'tool', path: '/assets/tools/iron_bucket.png' },
  wooden_watering_can: { name: 'Holz-Gießkanne', sprite: 'item_wooden_watering_can', category: 'tool', slot: 'tool', path: '/assets/tools/wooden_watering_can.png' },
  iron_watering_can:   { name: 'Eisen-Gießkanne',sprite: 'item_iron_watering_can',   category: 'tool', slot: 'tool', path: '/assets/tools/iron_watering_can.png' },
  leather_waterskin:   { name: 'Wasserschlauch', sprite: 'item_leather_waterskin',   category: 'tool', slot: 'tool', path: '/assets/tools/leather_waterskin.png' },
  wood:          { name: 'Holz',        sprite: 'item_wood',          category: 'resource',                       path: `${OP}/wood_logs.png` },
  stone:         { name: 'Stein',       sprite: 'item_stone',         category: 'resource',                       path: `${OP}/rough_stone.png` },
  iron_ore:      { name: 'Eisenerz',    sprite: 'item_iron_ore',      category: 'resource',                       path: `${OP}/iron_ore.png` },
  gold_ore:      { name: 'Golderz',     sprite: 'item_gold_ore',      category: 'resource',                       path: `${OP}/gold_ore.png` },
  silver_ore:    { name: 'Silbererz',   sprite: 'item_silver_ore',    category: 'resource',                       path: '/assets/resources/silver_ore.png' },
  mythril_ore:   { name: 'Mythril',     sprite: 'item_mythril_ore',   category: 'resource',                       path: '/assets/resources/mythril_ore.png' },
  steel_ingot:    { name: 'Stahlbarren',   sprite: 'item_steel_ingot',    category: 'resource',                       path: '/assets/resources/steel_ingot.png' },
  iron_ingot:     { name: 'Eisenbarren',   sprite: 'item_iron_ingot',     category: 'resource',                       path: '/assets/resources/iron_ingot.png' },
  copper_ingot:   { name: 'Kupferbarren',  sprite: 'item_copper_ingot',   category: 'resource',                       path: '/assets/resources/copper_ingot.png' },
  silver_ingot:   { name: 'Silberbarren',  sprite: 'item_silver_ingot',   category: 'resource',                       path: '/assets/resources/silver_ingot.png' },
  gold_ingot:     { name: 'Goldbarren',    sprite: 'item_gold_ingot',     category: 'resource',                       path: '/assets/resources/gold_ingot.png' },
  mithril_ingot:  { name: 'Mithrilbarren', sprite: 'item_mithril_ingot',  category: 'resource',                       path: '/assets/resources/mithril_ingot.png' },
  adamant_ingot:  { name: 'Adamantbarren', sprite: 'item_adamant_ingot',  category: 'resource',                       path: '/assets/resources/adamant_ingot.png' },
  platinum_ingot: { name: 'Platinbarren',  sprite: 'item_platinum_ingot', category: 'resource',                       path: '/assets/resources/platinum_ingot.png' },
  tungsten_ingot: { name: 'Wolframbarren', sprite: 'item_tungsten_ingot', category: 'resource',                       path: '/assets/resources/tungsten_ingot.png' },
  crystal_ingot:  { name: 'Kristallbarren',sprite: 'item_crystal_ingot',  category: 'resource',                       path: '/assets/resources/crystal_ingot.png' },
  crystal:       { name: 'Kristall',    sprite: 'item_crystal',       category: 'resource',                       path: `${OP}/blue_crystal.png` },
  bone:          { name: 'Knochen',     sprite: 'item_bone',          category: 'resource',                       path: `${OP}/bone_fragments.png` },
  cloth:         { name: 'Stoff',       sprite: 'item_cloth',         category: 'resource',                       path: `${OP}/cloth_bolt.png` },
  cloth_green:   { name: 'Grüner Stoff',sprite: 'item_cloth_green',   category: 'resource',                       path: '/assets/resources/cloth_green.png' },
  plant_fiber:   { name: 'Pflanzenfaser',sprite: 'item_plant_fiber',  category: 'resource',                       path: '/assets/resources/cloth.png' },
  leather:       { name: 'Leder',       sprite: 'item_leather',       category: 'resource',                       path: `${OP}/leather_roll.png` },
  copper_coin:   { name: 'Kupfermünze', sprite: 'item_copper_coin',   category: 'resource',                       path: '/assets/currency/coin_copper.png' },
  silver_coin:   { name: 'Silbermünze', sprite: 'item_silver_coin',   category: 'resource',                       path: '/assets/currency/coin_silver.png' },
  gold_coin:     { name: 'Goldmünze',   sprite: 'item_gold_coin',     category: 'resource',                       path: '/assets/currency/coin_gold.png' },
  // — Asset-Drop 2026-05-27b: Animal-Products —
  wool_fleece:     { name: 'Wollvlies',       sprite: 'item_wool_fleece',     category: 'resource', path: '/assets/resources/animal_products/wool_fleece.png' },
  wool_shearing:   { name: 'Schurwolle',      sprite: 'item_wool_shearing',   category: 'resource', path: '/assets/resources/animal_products/wool_shearing_bundle.png' },
  wool_cloth_roll: { name: 'Wollstoff-Rolle', sprite: 'item_wool_cloth_roll', category: 'resource', path: '/assets/resources/animal_products/wool_cloth_roll.png' },
  yarn_ball:       { name: 'Wollknäuel',      sprite: 'item_yarn_ball',       category: 'resource', path: '/assets/resources/animal_products/yarn_ball.png' },
  hide_raw:        { name: 'Rohe Tierhaut',   sprite: 'item_hide_raw',        category: 'resource', path: '/assets/resources/animal_products/hide_raw.png' },
  leather_bundle:  { name: 'Leder-Bündel',    sprite: 'item_leather_bundle',  category: 'resource', path: '/assets/resources/animal_products/leather_bundle.png' },
  feathers:        { name: 'Federn',          sprite: 'item_feathers',        category: 'resource', path: '/assets/resources/animal_products/feathers.png' },
  manure:          { name: 'Mist',            sprite: 'item_manure',          category: 'resource', path: '/assets/resources/animal_products/manure_pile.png' },
  wax_block:       { name: 'Wachsblock',      sprite: 'item_wax_block',       category: 'resource', path: '/assets/resources/animal_products/wax_block.png' },
  candle_bundle:   { name: 'Kerzen-Bündel',   sprite: 'item_candle_bundle',   category: 'resource', path: '/assets/resources/animal_products/candle_bundle.png' },
  feed_sack:       { name: 'Futter-Sack',     sprite: 'item_feed_sack',       category: 'resource', path: '/assets/resources/animal_products/feed_sack.png' },
  animal_bedding:  { name: 'Tierstreu',       sprite: 'item_animal_bedding',  category: 'resource', path: '/assets/resources/animal_products/animal_bedding_straw.png' },
  // — Asset-Drop 2026-05-27b: Dairy / Processed Food —
  milk_bucket:   { name: 'Eimer Milch',     sprite: 'item_milk_bucket',   category: 'food', path: '/assets/food/dairy/milk_bucket.png' },
  milk_jug:      { name: 'Milch-Krug',      sprite: 'item_milk_jug',      category: 'food', path: '/assets/food/dairy/milk_jug.png' },
  cream_bowl:    { name: 'Sahne',           sprite: 'item_cream_bowl',    category: 'food', path: '/assets/food/dairy/cream_bowl.png' },
  curds_bowl:    { name: 'Quark',           sprite: 'item_curds_bowl',    category: 'food', path: '/assets/food/dairy/curds_bowl.png' },
  butter_pat:    { name: 'Butter',          sprite: 'item_butter_pat',    category: 'food', path: '/assets/food/dairy/butter_pat.png' },
  cheese_wedge:  { name: 'Käsestück',       sprite: 'item_cheese_wedge',  category: 'food', path: '/assets/food/dairy/cheese_wedge.png' },
  cheese_wheel:  { name: 'Käserad',         sprite: 'item_cheese_wheel',  category: 'food', path: '/assets/food/dairy/cheese_wheel.png' },
  egg:           { name: 'Ei',              sprite: 'item_egg',           category: 'food', path: '/assets/food/dairy/egg.png' },
  egg_basket:    { name: 'Eier-Korb',       sprite: 'item_egg_basket',    category: 'food', path: '/assets/food/dairy/egg_basket.png' },
  flour_sack:    { name: 'Mehl-Sack',       sprite: 'item_flour_sack',    category: 'resource', path: '/assets/food/processed/flour_sack.png' },
  grain_sack:    { name: 'Getreide-Sack',   sprite: 'item_grain_sack',    category: 'resource', path: '/assets/food/processed/grain_sack.png' },
  oat_sack:      { name: 'Hafer-Sack',      sprite: 'item_oat_sack',      category: 'resource', path: '/assets/food/processed/oat_sack.png' },
  salt_bag:      { name: 'Salz-Beutel',     sprite: 'item_salt_bag',      category: 'resource', path: '/assets/food/processed/salt_bag.png' },
  lard_pot:      { name: 'Schmalztopf',     sprite: 'item_lard_pot',      category: 'food',     path: '/assets/food/processed/lard_pot.png' },
  salted_meat:   { name: 'Pökelfleisch',    sprite: 'item_salted_meat',   category: 'food',     path: '/assets/food/processed/salted_meat.png' },
  smoked_meat:   { name: 'Räucherfleisch',  sprite: 'item_smoked_meat',   category: 'food',     path: '/assets/food/processed/smoked_meat.png' },
  sausage:       { name: 'Wurst',           sprite: 'item_sausage',       category: 'food',     path: '/assets/food/processed/sausage.png' },
  dried_fish:    { name: 'Trockenfisch',    sprite: 'item_dried_fish',    category: 'food',     path: '/assets/food/processed/dried_fish_bundle.png' },
  honey_jar:     { name: 'Honigglas',       sprite: 'item_honey_jar',     category: 'food',     path: '/assets/food/processed/honey_jar.png' },
  animal_feed:   { name: 'Tierfutter',      sprite: 'item_animal_feed',   category: 'resource', path: '/assets/food/processed/animal_feed.png' },
  cheese_crate:  { name: 'Käse-Kiste',      sprite: 'item_cheese_crate',  category: 'resource', path: '/assets/food/processed/cheese_crate.png' },
  // — Asset-Drop 2026-05-27b: Neue Werkzeuge —
  pitchfork:     { name: 'Heugabel',        sprite: 'item_pitchfork',     category: 'tool', slot: 'tool', path: '/assets/tools/pitchfork.png' },
  rope_coil:     { name: 'Seil-Rolle',      sprite: 'item_rope_coil',     category: 'resource',          path: '/assets/tools/rope_coil.png' },
};
const EQUIP_SLOTS = [
  { key: 'weapon',     label: 'Waffe' },
  { key: 'helmet',     label: 'Helm' },
  { key: 'chestplate', label: 'Brustpanzer' },
  { key: 'gloves',     label: 'Handschuhe' },
  { key: 'shield',     label: 'Schild' },
  { key: 'boots',      label: 'Stiefel' },
  { key: 'ring',       label: 'Ring' },
  { key: 'amulet',     label: 'Amulett' },
  { key: 'tool',       label: 'Werkzeug' },
];

// ─── Equipment-Sprite-Resolver ─────────────────────────────────────────────
// Mapping: item-kind → Asset-Basename. Greatsword nutzt sword_2h, scythe axe_2h.
const EQUIP_BASE = {
  sword:          'sword_1h',
  greatsword:     'sword_2h',
  axe:            'axe_1h',
  bow:            'bow_long',
  crossbow:       'crossbow',
  dagger:         'dagger',
  throwing_knife: 'dagger',
  mace:           'mace',
  spear:          'spear',
  staff:          'staff',
  wand:           'wand',
  scythe:         'axe_2h',
  helmet:         'helmet',
  chestplate:     'chestplate',
  shield:         'shield',
  boots:          'boots',
};
const WEAPON_MATERIALS = ['wood','copper','iron','steel','silver','gold',
                          'mithril','adamant','platinum','tungsten','crystal'];
const ARMOR_MATERIALS  = ['cloth','leather','fur','copper','iron','silver',
                          'gold','mithril','adamant','platinum','tungsten','crystal'];

// Welle 50 — World-Polish-Animations (Asset-Drop 2026-05-26)
// Spec aus assets/animations/professional/world_polish/manifest.json.
// 192×192 transparente Overlays, 12 FPS.
const WORLD_POLISH_ANIMS = [
  { key:'water_flowers',         frames:14, fps:12, looping:false, category:'farming'  },
  { key:'water_crop_tile',       frames:14, fps:12, looping:false, category:'farming'  },
  { key:'hoe_soil',              frames:12, fps:12, looping:false, category:'farming'  },
  { key:'sow_seeds',             frames:12, fps:12, looping:false, category:'farming'  },
  { key:'harvest_crop',          frames:12, fps:12, looping:false, category:'farming'  },
  { key:'crop_growth_sparkle',   frames:16, fps:12, looping:true,  category:'farming'  },
  { key:'speech_bubble_talk',    frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_trade',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_question',frames:12, fps:12, looping:true,  category:'social'   },
  { key:'speech_bubble_alert',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'thought_bubble_work',   frames:12, fps:12, looping:true,  category:'social'   },
  { key:'mining_chip',           frames:10, fps:12, looping:false, category:'work'     },
  { key:'chop_wood',             frames:10, fps:12, looping:false, category:'work'     },
  { key:'build_hammer',          frames:10, fps:12, looping:false, category:'work'     },
  { key:'crafting_sparks',       frames:14, fps:12, looping:true,  category:'work'     },
  { key:'item_pickup_pop',       frames:10, fps:12, looping:false, category:'feedback' },
  { key:'loot_twinkle',          frames:14, fps:12, looping:true,  category:'feedback' },
  { key:'level_up_ring',         frames:16, fps:12, looping:true,  category:'feedback' },
  { key:'negative_mood_pulse',   frames:12, fps:12, looping:false, category:'feedback' },
  { key:'footstep_dust',         frames: 8, fps:12, looping:true,  category:'ambient'  },
  { key:'leaf_rustle',           frames:16, fps:12, looping:true,  category:'ambient'  },
  { key:'campfire_embers',       frames:16, fps:12, looping:true,  category:'ambient'  },
];

// Welle world-detail-p2 (Asset-Drop 2026-05-27): Animals + Transport.
// Pro item zwei Spritesheets (walk/roll + idle). Frame-Größen variieren pro
// animal/vehicle (siehe assets/professional/world_detail_p2_*_animation_pack_2026_05_27/manifest.json).
// Keys: animal_<animal>_<dir>_walk|idle, transport_<vehicle>_<dir>_roll|idle.
const WORLD_DETAIL_P2_ANIMAL_ANIMS = [
  {"animal": "cow", "direction": "south", "walk_sheet": "/assets/animations/animals/cow/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/cow/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "cow", "direction": "east", "walk_sheet": "/assets/animations/animals/cow/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/cow/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "cow", "direction": "north", "walk_sheet": "/assets/animations/animals/cow/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/cow/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "cow", "direction": "west", "walk_sheet": "/assets/animations/animals/cow/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/cow/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "sheep", "direction": "south", "walk_sheet": "/assets/animations/animals/sheep/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/sheep/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "sheep", "direction": "east", "walk_sheet": "/assets/animations/animals/sheep/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/sheep/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "sheep", "direction": "north", "walk_sheet": "/assets/animations/animals/sheep/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/sheep/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "sheep", "direction": "west", "walk_sheet": "/assets/animations/animals/sheep/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/sheep/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goat", "direction": "south", "walk_sheet": "/assets/animations/animals/goat/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goat/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goat", "direction": "east", "walk_sheet": "/assets/animations/animals/goat/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goat/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goat", "direction": "north", "walk_sheet": "/assets/animations/animals/goat/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goat/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goat", "direction": "west", "walk_sheet": "/assets/animations/animals/goat/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goat/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "pig", "direction": "south", "walk_sheet": "/assets/animations/animals/pig/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/pig/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "pig", "direction": "east", "walk_sheet": "/assets/animations/animals/pig/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/pig/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "pig", "direction": "north", "walk_sheet": "/assets/animations/animals/pig/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/pig/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "pig", "direction": "west", "walk_sheet": "/assets/animations/animals/pig/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/pig/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "horse", "direction": "south", "walk_sheet": "/assets/animations/animals/horse/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/horse/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "horse", "direction": "east", "walk_sheet": "/assets/animations/animals/horse/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/horse/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "horse", "direction": "north", "walk_sheet": "/assets/animations/animals/horse/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/horse/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "horse", "direction": "west", "walk_sheet": "/assets/animations/animals/horse/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/horse/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "farm_dog", "direction": "south", "walk_sheet": "/assets/animations/animals/farm_dog/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/farm_dog/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "farm_dog", "direction": "east", "walk_sheet": "/assets/animations/animals/farm_dog/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/farm_dog/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "farm_dog", "direction": "north", "walk_sheet": "/assets/animations/animals/farm_dog/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/farm_dog/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "farm_dog", "direction": "west", "walk_sheet": "/assets/animations/animals/farm_dog/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/farm_dog/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  // Welle 24 — Poultry + Wildlife (chicken_hen, rooster, duck, goose, rabbit @ 64×64; fox @ 96×96)
  {"animal": "chicken_hen", "direction": "south", "walk_sheet": "/assets/animations/animals/chicken_hen/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/chicken_hen/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "chicken_hen", "direction": "east", "walk_sheet": "/assets/animations/animals/chicken_hen/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/chicken_hen/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "chicken_hen", "direction": "north", "walk_sheet": "/assets/animations/animals/chicken_hen/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/chicken_hen/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "chicken_hen", "direction": "west", "walk_sheet": "/assets/animations/animals/chicken_hen/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/chicken_hen/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rooster", "direction": "south", "walk_sheet": "/assets/animations/animals/rooster/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rooster/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rooster", "direction": "east", "walk_sheet": "/assets/animations/animals/rooster/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rooster/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rooster", "direction": "north", "walk_sheet": "/assets/animations/animals/rooster/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rooster/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rooster", "direction": "west", "walk_sheet": "/assets/animations/animals/rooster/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rooster/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "duck", "direction": "south", "walk_sheet": "/assets/animations/animals/duck/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/duck/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "duck", "direction": "east", "walk_sheet": "/assets/animations/animals/duck/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/duck/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "duck", "direction": "north", "walk_sheet": "/assets/animations/animals/duck/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/duck/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "duck", "direction": "west", "walk_sheet": "/assets/animations/animals/duck/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/duck/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goose", "direction": "south", "walk_sheet": "/assets/animations/animals/goose/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goose/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goose", "direction": "east", "walk_sheet": "/assets/animations/animals/goose/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goose/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goose", "direction": "north", "walk_sheet": "/assets/animations/animals/goose/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goose/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "goose", "direction": "west", "walk_sheet": "/assets/animations/animals/goose/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/goose/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "fox", "direction": "south", "walk_sheet": "/assets/animations/animals/fox/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/fox/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "fox", "direction": "east", "walk_sheet": "/assets/animations/animals/fox/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/fox/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "fox", "direction": "north", "walk_sheet": "/assets/animations/animals/fox/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/fox/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "fox", "direction": "west", "walk_sheet": "/assets/animations/animals/fox/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/fox/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 96, "walk_fh": 96, "idle_fw": 96, "idle_fh": 96},
  {"animal": "rabbit", "direction": "south", "walk_sheet": "/assets/animations/animals/rabbit/south/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rabbit/south/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rabbit", "direction": "east", "walk_sheet": "/assets/animations/animals/rabbit/east/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rabbit/east/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rabbit", "direction": "north", "walk_sheet": "/assets/animations/animals/rabbit/north/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rabbit/north/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
  {"animal": "rabbit", "direction": "west", "walk_sheet": "/assets/animations/animals/rabbit/west/walk_sheet.png", "idle_sheet": "/assets/animations/animals/rabbit/west/idle_sheet.png", "walk_frames": 4, "idle_frames": 2, "walk_fw": 64, "walk_fh": 64, "idle_fw": 64, "idle_fh": 64},
];
const WORLD_DETAIL_P2_TRANSPORT_ANIMS = [
  {"vehicle": "handcart_empty", "direction": "south", "roll_sheet": "/assets/animations/transport/handcart_empty/south/roll_sheet.png", "idle_sheet": "/assets/animations/transport/handcart_empty/south/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "handcart_empty", "direction": "east", "roll_sheet": "/assets/animations/transport/handcart_empty/east/roll_sheet.png", "idle_sheet": "/assets/animations/transport/handcart_empty/east/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "handcart_empty", "direction": "north", "roll_sheet": "/assets/animations/transport/handcart_empty/north/roll_sheet.png", "idle_sheet": "/assets/animations/transport/handcart_empty/north/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "handcart_empty", "direction": "west", "roll_sheet": "/assets/animations/transport/handcart_empty/west/roll_sheet.png", "idle_sheet": "/assets/animations/transport/handcart_empty/west/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "farm_cart_hay", "direction": "south", "roll_sheet": "/assets/animations/transport/farm_cart_hay/south/roll_sheet.png", "idle_sheet": "/assets/animations/transport/farm_cart_hay/south/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "farm_cart_hay", "direction": "east", "roll_sheet": "/assets/animations/transport/farm_cart_hay/east/roll_sheet.png", "idle_sheet": "/assets/animations/transport/farm_cart_hay/east/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "farm_cart_hay", "direction": "north", "roll_sheet": "/assets/animations/transport/farm_cart_hay/north/roll_sheet.png", "idle_sheet": "/assets/animations/transport/farm_cart_hay/north/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "farm_cart_hay", "direction": "west", "roll_sheet": "/assets/animations/transport/farm_cart_hay/west/roll_sheet.png", "idle_sheet": "/assets/animations/transport/farm_cart_hay/west/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 128, "roll_fh": 128, "idle_fw": 128, "idle_fh": 128},
  {"vehicle": "horse_cart_single", "direction": "south", "roll_sheet": "/assets/animations/transport/horse_cart_single/south/roll_sheet.png", "idle_sheet": "/assets/animations/transport/horse_cart_single/south/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "horse_cart_single", "direction": "east", "roll_sheet": "/assets/animations/transport/horse_cart_single/east/roll_sheet.png", "idle_sheet": "/assets/animations/transport/horse_cart_single/east/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "horse_cart_single", "direction": "north", "roll_sheet": "/assets/animations/transport/horse_cart_single/north/roll_sheet.png", "idle_sheet": "/assets/animations/transport/horse_cart_single/north/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "horse_cart_single", "direction": "west", "roll_sheet": "/assets/animations/transport/horse_cart_single/west/roll_sheet.png", "idle_sheet": "/assets/animations/transport/horse_cart_single/west/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "market_wagon_covered", "direction": "south", "roll_sheet": "/assets/animations/transport/market_wagon_covered/south/roll_sheet.png", "idle_sheet": "/assets/animations/transport/market_wagon_covered/south/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "market_wagon_covered", "direction": "east", "roll_sheet": "/assets/animations/transport/market_wagon_covered/east/roll_sheet.png", "idle_sheet": "/assets/animations/transport/market_wagon_covered/east/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "market_wagon_covered", "direction": "north", "roll_sheet": "/assets/animations/transport/market_wagon_covered/north/roll_sheet.png", "idle_sheet": "/assets/animations/transport/market_wagon_covered/north/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
  {"vehicle": "market_wagon_covered", "direction": "west", "roll_sheet": "/assets/animations/transport/market_wagon_covered/west/roll_sheet.png", "idle_sheet": "/assets/animations/transport/market_wagon_covered/west/idle_sheet.png", "roll_frames": 4, "idle_frames": 2, "roll_fw": 160, "roll_fh": 160, "idle_fw": 160, "idle_fh": 160},
];

function _equipDir(category) {
  if (category === 'weapon')  return 'weapons';
  if (category === 'armor')   return 'armor';
  if (category === 'jewelry') return 'jewelry';
  return null;
}

// Liefert den Asset-URL-Pfad. Item kann Inventory-Object oder kind-String sein.
function itemAssetPath(item, materialOpt) {
  const kind = (typeof item === 'string') ? item : item?.kind;
  const quality = (typeof item === 'string') ? null : item?.quality;
  const cfg = ITEM[kind];
  if (!cfg) return '';
  // Pro-Sprite-Set hat Vorrang (Asset-Drop 2026-05-26b)
  if (RARITY_WEAPONS.has(kind)) {
    const r = QUALITY_TO_RARITY[quality || 'normal'] || 'common';
    const p = proWeaponPath(kind, r);
    if (p) return p;
  }
  if (cfg.category === 'armor' && PRO_ARMOR_SLOTS.includes(cfg.slot)) {
    const r = QUALITY_TO_RARITY[quality || 'normal'] || 'common';
    return proArmorPath(cfg.slot, r);
  }
  return cfg.path || '';
}

// Ground-Display-Scale pro Item — Sprites sind alle 64×64, aber Münzen sind
// real klein, Schwerter groß. Skaliert relativ zu TILE_SIZE.
const ITEM_GROUND_SCALE_BY_CATEGORY = {
  resource:   0.55,
  food:       0.55,
  consumable: 0.55,
  magic:      0.65,
  jewelry:    0.45,
  weapon:     0.85,
  armor:      0.75,
  tool:       0.70,
};
const ITEM_GROUND_SCALE_OVERRIDES = {
  // Münzen — kleine Real-Größe
  copper_coin: 0.35,
  silver_coin: 0.35,
  gold_coin:   0.35,
  // Kleine Pflanzen-Items
  herb:        0.50,
  berries:     0.45,
  mushroom_food: 0.50,
  // Große Zweihänder
  greatsword:  1.00,
  scythe:      0.95,
  spear:       0.95,
  staff:       0.95,
  bow:         0.95,
  crossbow:    0.90,
};
function itemGroundScale(item) {
  const kind = typeof item === 'string' ? item : item?.kind;
  if (ITEM_GROUND_SCALE_OVERRIDES[kind] != null) return ITEM_GROUND_SCALE_OVERRIDES[kind];
  const cfg = ITEM[kind];
  if (cfg && ITEM_GROUND_SCALE_BY_CATEGORY[cfg.category] != null) {
    return ITEM_GROUND_SCALE_BY_CATEGORY[cfg.category];
  }
  return 0.60;
}

// Phaser-Texture-Key — Pro-Sprite-Set; fällt auf Base-Sprite zurück.
function itemSpriteKey(scene, item) {
  const kind = (typeof item === 'string') ? item : item?.kind;
  const quality = (typeof item === 'string') ? null : item?.quality;
  const cfg = ITEM[kind];
  if (!cfg) return null;
  // Pro-Weapon-Sprite (rarity-spezifisch)
  if (RARITY_WEAPONS.has(kind)) {
    const r = QUALITY_TO_RARITY[quality || 'normal'] || 'common';
    const rkey = `weapon_rarity_${r}_${kind}`;
    if (scene && scene.textures && scene.textures.exists(rkey)) return rkey;
  }
  // Pro-Armor-Sprite (rarity-spezifisch pro Slot)
  if (cfg.category === 'armor' && PRO_ARMOR_SLOTS.includes(cfg.slot)) {
    const r = QUALITY_TO_RARITY[quality || 'normal'] || 'common';
    const akey = `armor_rarity_${r}_${cfg.slot}`;
    if (scene && scene.textures && scene.textures.exists(akey)) return akey;
  }
  return cfg.sprite;
}

// Quality → Rarity-Mapping (semantisch identische 5 Stufen)
const QUALITY_TO_RARITY = {
  rough: 'poor', normal: 'common', fine: 'rare',
  masterwork: 'very_rare', legendary: 'legendary',
};

// Kategorien die KEINE Qualitätsstufe haben (Roh-Materialien, Münzen etc.).
// Werden visuell als 'rough'/grau gerendert statt common-grün — Qualität
// existiert konzeptuell nur für Equipment.
const NO_QUALITY_CATEGORIES = new Set(['resource', 'food', 'consumable', 'magic']);

function effectiveQuality(item) {
  if (!item) return 'normal';
  const q = item.quality;
  if (q && q !== 'normal') return q;
  const cfg = ITEM[item.kind];
  if (cfg && NO_QUALITY_CATEGORIES.has(cfg.category)) return 'rough';
  return q || 'normal';
}
const RARITY_WEAPONS = new Set(['sword','greatsword','axe','spear','bow','crossbow',
                                 'dagger','mace','staff','wand','scythe','throwing_knife']);

// Pro-Sprite-Set (Asset-Drop 2026-05-26b). Mapping pro Spiel-Kind × Rarity auf
// konkrete Pro-Sprite-IDs aus dem rarity_v2-Manifest. `default` ist der Fallback
// (für Items ohne Quality-Info, Default-Inventar-Display).
const PRO_RARITIES = ['poor','common','rare','very_rare','legendary'];
const PRO_WEAPON_MAP = {
  sword: {
    default: 'black_guard_longsword',
    poor: 'silver_straightsword',
    common: 'black_guard_longsword',
    rare: 'crescent_saber',
    very_rare: 'thorn_blackblade',
    legendary: 'wolf_end_redblade',
  },
  greatsword: {
    default: 'cleaver_greatsword',
    poor: 'cleaver_greatsword',
    common: 'cleaver_greatsword',
    rare: 'rose_glass_sword',
    very_rare: 'azure_glaive',
    legendary: 'crimson_twinblade',
  },
  axe: {
    default: 'old_execution_axe',
    poor: 'iron_hatchet',
    common: 'old_execution_axe',
    rare: 'blue_crescent_axe',
    very_rare: 'flame_cleaver_axe',
    legendary: 'flame_cleaver_axe',
  },
  bow: {
    default: 'ashwood_recurve_bow',
    poor: 'ashwood_recurve_bow',
    common: 'hunter_bow_set',
    rare: 'ebony_longbow',
    very_rare: 'goldleaf_bow',
    legendary: 'gandiva_bow',
  },
  crossbow: {
    // kein dediziertes Crossbow im Pro-Set — Bow-Sprites als Fallback
    default: 'stormbow',
    poor: 'ashwood_recurve_bow',
    common: 'hunter_bow_set',
    rare: 'stormbow',
    very_rare: 'goldleaf_bow',
    legendary: 'gandiva_bow',
  },
  spear: {
    default: 'plain_war_spear',
    poor: 'plain_war_spear',
    common: 'plain_war_spear',
    rare: 'raven_halberd',
    very_rare: 'bloodpoint_lance',
    legendary: 'amethyst_trident',
  },
  staff: {
    default: 'red_oak_staff',
    poor: 'red_oak_staff',
    common: 'red_oak_staff',
    rare: 'white_magus_staff',
    very_rare: 'white_magus_staff',
    legendary: 'white_magus_staff',
  },
  wand: {
    // kein Wand im Pro-Set — Staff-Sprites
    default: 'red_oak_staff',
    poor: 'red_oak_staff',
    common: 'red_oak_staff',
    rare: 'white_magus_staff',
    very_rare: 'white_magus_staff',
    legendary: 'white_magus_staff',
  },
  scythe: {
    default: 'graveyard_scythe',
    poor: 'iron_hook_sickle',
    common: 'iron_hook_sickle',
    rare: 'graveyard_scythe',
    very_rare: 'chain_reaper',
    legendary: 'void_reaper_scythe',
  },
  dagger: {
    default: 'hooked_ritual_dagger',
    poor: 'hooked_ritual_dagger',
    common: 'hooked_ritual_dagger',
    rare: 'hooked_ritual_dagger',
    very_rare: 'blackthorn_shard',
    legendary: 'ice_and_night_blades',
  },
  throwing_knife: {
    default: 'bloodtalon_throwers',
    poor: 'bloodtalon_throwers',
    common: 'bloodtalon_throwers',
    rare: 'bloodtalon_throwers',
    very_rare: 'bloodtalon_throwers',
    legendary: 'bloodtalon_throwers',
  },
  mace: {
    // kein Mace im Pro-Set — Axe-Sprites als nächstbester Blunt/Heavy-Look
    default: 'iron_hatchet',
    poor: 'iron_hatchet',
    common: 'old_execution_axe',
    rare: 'blue_crescent_axe',
    very_rare: 'flame_cleaver_axe',
    legendary: 'flame_cleaver_axe',
  },
};
const PRO_ARMOR_SLOTS = ['helmet','chestplate','shield','boots','gloves'];

// Pro-Armor-Set (Asset-Drop 2026-05-26c). Nicht jede Rarity hat ein passendes
// Stück für jeden Slot — fehlende Tiers fallen auf das nächstgelegene zurück.
const PRO_ARMOR_MAP = {
  helmet: {
    // kein poor/common — rare-Helm ist neutraler Fallback
    default:   'crested_hoplite_helm',
    poor:      'crested_hoplite_helm',
    common:    'crested_hoplite_helm',
    rare:      'crested_hoplite_helm',
    very_rare: 'crowned_steel_helm',
    legendary: 'templar_visor_helm',
  },
  chestplate: {
    // kein poor/legendary — common am unteren Ende, very_rare oben
    default:   'wandering_knight_armor',
    poor:      'grey_landsknecht_armor',
    common:    'wandering_knight_armor',
    rare:      'mercenary_plate_cuirass',
    very_rare: 'samurai_war_armor',
    legendary: 'samurai_war_armor',
  },
  gloves: {
    default:   'thief_buckled_gloves',
    poor:      'black_leather_glove',
    common:    'thief_buckled_gloves',
    rare:      'stone_guard_gauntlets',
    very_rare: 'noble_gilded_gloves',
    legendary: 'void_claw_gauntlets',
  },
  shield: {
    // nur ein Pro-Sprite — ornate_guard_shield für alle Tiers
    default:   'ornate_guard_shield',
    poor:      'ornate_guard_shield',
    common:    'ornate_guard_shield',
    rare:      'ornate_guard_shield',
    very_rare: 'ornate_guard_shield',
    legendary: 'ornate_guard_shield',
  },
  boots: {
    default:   'dwarven_field_boots',
    poor:      'wrapped_ranger_boots',
    common:    'dwarven_field_boots',
    rare:      'middle_earth_plate_boots',
    very_rare: 'middle_earth_plate_boots',
    legendary: 'ember_wolf_greaves',
  },
};

// Welle 23: Set aller (rarity, slug) Kombinationen die unter rarity_v2/
// existieren. Generiert via tools/check_weapons.py. Wenn eine angeforderte
// Kombination NICHT drin ist, fällt proWeaponPath auf icons_128/ zurück
// (dort liegen die Basis-Sprites für alle Slugs).
const PRO_WEAPON_RARITY_FILES = new Set([
  'common|ashwood_recurve_bow','common|black_guard_longsword','common|cleaver_greatsword',
  'common|hunter_bow_set','common|iron_hook_sickle','common|old_execution_axe',
  'common|red_oak_staff','common|steel_katana',
  'legendary|amethyst_trident','legendary|crimson_twinblade','legendary|flame_cleaver_axe',
  'legendary|gandiva_bow','legendary|obsidian_runeblade','legendary|void_reaper_scythe',
  'legendary|wolf_end_redblade',
  'poor|iron_hatchet','poor|plain_aruming_sword','poor|plain_war_spear',
  'poor|silver_straightsword','poor|woodcutter_hatchet',
  'rare|blackthorn_shard','rare|bloodtalon_throwers','rare|blue_crescent_axe',
  'rare|crescent_saber','rare|ebony_longbow','rare|graveyard_scythe',
  'rare|hooked_ritual_dagger','rare|ice_and_night_blades','rare|raven_halberd',
  'rare|rose_glass_sword','rare|stormbow','rare|white_magus_staff',
  'very_rare|azure_glaive','very_rare|bloodpoint_lance','very_rare|chain_reaper',
  'very_rare|demon_slayer_lance','very_rare|goldleaf_bow','very_rare|ruby_spear',
  'very_rare|sunspike_lance','very_rare|thorn_blackblade',
]);

function proWeaponPath(kind, rarity) {
  const m = PRO_WEAPON_MAP[kind];
  if (!m) return null;
  const id = m[rarity] || m.default;
  if (!id) return null;
  // Wenn rarity_v2-File existiert: nutze es. Sonst Fallback auf icons_128
  // (Basis-Sprite ohne Rarity-Tinting).
  if (rarity && rarity !== 'default'
      && PRO_WEAPON_RARITY_FILES.has(`${rarity}|${id}`)) {
    return `/assets/equipment/weapons/professional/reference_based/rarity_v2/${rarity}/${id}.png`;
  }
  return `/assets/equipment/weapons/professional/reference_based/icons_128/${id}.png`;
}
function proArmorPath(slot, rarity) {
  const m = PRO_ARMOR_MAP[slot];
  if (!m) return null;
  const r = rarity || 'common';
  const id = m[r] || m.default;
  if (!id) return null;
  // Files liegen unter der Rarity, in der das Sprite zugewiesen wurde — nicht
  // unter `r`. Lookup über die Slot-Map.
  return `/assets/equipment/armor/professional/reference_based/by_rarity/${_proArmorAssetRarity(slot, id)}/${id}.png`;
}

// Pro Armor-Asset hat eine canonical Rarity (im Manifest). Wir mappen
// Asset-ID auf den Pfad-Rarity-Slug.
const _PRO_ARMOR_RARITY_OF = {
  // common
  grey_landsknecht_armor: 'common', black_tactical_armor: 'common',
  green_hooded_mantle: 'common', wandering_knight_armor: 'common',
  wrapped_ranger_boots: 'common', dwarven_field_boots: 'common',
  thief_buckled_gloves: 'common', heavy_iron_gauntlet: 'common',
  // rare
  crested_hoplite_helm: 'rare', black_knight_helm: 'rare',
  mercenary_plate_cuirass: 'rare', linothorax_cuirass: 'rare',
  black_iron_greaves: 'rare', runeplate_greaves: 'rare', middle_earth_plate_boots: 'rare',
  stone_guard_gauntlets: 'rare', fur_cuffed_brawler_gloves: 'rare', black_thievery_gloves: 'rare',
  // very_rare
  winged_crusader_helm: 'very_rare', winged_knight_helm: 'very_rare', crowned_steel_helm: 'very_rare',
  spiked_war_cuirass: 'very_rare', samurai_war_armor: 'very_rare',
  noble_gilded_gloves: 'very_rare', ornate_guard_shield: 'very_rare',
  // legendary
  templar_visor_helm: 'legendary', plague_doctor_helm: 'legendary', antlered_dark_helm: 'legendary',
  ember_wolf_greaves: 'legendary', void_claw_gauntlets: 'legendary',
  // poor
  black_leather_glove: 'poor',
};
function _proArmorAssetRarity(_slot, assetId) {
  return _PRO_ARMOR_RARITY_OF[assetId] || 'common';
}

// ─── Material-Auswahl für Wände/Böden ─────────────────────────────────────────
const MATERIALS = ['stone', 'wood', 'straw'];
const MATERIAL_LABELS = { stone: 'Stein', wood: 'Holz', straw: 'Stroh' };

// ─── Wand-Auto-Tiling Bitmask N=1 E=2 S=4 W=8 ────────────────────────────────
// Map auf Sprite-Varianten (corner_ne, end_s, straight_ns etc.) — Fallback bei
// fehlenden Varianten (T, Cross) ist die jeweilige Achse.
const WALL_MASK_TO_VARIANT = {
  0:  'straight_ns',  // alone — fallback
  1:  'end_s',        // N
  2:  'end_w',        // E
  3:  'corner_ne',    // N+E
  4:  'end_n',        // S
  5:  'straight_ns',  // N+S
  6:  'corner_es',    // E+S
  7:  'straight_ns',  // N+E+S — kein T, fallback
  8:  'end_e',        // W
  9:  'corner_wn',    // N+W
  10: 'straight_ew',  // E+W
  11: 'straight_ew',  // N+E+W — kein T, fallback
  12: 'corner_sw',    // S+W
  13: 'straight_ns',  // N+S+W — kein T, fallback
  14: 'straight_ew',  // E+S+W — kein T, fallback
  15: 'straight_ew',  // Cross — kein Sprite, fallback
};

// Spieler-Name kommt aus dem Auth-Cookie (siehe IIFE am Ende). Phaser-Init wartet darauf.
let MY_ID = null;
let MY_ROLE = null;

// ─── Phaser Scene ─────────────────────────────────────────────────────────────
class WorldScene extends Phaser.Scene {
  constructor() {
    super({ key: 'WorldScene' });
    this.otherPlayers   = {};
    this.mySprite       = null;
    this.myTileX        = 0;
    this.myTileY        = 0;
    // Pixel-Movement (kontinuierlich, smooth)
    // Hitbox-Best-Practice für tile-based 2D top-down (Stardew, Pokémon, RimWorld):
    //  • Movement-Hitbox ist KLEINER als das Sprite (forgiveness, "fair feels")
    //  • Combat-Range wird tile-basiert geprüft (Manhattan/Chebyshev), nicht pixel-perfect
    //  • Origin am Sprite-Mittelpunkt für sauberes Z-Order
    //  • Tap-Targets (Items, NPCs) min. 32×32 px für Mobile (Apple HIG/Material)
    // → collisionHalf 14px (44% von TILE_SIZE) statt 50% — Player rutscht durch enge Lücken,
    //   Treffer fühlt sich "knapp aber fair" an
    this.myPx           = 0;
    this.myPy           = 0;
    this.moveSpeed      = 240;        // px/sec
    this.collisionHalf  = 14;         // px Hitbox-Radius (≈44% TILE_SIZE) — forgiveness
    this.ws             = null;
    this.wasd           = null;
    this.tileSprites    = {};          // key: "x,y" → Phaser.Image für Welt-Tiles
    this.chunks         = {};          // key: "cx,cy" → 2D-Array (CHUNK_SIZE × CHUNK_SIZE)
    this.worldData      = { width: 0, height: 0 };  // Legacy, wird nicht mehr genutzt
    this.structSprites  = {};          // key: "x,y" → Phaser.Image (Object-Layer)
    this.structures     = {};          // key: "x,y" → Object-Layer-Struct
    this.floorSprites   = {};          // key: "x,y" → Phaser.Image (Floor-Layer)
    this.floors         = {};          // key: "x,y" → Floor-Layer-Struct
    this.doorFrameSprites = {};        // key: "x,y" → Wall-Rahmen-Sprite hinter Tür
    this.npcs           = {};          // key: npc_id → sprite + state
    this.activeDialog   = null;        // { npc_id, waiting: bool }
    this.selectedMaterial = 'stone';   // für Bauen: stone | wood | straw
    this.itemSprites    = {};          // key: item_id → Phaser.Image (für Boden-Items)
    this.weatherLayers  = {};          // key: layer-name → {img, frame, count, alpha}
    this.weatherPhase   = 'clear';     // 'clear' | 'rain' | 'snow' | 'fog' | 'swamp_mist'
    this.weatherIntensity = 0;         // 0=clear, 1=light, 2=medium, 3=heavy, 4=peak
    this.inventory      = [];          // Spieler-Inventar [item dict, ...]
    this.inventoryOpen  = false;
    this.myHp           = 100;
    this.myMaxHp        = 100;
    this.myMana         = 50;
    this.myMaxMana      = 50;
    this.myHunger       = 100;
    this.myMaxHunger    = 100;
    this.myThirst       = 100;
    this.myMaxThirst    = 100;
    this.myStamina      = 100;
    this.myMaxStamina   = 100;
    this.mySkills       = {};
    this.skillsOpen     = false;
    this.researchOpen   = false;
    this.myResearch     = {};
    this.questsOpen     = false;
    this.myQuests       = [];
    this.talentsOpen    = false;
    this.myTalents      = { learned: [], points: 0, tree: {} };
    this.activeTalentTab = 'combat';
    this.factionsOpen   = false;
    this.myFactions     = [];
    this.attributesOpen = false;
    this.myAttributes   = { values: {}, labels: {} };
    this.learnedSpells  = [];
    // Welle 9b: Dungeon-Mode
    this.inDungeon      = false;
    this.dungeonTiles   = null;
    this.dungeonSize    = 0;
    this.dungeonSprites = {};   // key: "x,y" → Phaser.Image
    // Welle 34: Hotbar — 9 Slots mit item_id-Refs (localStorage-persistiert)
    this.hotbar         = this._loadHotbar();
    this.activeHotbar   = -1;
    this.activeChest    = null;        // { chest_id, items }
    this.activeCrafting = null;        // { station, recipes }
    this.activeTrade    = null;        // { npc_id, npc_name, offerings, coins }
    this.buildMode      = false;
    this.selectedStruct = 'wall';
    this.placeRotation  = 0;          // 0/90/180/270 — R-Taste cycled
    this.placeGhost     = null;       // Phaser-Sprite, semi-transparent
    this.hoverGfx       = null;
  }

  preload() {
    this.load.image('tile_water',      '/assets/tiles/water.png');
    this.load.image('tile_sand',       '/assets/tiles/sand.png');
    this.load.image('tile_grass',      '/assets/tiles/grass.png');
    this.load.image('tile_forest',     '/assets/tiles/forest.png');
    this.load.image('tile_mountain',   '/assets/tiles/mountain.png');
    this.load.image('tile_desert',     '/assets/tiles/desert.png');
    this.load.image('tile_jungle',     '/assets/tiles/jungle.png');
    this.load.image('tile_lava',       '/assets/tiles/lava.png');
    this.load.image('tile_snow',       '/assets/tiles/snow.png');
    this.load.image('tile_swamp',      '/assets/tiles/swamp.png');
    this.load.image('struct_wall',     '/assets/structures/wall.png');  // Legacy-Fallback
    this.load.image('struct_floor',    '/assets/structures/floor.png');
    this.load.image('struct_campfire', '/assets/structures/campfire.png');
    this.load.image('struct_marker',   '/assets/structures/marker.png');
    // Welle 24 — World-Detail Asset-Drop (sign/transport/farm)
    this.load.image('struct_crossroads_signpost', '/assets/props/settlement/signs/wayfinding/crossroads_signpost.png');
    this.load.image('struct_signpost_village', '/assets/props/settlement/signs/wayfinding/signpost_village.png');
    this.load.image('struct_signpost_market', '/assets/props/settlement/signs/wayfinding/signpost_market.png');
    this.load.image('struct_signpost_inn', '/assets/props/settlement/signs/wayfinding/signpost_inn.png');
    this.load.image('struct_signpost_church', '/assets/props/settlement/signs/wayfinding/signpost_church.png');
    this.load.image('struct_signpost_mill', '/assets/props/settlement/signs/wayfinding/signpost_mill.png');
    this.load.image('struct_signpost_mine', '/assets/props/settlement/signs/wayfinding/signpost_mine.png');
    this.load.image('struct_warning_bandits', '/assets/props/settlement/signs/wayfinding/warning_bandits.png');
    this.load.image('struct_signpost_town', '/assets/props/settlement/signs/wayfinding/signpost_town.png');
    this.load.image('struct_signpost_farm', '/assets/props/settlement/signs/wayfinding/signpost_farm.png');
    this.load.image('struct_signpost_forest', '/assets/props/settlement/signs/wayfinding/signpost_forest.png');
    this.load.image('struct_signpost_docks', '/assets/props/settlement/signs/wayfinding/signpost_docks.png');
    this.load.image('struct_signpost_graveyard', '/assets/props/settlement/signs/wayfinding/signpost_graveyard.png');
    this.load.image('struct_road_marker_stone', '/assets/props/settlement/signs/wayfinding/road_marker_stone.png');
    this.load.image('struct_boundary_post', '/assets/props/settlement/signs/wayfinding/boundary_post.png');
    this.load.image('struct_blank_weathered_signpost', '/assets/props/settlement/signs/wayfinding/blank_weathered_signpost.png');
    this.load.image('struct_bakery_sign', '/assets/props/settlement/signs/trade/bakery_sign.png');
    this.load.image('struct_blacksmith_sign', '/assets/props/settlement/signs/trade/blacksmith_sign.png');
    this.load.image('struct_tailor_sign', '/assets/props/settlement/signs/trade/tailor_sign.png');
    this.load.image('struct_inn_sign', '/assets/props/settlement/signs/trade/inn_sign.png');
    this.load.image('struct_stable_sign', '/assets/props/settlement/signs/trade/stable_sign.png');
    this.load.image('struct_market_sign', '/assets/props/settlement/signs/trade/market_sign.png');
    this.load.image('struct_apothecary_sign', '/assets/props/settlement/signs/trade/apothecary_sign.png');
    this.load.image('struct_carpenter_sign', '/assets/props/settlement/signs/trade/carpenter_sign.png');
    this.load.image('struct_miller_sign', '/assets/props/settlement/signs/trade/miller_sign.png');
    this.load.image('struct_dairy_sign', '/assets/props/settlement/signs/trade/dairy_sign.png');
    this.load.image('struct_butcher_sign', '/assets/props/settlement/signs/trade/butcher_sign.png');
    this.load.image('struct_fishmonger_sign', '/assets/props/settlement/signs/trade/fishmonger_sign.png');
    this.load.image('struct_tanner_sign', '/assets/props/settlement/signs/trade/tanner_sign.png');
    this.load.image('struct_weaver_sign', '/assets/props/settlement/signs/trade/weaver_sign.png');
    this.load.image('struct_tavern_red_lion_sign', '/assets/props/settlement/signs/trade/tavern_red_lion_sign.png');
    this.load.image('struct_scribe_sign', '/assets/props/settlement/signs/trade/scribe_sign.png');
    this.load.image('struct_handcart_empty', '/assets/props/transport/handcart_empty.png');
    this.load.image('struct_handcart_crates', '/assets/props/transport/handcart_crates.png');
    this.load.image('struct_farm_cart_empty', '/assets/props/transport/farm_cart_empty.png');
    this.load.image('struct_farm_cart_hay', '/assets/props/transport/farm_cart_hay.png');
    this.load.image('struct_farm_cart_barrels', '/assets/props/transport/farm_cart_barrels.png');
    this.load.image('struct_market_wagon_covered', '/assets/props/transport/market_wagon_covered.png');
    this.load.image('struct_merchant_wagon_closed', '/assets/props/transport/merchant_wagon_closed.png');
    this.load.image('struct_horse_cart_single', '/assets/props/transport/horse_cart_single.png');
    this.load.image('struct_horse_cart_pair', '/assets/props/transport/horse_cart_pair.png');
    this.load.image('struct_ox_cart', '/assets/props/transport/ox_cart.png');
    this.load.image('struct_donkey_pack_cart', '/assets/props/transport/donkey_pack_cart.png');
    this.load.image('struct_broken_wagon_large', '/assets/props/transport/broken_wagon_large.png');
    this.load.image('struct_wagon_wheel_loose', '/assets/props/transport/wagon_wheel_loose.png');
    this.load.image('struct_wagon_harness', '/assets/props/transport/wagon_harness.png');
    this.load.image('struct_hitching_post', '/assets/props/transport/hitching_post.png');
    this.load.image('struct_wheelbarrow_tools', '/assets/props/transport/wheelbarrow_tools.png');
    this.load.image('struct_barn_small', '/assets/structures/farm/barn_small.png');
    this.load.image('struct_barn_large', '/assets/structures/farm/barn_large.png');
    this.load.image('struct_stable', '/assets/structures/farm/stable.png');
    this.load.image('struct_cow_shed', '/assets/structures/farm/cow_shed.png');
    this.load.image('struct_sheepfold', '/assets/structures/farm/sheepfold.png');
    this.load.image('struct_goat_pen', '/assets/structures/farm/goat_pen.png');
    this.load.image('struct_pigsty', '/assets/structures/farm/pigsty.png');
    this.load.image('struct_henhouse', '/assets/structures/farm/henhouse.png');
    this.load.image('struct_duck_pond', '/assets/structures/farm/duck_pond.png');
    this.load.image('struct_goose_pasture_marker', '/assets/structures/farm/goose_pasture_marker.png');
    this.load.image('struct_dovecote', '/assets/structures/farm/dovecote.png');
    this.load.image('struct_cart_shed', '/assets/structures/farm/cart_shed.png');
    this.load.image('struct_dairy_house', '/assets/structures/farm/dairy_house.png');
    this.load.image('struct_smokehouse', '/assets/structures/farm/smokehouse.png');
    this.load.image('struct_hayloft', '/assets/structures/farm/hayloft.png');
    this.load.image('struct_granary', '/assets/structures/farm/granary.png');
    this.load.image('struct_water_trough', '/assets/structures/farm/water_trough.png');
    this.load.image('struct_feed_trough', '/assets/structures/farm/feed_trough.png');
    this.load.image('struct_hay_bale', '/assets/structures/farm/hay_bale.png');
    this.load.image('struct_hay_stack', '/assets/structures/farm/hay_stack.png');
    this.load.image('struct_straw_bale', '/assets/structures/farm/straw_bale.png');
    this.load.image('struct_feed_sack', '/assets/resources/animal_products/feed_sack.png');
    this.load.image('struct_fence_gate_farm', '/assets/structures/farm/fence_gate_farm.png');
    this.load.image('struct_wooden_fence_segment', '/assets/structures/farm/wooden_fence_segment.png');
    this.load.image('struct_milking_stool', '/assets/structures/farm/milking_stool.png');
    this.load.image('struct_cheese_press', '/assets/structures/farm/cheese_press.png');
    this.load.image('struct_nesting_box_egg', '/assets/structures/farm/nesting_box_egg.png');
    this.load.image('struct_animal_bedding_straw', '/assets/resources/animal_products/animal_bedding_straw.png');
    this.load.image('struct_pitchfork', '/assets/tools/pitchfork.png');
    this.load.image('struct_shovel', '/assets/tools/shovel.png');
    this.load.image('struct_wooden_bucket', '/assets/tools/wooden_bucket.png');
    this.load.image('struct_rope_coil', '/assets/tools/rope_coil.png');
    this.load.image('struct_chest',    '/assets/structures/chest.png');
    this.load.image('struct_workbench','/assets/structures/workbench.png');
    this.load.image('struct_furnace',  '/assets/structures/furnace.png');
    this.load.image('struct_anvil',    '/assets/structures/anvil.png');
    this.load.image('struct_bed',      '/assets/structures/bed.png');
    this.load.image('struct_well',     '/assets/structures/well.png');
    this.load.image('struct_farm_plot','/assets/structures/farm_plot.png');
    this.load.image('struct_spike_trap',  '/assets/traps/spike_trap.png');
    this.load.image('struct_poison_trap', '/assets/traps/poison_trap.png');
    this.load.image('struct_stairs_down', '/assets/dungeons/stairs_down.png');
    // Welle 23 — Gilden + Tempel + Quest-Board (Sprites fehlen noch in
    // assets/, daher als Platzhalter andere Structure-Sprites recycled).
    // Sobald echte Sprites da sind: hier Pfade auf eigene Files umstellen.
    this.load.image('struct_mage_guild',     '/assets/structures/workbench.png');
    this.load.image('struct_fighters_guild', '/assets/structures/anvil.png');
    this.load.image('struct_healers_guild',  '/assets/structures/bed.png');
    this.load.image('struct_thieves_guild',  '/assets/structures/chest.png');
    this.load.image('struct_temple',         '/assets/structures/well.png');
    this.load.image('struct_quest_board',    '/assets/structures/marker.png');

    // Deko-Props — Default-Pfade aus /assets/props/<cat>/.
    for (const p of ['tree_oak','tree_pine','tree_dead','tree_stump','fallen_log',
                     'bush','tall_grass','flowers','mushrooms',
                     'rock_small','rock_large','rock_mossy']) {
      this.load.image(`prop_${p}`, `/assets/props/nature/${p}.png`);
    }
    for (const p of ['lily_pads','reeds','dock_straight','wooden_bridge','shipwreck']) {
      this.load.image(`prop_${p}`, `/assets/props/water/${p}.png`);
    }
    for (const p of ['broken_cart','barrel','crate','sack','fence','camp_tent','cooking_pot']) {
      this.load.image(`prop_${p}`, `/assets/props/settlement/${p}.png`);
    }
    // Override mit hochwertigen original_pack-Versionen wo verfügbar (128×128
    // hand-painted statt der älteren 64×64 props).
    const OP_PROPS = {
      tree_oak:    'oak_tree',     tree_pine:   'pine_tree',
      tree_dead:   'dead_tree',    rock_mossy:  'mossy_rock',
      bush:        'bush',         tall_grass:  'tall_grass_tuft',
      mushrooms:   'mushroom_cluster',
      broken_cart: 'broken_cart',  barrel:      'barrel',
    };
    for (const [key, slug] of Object.entries(OP_PROPS)) {
      this.load.image(`prop_${key}`,
        `/assets/professional/original_pack_2026_05_27/icons_128/${slug}.png`);
    }
    // Neuer Struktur-Typ aus original_pack — Rune-Altar für Forschungs-/Ritual-Sites.
    this.load.image('prop_rune_altar',
      '/assets/professional/original_pack_2026_05_27/icons_128/rune_altar.png');
    for (const p of ['ruin_pillar','rubble','statue_broken','bones_scatter','gravestone']) {
      this.load.image(`prop_${p}`, `/assets/props/ruins/${p}.png`);
    }
    for (const p of ['dock_corner','boat_small','anchor','fishing_net','driftwood']) {
      this.load.image(`prop_${p}`, `/assets/props/water/${p}.png`);
    }
    // Welle 12: Biome-spezifische Props
    for (const p of ['cactus','desert_skull','dry_bush']) {
      this.load.image(`prop_${p}`, `/assets/props/biomes/desert/${p}.png`);
    }
    for (const p of ['jungle_flower','jungle_vines','palm_tree']) {
      this.load.image(`prop_${p}`, `/assets/props/biomes/jungle/${p}.png`);
    }
    for (const p of ['frozen_bush','ice_crystal','snow_rock']) {
      this.load.image(`prop_${p}`, `/assets/props/biomes/snow/${p}.png`);
    }
    // Farming-Drop 2026-05-26
    for (const p of ['strawberry_bush','blueberry_bush','blackberry_bush','raspberry_bush',
                     'carrot_plant','potato_plant','cucumber_plant','tomato_plant',
                     'onion_plant','cabbage_plant','pumpkin_plant','corn_plant',
                     'wheat_seedling','wheat_grown']) {
      this.load.image(`prop_${p}`, `/assets/props/crops/${p}.png`);
    }
    for (const p of ['apple_tree','pear_tree','plum_tree','cherry_tree']) {
      this.load.image(`prop_${p}`, `/assets/props/orchard/${p}.png`);
    }
    // Asset-Drop 2026-05-27b: Farm-Gebäude + Farm-Props (16 Gebäude + 12 Props).
    // Sprite-Key: farm_<kind>, Pfade aus assets/structures/farm/.
    for (const f of ['barn_large','barn_small','cow_shed','pigsty','henhouse',
                     'goat_pen','sheepfold','stable','dovecote','dairy_house',
                     'granary','hayloft','smokehouse','cart_shed',
                     'duck_pond','goose_pasture_marker',
                     'feed_trough','water_trough','hay_bale','hay_stack','straw_bale',
                     'cheese_press','milking_stool','nesting_box_egg',
                     'wooden_fence_segment']) {
      this.load.image(`farm_${f}`, `/assets/structures/farm/${f}.png`);
    }
    // fence_gate_farm hat einen abweichenden Filename
    this.load.image('farm_fence_gate', '/assets/structures/farm/fence_gate_farm.png');
    // butter_churn + cheese_rack liegen unter food/dairy/ statt structures/farm/
    this.load.image('farm_butter_churn', '/assets/food/dairy/butter_churn.png');
    this.load.image('farm_cheese_rack',  '/assets/food/dairy/cheese_rack.png');
    for (const p of ['swamp_bubbles','swamp_log']) {
      this.load.image(`prop_${p}`, `/assets/props/biomes/swamp/${p}.png`);
    }
    this.load.image('prop_lava_rock', '/assets/props/biomes/lava/lava_rock.png');
    // Dungeon-Tiles + Props (für Welle 9b — bereits ladbar)
    for (const t of ['dungeon_door','dungeon_floor','dungeon_wall','stairs_down']) {
      this.load.image(`dungeon_${t}`, `/assets/dungeons/${t}.png`);
    }
    for (const p of ['altar','brazier','sarcophagus','treasure_chest','wall_torch']) {
      this.load.image(`prop_${p}`, `/assets/dungeon_props/${p}.png`);
    }

    // Visual-Effects
    this.load.image('fx_hit_spark',    '/assets/effects/hit_spark.png');
    this.load.image('fx_heal_glow',    '/assets/effects/heal_glow.png');
    this.load.image('fx_poison_cloud', '/assets/effects/poison_cloud.png');
    this.load.image('char_player',     '/assets/characters/player.png');
    // Welle 23 — Player-Presets (Character-Creation)
    for (const p of ['ember_mage', 'iron_delver', 'knife_runner',
                      'shieldbearer', 'wanderer_cloak', 'wild_ranger']) {
      this.load.image(`preset_${p}`, `/assets/characters/player_presets/${p}.png`);
    }
    this.load.image('fx_shadow',       '/assets/effects/shadow.png');

    // Pro-Set (Welle 14): hochwertige world-Sprites unter world_sprites/reference_based/.
    const PRO_MONSTERS = [
      'razorback_vermin','spined_abyss_larva','reed_walker',
      'redland_scavenger','mossback_warden','grave_wraith',
      'serpent_oracle','urtikus_eye_fiend','mantis_chimera',
      'iron_spider','dendroid_guardian','blood_antler_drake',
      'kaiju_thornback','void_eye_brute','frost_rune_boar_prime',
      'magma_shell_devourer','rockshell_colossus',
    ];
    for (const m of PRO_MONSTERS) {
      this.load.image(`monster_${m}`,
        `/assets/monsters/world_sprites/reference_based/sprites_96/${m}_world_96.png`);
    }
    // Welle 23: Legacy-Creature-Sprites aus dem Animations-Asset-Pool nutzen
    // (idle_1.png als static-Sprite). Jede Kreatur bekommt damit ihr eigenes
    // Aussehen statt monster_unknown-Fallback. Hostile-only: friendly NPCs
    // werden weiterhin aus /assets/characters/npcs/ geladen (siehe unten).
    // bandit/robber/thief sind Menschen → bekommen Character-Sprites (oben geladen),
    // nicht in dieser Monster-Liste.
    const LEGACY_MONSTERS = [
      'goblin','wolf','skeleton','spider','slime',
      'rat','bat','zombie','boar','bear',
      'ogre','necromancer','dragon_whelp',
      'stag','lynx','cougar','wolverine','dire_wolf','wolf_alpha',
      'cave_bear','polar_bear','crocodile','cobra',
      'slimelet','fae_mite','gloom_moth','ember_newt','ember_rat',
      'shadow_bat','thorn_scarab','crystal_beetle','crystal_tick',
      'frost_sprite','fire_imp','mushroom_imp','thornling','treant',
      'stone_golem','crystal_golem','gargoyle','bone_crawler','giant_spider',
      'minotaur','harpy','basilisk','chimera','griffin','hydra','manticore',
    ];
    for (const m of LEGACY_MONSTERS) {
      this.load.image(`monster_${m}`, `/assets/animations/monsters/${m}/idle_1.png`);
    }
    // Generischer Fallback nur noch falls eine Kreatur weder Pro- noch Legacy-
    // Sprite hat (sollte nicht passieren, aber schützt vor Crashes).
    this.load.image('monster_unknown',
      `/assets/monsters/world_sprites/reference_based/sprites_96/razorback_vermin_world_96.png`);
    // Walk-Animation (Welle 40)
    for (const dir of ['down','up','left','right']) {
      for (const f of [1, 2]) {
        this.load.image(`player_walk_${dir}_${f}`, `/assets/animations/player/walk_${dir}_${f}.png`);
      }
    }
    // Walk-Cycle für animierte Friendly-NPCs (Welle 23 — 7 Kinds × 10 Frames).
    // Prefix `cha_` für /assets/animations/characters/, `mob_` für /monsters/.
    // `_updateWalkFrame` wählt den Prefix anhand des NPC-Kinds.
    for (const kind of ANIMATED_NPC_KINDS) {
      for (const f of [1, 2]) {
        this.load.image(`cha_${kind}_idle_${f}`,
          `/assets/animations/characters/${kind}/idle_${f}.png`);
        for (const dir of ['down','up','left','right']) {
          this.load.image(`cha_${kind}_walk_${dir}_${f}`,
            `/assets/animations/characters/${kind}/walk_${dir}_${f}.png`);
        }
      }
    }
    // Asset-Drop 2026-05-27b: Walk-Cycles für Nutztiere + Carts.
    // Struktur: /assets/animations/animals/<base>/<direction>/walk_NN.png (4 frames)
    // + idle_NN.png (2 frames). Direction = north/south/east/west.
    // Wir mappen Phaser-Direction → animation-Direction und nutzen Frame 1+3
    // aus den 4 walk-frames für das existierende 2-Frame-System.
    const ANIMAL_DIR_MAP = { up: 'north', down: 'south', left: 'west', right: 'east' };
    const ANIMAL_VARIANTS = {
      cow: 'cow', bull: 'cow', calf: 'cow', ox: 'cow',
      sheep: 'sheep', ram: 'sheep', lamb: 'sheep', sheared_sheep: 'sheep',
      pig: 'pig', piglet: 'pig', boar_domestic: 'pig',
      goat: 'goat', buck_goat: 'goat', kid_goat: 'goat',
      horse: 'horse', draft_horse: 'horse', foal: 'horse', donkey: 'horse', mule: 'horse',
      dog: 'farm_dog',
    };
    for (const [variant, base] of Object.entries(ANIMAL_VARIANTS)) {
      // Idle (2 frames, aus south-Ordner)
      for (const f of [1, 2]) {
        this.load.image(`cha_${variant}_idle_${f}`,
          `/assets/animations/animals/${base}/south/idle_0${f}.png`);
      }
      // Walk pro Richtung — Frame 1 und 3 von 4 (Bewegungs-Extrema)
      for (const [phaserDir, animDir] of Object.entries(ANIMAL_DIR_MAP)) {
        this.load.image(`cha_${variant}_walk_${phaserDir}_1`,
          `/assets/animations/animals/${base}/${animDir}/walk_01.png`);
        this.load.image(`cha_${variant}_walk_${phaserDir}_2`,
          `/assets/animations/animals/${base}/${animDir}/walk_03.png`);
      }
    }
    // Cart-Animationen: roll_NN statt walk_NN, sonst gleiche Struktur.
    // Wir mappen auf `cha_<cart>_walk_*` damit der bestehende Walk-Cycle greift.
    const CART_ANIMS = ['farm_cart_hay', 'handcart_empty', 'horse_cart_single', 'market_wagon_covered'];
    for (const cart of CART_ANIMS) {
      for (const f of [1, 2]) {
        this.load.image(`cha_${cart}_idle_${f}`,
          `/assets/animations/transport/${cart}/south/idle_0${f}.png`);
      }
      for (const [phaserDir, animDir] of Object.entries(ANIMAL_DIR_MAP)) {
        this.load.image(`cha_${cart}_walk_${phaserDir}_1`,
          `/assets/animations/transport/${cart}/${animDir}/roll_01.png`);
        this.load.image(`cha_${cart}_walk_${phaserDir}_2`,
          `/assets/animations/transport/${cart}/${animDir}/roll_03.png`);
      }
    }

    // Walk-Cycle für animierte Monster (49 Kinds × 10 Frames).
    for (const kind of ANIMATED_MONSTER_KINDS) {
      for (const f of [1, 2]) {
        this.load.image(`mob_${kind}_idle_${f}`,
          `/assets/animations/monsters/${kind}/idle_${f}.png`);
        for (const dir of ['down','up','left','right']) {
          this.load.image(`mob_${kind}_walk_${dir}_${f}`,
            `/assets/animations/monsters/${kind}/walk_${dir}_${f}.png`);
        }
      }
    }
    // Spell-Animationen (Welle 40)
    for (const f of [1, 2, 3]) {
      this.load.image(`fx_fireball_${f}`, `/assets/animations/spells/fireball_explosion_${f}.png`);
    }
    this.load.image('fx_fireball_projectile', '/assets/animations/spells/fireball_projectile.png');
    for (const f of [1, 2]) {
      this.load.image(`fx_heal_${f}`, `/assets/animations/spells/heal_pulse_${f}.png`);
      this.load.image(`fx_lightning_${f}`, `/assets/animations/spells/lightning_strike_${f}.png`);
      this.load.image(`fx_magic_circle_${f}`, `/assets/animations/spells/magic_circle_${f}.png`);
    }
    this.load.image('fx_ice_shard', '/assets/animations/spells/ice_shard_projectile.png');
    this.load.image('fx_ice_impact', '/assets/animations/spells/ice_impact.png');
    // Attack-Animationen (Welle 40)
    for (const f of [1, 2, 3]) {
      this.load.image(`fx_sword_slash_${f}`, `/assets/animations/attacks/sword_slash_${f}.png`);
      this.load.image(`fx_axe_swing_${f}`, `/assets/animations/attacks/axe_swing_${f}.png`);
    }
    for (const f of [1, 2]) {
      this.load.image(`fx_mace_hit_${f}`, `/assets/animations/attacks/mace_hit_${f}.png`);
    }
    this.load.image('fx_arrow_projectile', '/assets/animations/attacks/arrow_projectile.png');
    this.load.image('fx_arrow_hit', '/assets/animations/attacks/arrow_hit.png');

    // Character-Sprites — alle Files unter /assets/characters/npcs/.
    // Quelle: assets/characters/character_roster_manifest.json (npc_core-Liste).
    // Enthält Friendly (Handwerker, Dorf-Rollen, Tiere, Kind) UND hostile Humans
    // (bandit, robber, thief). _npcSpriteKey kann via sprite_variant den Default
    // pro Kind überschreiben (z.B. bandit_axe statt bandit).
    for (const n of [
      // Asset-Drop 2026-05-27: vollständiger Roster
      'baker', 'bandit', 'bard', 'blacksmith', 'carpenter',
      'cat', 'child', 'dog', 'farmer', 'farmer_female',
      'fisher', 'guard', 'healer', 'hermit', 'hunter',
      'innkeeper', 'mage', 'merchant', 'miner', 'peasant',
      'priest', 'quest_giver', 'robber', 'scholar', 'scribe',
      'tailor', 'thief', 'village_elder', 'villager', 'woodcutter',
    ]) {
      this.load.image(`npc_${n}`, `/assets/characters/npcs/${n}.png`);
    }
    // NPC-Varianten (Waffen/Rollen) — werden vom backend pro NPC zugewiesen
    for (const v of ['bandit_axe','bandit_bow','bandit_dagger','bandit_spear',
                     'miner_pickaxe',
                     'soldier_axe','soldier_spear','soldier_sword_shield',
                     'watchman_crossbow','watchman_lantern']) {
      this.load.image(`npc_${v}`, `/assets/characters/npcs/variants/${v}.png`);
    }
    // Asset-Drop 2026-05-27b: Nutztiere (Livestock + Poultry).
    // Sprite-Key: animal_<kind>, Pfade aus assets/animals/{livestock,poultry}/.
    for (const a of ['cow','bull','calf','ox','sheep','ram','lamb','sheared_sheep',
                     'pig','piglet','boar_domestic',
                     'goat','buck_goat','kid_goat',
                     'horse','draft_horse','foal','donkey','mule']) {
      this.load.image(`animal_${a}`, `/assets/animals/livestock/${a}.png`);
    }
    for (const a of ['chicken_hen','rooster','chick',
                     'duck','drake','duckling',
                     'goose','gander','gosling']) {
      this.load.image(`animal_${a}`, `/assets/animals/poultry/${a}.png`);
    }
    // Asset-Drop 2026-05-27c: Karawanen-Wagen Static-Fallback-Sprites
    // (Animationen werden weiter unten als `cha_<cart>_*` geladen, dies hier
    // ist nur das statische Inventar-/Default-Sprite.)
    for (const c of ['farm_cart_hay','handcart_empty','horse_cart_single','market_wagon_covered']) {
      this.load.image(`cart_${c}`, `/assets/props/transport/${c}.png`);
    }

    // Items (Waffen, Rüstung, Schmuck, Consumables, Resources)
    for (const [kind, cfg] of Object.entries(ITEM)) {
      this.load.image(cfg.sprite, cfg.path);
    }
    // Pro-Weapon-Variants (Asset-Drop 2026-05-26b): pro Spiel-Kind × Rarity
    // ein Pro-Sprite. Lädt nur die im PRO_WEAPON_MAP referenzierten Files.
    for (const r of PRO_RARITIES) {
      for (const kind of Object.keys(PRO_WEAPON_MAP)) {
        const url = proWeaponPath(kind, r);
        if (url) this.load.image(`weapon_rarity_${r}_${kind}`, url);
      }
    }
    // Pro-Armor-Variants: 5 Slots × 5 Rarities
    for (const r of PRO_RARITIES) {
      for (const slot of PRO_ARMOR_SLOTS) {
        this.load.image(`armor_rarity_${r}_${slot}`, proArmorPath(slot, r));
      }
    }

    // Wand- und Boden-Sprites pro Material (3 × 10 walls + 3 floors)
    for (const material of MATERIALS) {
      for (const variant of ['corner_es', 'corner_ne', 'corner_sw', 'corner_wn',
                             'end_e', 'end_n', 'end_s', 'end_w',
                             'straight_ew', 'straight_ns']) {
        this.load.image(`wall_${material}_${variant}`,
                        `/assets/building/${material}/walls/${variant}.png`);
      }
      this.load.image(`floor_${material}`,
                      `/assets/building/${material}/floor.png`);
    }
    // Fence-Varianten (gleiches Mask-System wie Walls)
    for (const variant of ['corner_es', 'corner_ne', 'corner_sw', 'corner_wn',
                           'end_e', 'end_n', 'end_s', 'end_w',
                           'straight_ew', 'straight_ns']) {
      this.load.image(`fence_${variant}`,
                      `/assets/props/settlement/fence_${variant}.png`);
    }
    // Garden-Gates (open/closed × ew/ns)
    for (const dir of ['ew', 'ns']) {
      for (const state of ['open', 'closed']) {
        this.load.image(`garden_gate_${dir}_${state}`,
                        `/assets/props/settlement/garden_gate_${dir}_${state}.png`);
      }
    }
    // Türen + Treppen
    for (const door of ['door_wood', 'door_wood_open',
                        'door_iron', 'door_iron_open',
                        'door_stone', 'door_stone_open',
                        'door_reinforced']) {
      this.load.image(door, `/assets/buildings/${door}.png`);
    }
    for (const stair of ['stairs_wood_up','stairs_wood_down',
                         'stairs_stone_up','stairs_stone_down']) {
      this.load.image(stair, `/assets/buildings/${stair}.png`);
    }
    // Wetter-Frames Pro-Set (Asset-Drop 2026-05-26d): 16-Frame loopable
    // fullscreen overlays in 768×512, designed für camera-space stretch.
    // Frame-Filenames: rain_light_overlay_01..16.png. Key-Format: pw_<name>_NN.
    const PRO_WEATHER = [
      'rain_light','rain_medium','rain_heavy','rain_downpour',
      'snow_light','snow_medium','snow_heavy','snow_blizzard',
      'fog_light','fog_dense',
      'swamp_mist','jungle_humidity','desert_heat_haze',
      'storm_cell',
    ];
    for (const name of PRO_WEATHER) {
      for (let f = 1; f <= 16; f++) {
        const ff = String(f).padStart(2, '0');
        this.load.image(`pw_${name}_${ff}`,
          `/assets/animations/professional/weather_overlays/${name}_overlay/${name}_overlay_${ff}.png`);
      }
    }
    // Welle 50 — World-Polish-Effekte: 22 transparente Spritesheets 192×192
    // (siehe assets/animations/professional/world_polish/manifest.json)
    for (const a of WORLD_POLISH_ANIMS) {
      this.load.spritesheet(
        `wp_${a.key}`,
        `/assets/animations/professional/world_polish/${a.category}/${a.key}/${a.key}_sheet.png`,
        { frameWidth: 192, frameHeight: 192 }
      );
    }
    // Welle world-detail-p2 (Asset-Drop 2026-05-27): Animal-Animations
    // 24 animals × 2 sheets (walk + idle) = 48 Spritesheets. Frame-Größen
    // variieren pro Tier (64×64 für sheep/goat/pig, 96×96 für cow/horse/farm_dog).
    for (const a of WORLD_DETAIL_P2_ANIMAL_ANIMS) {
      this.load.spritesheet(
        `animal_${a.animal}_${a.direction}_walk`,
        a.walk_sheet,
        { frameWidth: a.walk_fw, frameHeight: a.walk_fh }
      );
      this.load.spritesheet(
        `animal_${a.animal}_${a.direction}_idle`,
        a.idle_sheet,
        { frameWidth: a.idle_fw, frameHeight: a.idle_fh }
      );
    }
    // Welle world-detail-p2: Transport-Animations
    // 16 vehicles × 2 sheets (roll + idle) = 32 Spritesheets. Frame-Größen
    // 128×128 (handcart/farm_cart) bzw. 160×160 (horse_cart/market_wagon).
    for (const t of WORLD_DETAIL_P2_TRANSPORT_ANIMS) {
      this.load.spritesheet(
        `transport_${t.vehicle}_${t.direction}_roll`,
        t.roll_sheet,
        { frameWidth: t.roll_fw, frameHeight: t.roll_fh }
      );
      this.load.spritesheet(
        `transport_${t.vehicle}_${t.direction}_idle`,
        t.idle_sheet,
        { frameWidth: t.idle_fw, frameHeight: t.idle_fh }
      );
    }
    // Welle 51 — Settlement-Schilder (icons_64 für Game-View, 1 Tile = 64px)
    for (const [slug] of SIGN_VARIANTS) {
      this.load.image(
        `sign_${slug}`,
        `/assets/props/settlement/signs/professional/icons_64/${slug}_sign.png`
      );
    }
    this.load.on('loaderror', (file) => {
      console.debug('Asset noch nicht da:', file.src);
    });
  }

  create() {
    // Welle 50: World-Polish-Animations registrieren (idempotent über Scene-Reloads)
    for (const a of WORLD_POLISH_ANIMS) {
      const key = `wp_${a.key}`;
      if (this.anims.exists(key)) continue;
      if (!this.textures.exists(key)) continue;  // Sheet wurde nicht geladen
      this.anims.create({
        key,
        frames: this.anims.generateFrameNumbers(key, { start: 0, end: a.frames - 1 }),
        frameRate: a.fps,
        repeat: a.looping ? -1 : 0,
      });
    }
    // Welle world-detail-p2: Animal-Animations registrieren (48 anims)
    // walk = -1 (loop), idle = -1 (loop). Beide @ 8 fps.
    for (const a of WORLD_DETAIL_P2_ANIMAL_ANIMS) {
      const walkKey = `animal_${a.animal}_${a.direction}_walk`;
      if (!this.anims.exists(walkKey) && this.textures.exists(walkKey)) {
        this.anims.create({
          key: walkKey,
          frames: this.anims.generateFrameNumbers(walkKey, { start: 0, end: a.walk_frames - 1 }),
          frameRate: 8,
          repeat: -1,
        });
      }
      const idleKey = `animal_${a.animal}_${a.direction}_idle`;
      if (!this.anims.exists(idleKey) && this.textures.exists(idleKey)) {
        this.anims.create({
          key: idleKey,
          frames: this.anims.generateFrameNumbers(idleKey, { start: 0, end: a.idle_frames - 1 }),
          frameRate: 8,
          repeat: -1,
        });
      }
    }
    // Welle world-detail-p2: Transport-Animations registrieren (32 anims)
    for (const t of WORLD_DETAIL_P2_TRANSPORT_ANIMS) {
      const rollKey = `transport_${t.vehicle}_${t.direction}_roll`;
      if (!this.anims.exists(rollKey) && this.textures.exists(rollKey)) {
        this.anims.create({
          key: rollKey,
          frames: this.anims.generateFrameNumbers(rollKey, { start: 0, end: t.roll_frames - 1 }),
          frameRate: 8,
          repeat: -1,
        });
      }
      const idleKey = `transport_${t.vehicle}_${t.direction}_idle`;
      if (!this.anims.exists(idleKey) && this.textures.exists(idleKey)) {
        this.anims.create({
          key: idleKey,
          frames: this.anims.generateFrameNumbers(idleKey, { start: 0, end: t.idle_frames - 1 }),
          frameRate: 8,
          repeat: -1,
        });
      }
    }
    // Welle 50: Ambient leaf_rustle — alle 7s ein zufälliges Wald-Tile in Sicht
    // (Forest=3, Jungle=6) bekommt einen kurzen Rascheleffekt. Subtil, kein Loop.
    this.time.addEvent({
      delay: 7000, loop: true,
      callback: () => {
        if (!this.anims.exists('wp_leaf_rustle')) return;
        const tries = 6;
        for (let i = 0; i < tries; i++) {
          const dx = Math.floor(Math.random() * 16) - 8;
          const dy = Math.floor(Math.random() * 12) - 6;
          const tx = this.myTileX + dx;
          const ty = this.myTileY + dy;
          const tid = this.tileAt(tx, ty);
          if (tid === 3 || tid === 6) {  // forest or jungle
            const cx = tx * TILE_SIZE + TILE_SIZE / 2;
            const cy = ty * TILE_SIZE + TILE_SIZE / 2;
            this.playOverlayAnim('leaf_rustle', cx, cy,
                                 { scale: 0.7, depth: 2.2, alpha: 0.5, once: true });
            break;
          }
        }
      },
    });

    this.wasd = this.input.keyboard.addKeys({
      up:    Phaser.Input.Keyboard.KeyCodes.W,
      down:  Phaser.Input.Keyboard.KeyCodes.S,
      left:  Phaser.Input.Keyboard.KeyCodes.A,
      right: Phaser.Input.Keyboard.KeyCodes.D,
    });
    this.cursors = this.input.keyboard.createCursorKeys();

    // Build-Mode-Toggle (deaktiviert wenn Dialog offen)
    this.input.keyboard.on('keydown-B', () => { if (!this.activeDialog) this.toggleBuildMode(); });
    // R im Build-Mode: rotiert das Preview/Place um 90° (0 → 90 → 180 → 270 → 0)
    this.input.keyboard.on('keydown-R', () => {
      if (this.activeDialog || !this.buildMode) return;
      this.placeRotation = ((this.placeRotation || 0) + 90) % 360;
      this._refreshPlaceGhost();
      this._refreshRotationLabel();
    });
    // Tasten 1-9: Build-Mode → Struktur; sonst → Hotbar-Slot aktivieren (Welle 34)
    const NUM_KEYS = ['ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE'];
    const BUILD_KINDS = ['wall','floor','campfire','marker','chest','workbench','furnace','anvil','bed'];
    NUM_KEYS.forEach((k, i) => {
      this.input.keyboard.on('keydown-' + k, () => {
        if (this.activeDialog) return;
        if (this.buildMode) this.selectStructure(BUILD_KINDS[i]);
        else this.activateHotbarSlot(i);
      });
    });
    this.input.keyboard.on('keydown-ZERO',  () => {
      if (this.activeDialog) return;
      if (this.buildMode) this.selectStructure('well');
    });
    this.input.keyboard.on('keydown-M',     () => { if (!this.activeDialog) this.rotateMaterial(); });
    this.input.keyboard.on('keydown-I',     () => { if (!this.activeDialog) this.toggleInventory(); });
    this.input.keyboard.on('keydown-K',     () => { if (!this.activeDialog) this.toggleSkills(); });
    this.input.keyboard.on('keydown-R',     () => { if (!this.activeDialog && !this.buildMode) this.toggleResearch(); });
    this.input.keyboard.on('keydown-Q',     () => { if (!this.activeDialog) this.toggleQuests(); });
    this.input.keyboard.on('keydown-T',     () => { if (!this.activeDialog) this.toggleTalents(); });
    this.input.keyboard.on('keydown-F',     () => { if (!this.activeDialog && !this.buildMode) this.toggleFactions(); });
    this.input.keyboard.on('keydown-C',     () => { if (!this.activeDialog) this.toggleAttributes(); });

    // Click-Handler für Bauen/Abreißen / NPC-Talk
    this.input.mouse.disableContextMenu();
    // Multi-Touch: Phaser hat default 2 Pointer; für Joystick+Tap+Button gleichzeitig brauchen wir mehr
    this.input.addPointer(3);  // ergibt total 5 Pointer
    this.input.on('pointerdown', (pointer) => this.onPointerDown(pointer));
    this.input.on('pointermove', (pointer) => this.onPointerMove(pointer));
    this.input.on('pointerup',   (pointer) => this.onPointerUp(pointer));

    // Dialog-UI-Buttons
    document.getElementById('dialog-close').addEventListener('click', () => this.closeDialog());
    document.getElementById('dialog-send').addEventListener('click', () => this.sendDialog());
    document.getElementById('dialog-quest-btn').addEventListener('click', () => {
      if (this.activeDialog) this.acceptQuestFromNPC(this.activeDialog.npc_id);
    });
    document.getElementById('dialog-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); this.sendDialog(); }
      else if (e.key === 'Escape') { e.preventDefault(); this.closeDialog(); }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.activeDialog) this.closeDialog();
      else if (e.key === 'Escape' && this.signInspectOpen) this.closeSignInspect();
      else if (e.key === 'Escape' && this.activeChest) this.closeChest();
      else if (e.key === 'Escape' && this.activeCrafting) this.closeCrafting();
      else if (e.key === 'Escape' && this.activeTrade) this.closeTrade();
      else if (e.key === 'Escape' && this.skillsOpen) this.toggleSkills();
      else if (e.key === 'Escape' && this.researchOpen) this.toggleResearch();
      else if (e.key === 'Escape' && this.questsOpen) this.toggleQuests();
      else if (e.key === 'Escape' && this.talentsOpen) this.toggleTalents();
      else if (e.key === 'Escape' && this.factionsOpen) this.toggleFactions();
      else if (e.key === 'Escape' && this.attributesOpen) this.toggleAttributes();
      else if (e.key === 'Escape' && this.inventoryOpen) this.toggleInventory();
      else if (e.key.toLowerCase() === 'i' && this.inventoryOpen) this.toggleInventory();
      else if (e.key.toLowerCase() === 'k' && this.skillsOpen) this.toggleSkills();
      else if (e.key.toLowerCase() === 'r' && this.researchOpen) this.toggleResearch();
      else if (e.key.toLowerCase() === 'q' && this.questsOpen) this.toggleQuests();
      else if (e.key.toLowerCase() === 't' && this.talentsOpen) this.toggleTalents();
      else if (e.key.toLowerCase() === 'f' && this.factionsOpen) this.toggleFactions();
      else if (e.key.toLowerCase() === 'c' && this.attributesOpen) this.toggleAttributes();
    });
    // Welle 51 — Sign-Inspect schließen (X, Esc, Klick außerhalb)
    document.getElementById('sign-inspect-close').addEventListener('click', () => this.closeSignInspect());
    document.getElementById('sign-inspect-overlay').addEventListener('click', (ev) => {
      if (ev.target.id === 'sign-inspect-overlay' && this.signInspectOpen) this.closeSignInspect();
    });
    document.getElementById('inventory-close').addEventListener('click', () => this.toggleInventory());
    // Tap außerhalb der Inventar-Box schließt es (wichtig auf Mobile, wo der
    // kleine X-Button leicht verfehlt wird)
    document.getElementById('inventory-overlay').addEventListener('click', (ev) => {
      if (ev.target.id === 'inventory-overlay' && this.inventoryOpen) this.toggleInventory();
    });
    document.getElementById('hand-craft-btn').addEventListener('click', () => {
      // Inventar zu, dann Hand-Crafting öffnen
      if (this.inventoryOpen) this.toggleInventory();
      this.ws.send(JSON.stringify({ type: 'open_hand_crafting' }));
    });
    document.getElementById('chest-close').addEventListener('click', () => this.closeChest());
    document.getElementById('crafting-close').addEventListener('click', () => this.closeCrafting());
    document.getElementById('trade-close').addEventListener('click', () => this.closeTrade());
    document.getElementById('skills-close').addEventListener('click', () => this.toggleSkills());
    document.getElementById('research-close').addEventListener('click', () => this.toggleResearch());
    document.getElementById('quests-close').addEventListener('click', () => this.toggleQuests());
    document.getElementById('talents-close').addEventListener('click', () => this.toggleTalents());
    document.getElementById('factions-close').addEventListener('click', () => this.toggleFactions());
    document.getElementById('attributes-close').addEventListener('click', () => this.toggleAttributes());

    // Pinned-Tooltip: ESC oder Click-outside schließt
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.unpinItemTooltip();
    });
    const closeOnOutside = (e) => {
      const tt = document.getElementById('item-tooltip');
      if (!tt || !tt.classList.contains('pinned')) return;
      // Schutz: gerade frisch gepinnt? Dann ignoriere — sonst schließt der
      // synthetic-click direkt nach contextmenu/long-press das Menü sofort wieder.
      const pinnedAt = parseInt(tt.dataset.pinnedAt || '0', 10);
      if (Date.now() - pinnedAt < 300) return;
      // touchend: e.target ist evtl. das gerade berührte Element, aber bei
      // mehreren Touches use changedTouches[0].target
      let target = e.target;
      if (e.type === 'touchend' && e.changedTouches && e.changedTouches[0]) {
        const t = e.changedTouches[0];
        target = document.elementFromPoint(t.clientX, t.clientY) || target;
      }
      if (!tt.contains(target)) this.unpinItemTooltip();
    };
    document.addEventListener('click', closeOnOutside);
    document.addEventListener('touchend', closeOnOutside, { passive: true });

    this.connectWS();
  }

  toggleBuildMode() {
    this.buildMode = !this.buildMode;
    document.getElementById('build-bar').style.display = this.buildMode ? 'block' : 'none';
    // Welle 51: Body-Klasse → Hotbar (CSS) wird im Build-Mode ausgeblendet
    document.body.classList.toggle('build-mode-active', this.buildMode);
    if (!this.buildMode) {
      if (this.hoverGfx) this.hoverGfx.clear();
      if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
      this.placeRotation = 0;
    }
    if (this.buildMode) this._populatePaletteOnce();
  }

  _populatePaletteOnce() {
    const tabs = document.getElementById('build-bar-tabs');
    if (tabs.children.length > 0) return;
    // Tabs rendern
    for (const cat of BUILD_CATEGORIES) {
      const tab = document.createElement('button');
      tab.className = 'bb-tab';
      tab.dataset.cat = cat.id;
      tab.innerHTML = `<span>${cat.icon}</span> ${cat.label}`;
      tab.addEventListener('click', () => this._selectBuildCategory(cat.id));
      tabs.appendChild(tab);
    }
    // Material-Select-Handler
    const matSel = document.getElementById('build-material-select');
    matSel.value = this.selectedMaterial;
    matSel.addEventListener('change', () => {
      this.selectedMaterial = matSel.value;
      // Ghost-Sprite mit neuem Material refreshen
      if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
    });
    // Initial-Kategorie aus selectedStruct ableiten (falls in einer ist)
    const startCat = (BUILD_CATEGORIES.find(c => _allTypesInCat(c).includes(this.selectedStruct))
                      || BUILD_CATEGORIES[0]).id;
    this._selectBuildCategory(startCat);
    this._refreshRotationLabel();
  }

  _selectBuildCategory(catId) {
    this._currentBuildCat = catId;
    const cat = BUILD_CATEGORIES.find(c => c.id === catId);
    if (!cat) return;
    document.querySelectorAll('#build-bar-tabs .bb-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.cat === catId));
    // Welle 51: Subtabs rendern wenn die Kategorie welche hat
    const subTabsEl = document.getElementById('build-bar-subtabs');
    subTabsEl.innerHTML = '';
    if (cat.subcategories && cat.subcategories.length > 0) {
      subTabsEl.classList.add('active');
      for (const sub of cat.subcategories) {
        const stab = document.createElement('button');
        stab.className = 'bb-subtab';
        stab.dataset.sub = sub.id;
        stab.innerHTML = `<span>${sub.icon}</span> ${sub.label}`;
        stab.addEventListener('click', () => this._selectBuildSubcategory(sub.id));
        subTabsEl.appendChild(stab);
      }
      // Falls aktuelle Auswahl in einer Unterkategorie liegt, diese aktivieren;
      // sonst erste Unterkategorie aktivieren
      const currentSub = cat.subcategories.find(s => s.types?.includes(this.selectedStruct));
      const targetSub = currentSub || cat.subcategories[0];
      this._selectBuildSubcategory(targetSub.id);
    } else {
      subTabsEl.classList.remove('active');
      this._currentBuildSub = null;
      this._renderPaletteForTypes(cat.types || []);
    }
  }

  _selectBuildSubcategory(subId) {
    const cat = BUILD_CATEGORIES.find(c => c.id === this._currentBuildCat);
    if (!cat || !cat.subcategories) return;
    const sub = cat.subcategories.find(s => s.id === subId);
    if (!sub) return;
    this._currentBuildSub = subId;
    document.querySelectorAll('#build-bar-subtabs .bb-subtab').forEach(t =>
      t.classList.toggle('active', t.dataset.sub === subId));
    this._renderPaletteForTypes(sub.types || []);
  }

  _renderPaletteForTypes(types) {
    const palette = document.getElementById('build-palette');
    palette.innerHTML = '';
    for (const type of types) {
      const cfg = STRUCTURE[type];
      if (!cfg || cfg.notBuildable || NATURAL_STRUCTURE_TYPES.has(type)) continue;
      const btn = document.createElement('button');
      btn.className = 'palette-btn';
      btn.dataset.type = type;
      btn.title = cfg.name + (cfg.key ? ` (Taste ${cfg.key})` : '');
      // Welle 51: für Schilder das tatsächliche Sign-PNG zeigen statt Emoji
      let iconHtml;
      if (type.startsWith('sign_')) {
        const slug = type.slice(5);
        iconHtml = `<img class="palette-img" src="/assets/props/settlement/signs/professional/icons_64/${slug}_sign.png" alt="">`;
      } else {
        iconHtml = `<span class="palette-icon">${cfg.icon || '•'}</span>`;
      }
      btn.innerHTML =
        iconHtml +
        `<span class="palette-label">${cfg.name.replace(/^🪧 /, '')}</span>` +
        (cfg.key ? `<span class="palette-key">${cfg.key}</span>` : '');
      btn.addEventListener('click', () => this.selectStructure(type));
      palette.appendChild(btn);
    }
    // Wenn die aktuelle Auswahl nicht in dieser Liste ist, picke die erste baubare
    if (!types.includes(this.selectedStruct) && types.length > 0) {
      const first = types.find(t => STRUCTURE[t] && !STRUCTURE[t].notBuildable
                                    && !NATURAL_STRUCTURE_TYPES.has(t));
      if (first) this.selectStructure(first);
    } else {
      // markiere aktiv
      this.selectStructure(this.selectedStruct);
    }
  }

  selectStructure(type) {
    if (!this.buildMode) return;
    if (!STRUCTURE[type]) return;
    this.selectedStruct = type;
    const sel = document.getElementById('build-selected');
    if (sel) sel.textContent = STRUCTURE[type].name;
    document.querySelectorAll('#build-palette .palette-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.type === type)
    );
    // Wenn Struktur in einer anderen Kategorie/Unterkategorie liegt → Tab wechseln
    if (this._currentBuildCat) {
      const curCat = BUILD_CATEGORIES.find(c => c.id === this._currentBuildCat);
      const inCurCatTypes = curCat?.types?.includes(type);
      const inCurSub = curCat?.subcategories?.find(s => s.id === this._currentBuildSub)?.types?.includes(type);
      if (!inCurCatTypes && !inCurSub) {
        // Finde die Kategorie, die diesen Typ enthält (flach oder via Unterkategorie)
        const newCat = BUILD_CATEGORIES.find(c => _allTypesInCat(c).includes(type));
        if (newCat) this._selectBuildCategory(newCat.id);
      }
    }
    // Ghost-Sprite mit neuem Type refreshen
    if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
  }

  _applyAdaptiveZoom() {
    if (!this.cameras || !this.cameras.main) return;
    const minDim = Math.min(window.innerWidth, window.innerHeight);
    // Ziel: ~11 Tiles auf der schmalen Achse sichtbar. Mobile-Portrait würde
    // sonst nur 6 Tiles zeigen (zu wenig Überblick).
    const desiredTilesVisible = 11;
    let zoom = minDim / (TILE_SIZE * desiredTilesVisible);
    zoom = Math.max(0.45, Math.min(1.0, zoom));   // Clamp [0.45 .. 1.0]
    this.cameras.main.setZoom(zoom);
  }

  _refreshRotationLabel() {
    const el = document.getElementById('build-rotation-label');
    if (el) el.textContent = `${this.placeRotation || 0}°`;
  }

  rotateMaterial() {
    if (!this.buildMode) return;
    const idx = MATERIALS.indexOf(this.selectedMaterial);
    this.selectedMaterial = MATERIALS[(idx + 1) % MATERIALS.length];
    const sel = document.getElementById('build-material-select');
    if (sel) sel.value = this.selectedMaterial;
    if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
  }

  onPointerDown(pointer) {
    if (!this.mySprite) return;
    const wp = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
    const tx = Math.floor(wp.x / TILE_SIZE);
    const ty = Math.floor(wp.y / TILE_SIZE);

    // Welle 17: Pending Wasser-Aktion intercepted den nächsten Click
    if (this.pendingWaterAction) {
      const pa = this.pendingWaterAction;
      this.pendingWaterAction = null;
      this.ws.send(JSON.stringify({ ...pa, x: tx, y: ty }));
      return;
    }

    if (this.buildMode) {
      // Maus: rechte Taste = remove. Touch: Long-Press (500ms) = remove.
      if (pointer.rightButtonDown()) {
        this.ws.send(JSON.stringify({ type: 'remove_structure', x: tx, y: ty }));
        return;
      }
      if (pointer.wasTouch) {
        // Tap-Action erst auf Pointer-Up entscheiden (Long-Press vs Tap)
        if (this._longPress) clearTimeout(this._longPress.timer);
        this._longPress = {
          pid: pointer.id,
          x: pointer.x, y: pointer.y,
          tx, ty,
          fired: false,
          timer: setTimeout(() => {
            this._longPress.fired = true;
            this.ws.send(JSON.stringify({ type: 'remove_structure', x: tx, y: ty }));
            this.showEvent('🗑️ entfernt');
          }, 500),
        };
        return;
      }
      // Maus-Tap im Build-Mode → place
      this.ws.send(JSON.stringify({
        type: 'place_structure',
        x: tx, y: ty,
        structure_type: this.selectedStruct,
        material: this.selectedMaterial,
        rotation: this.placeRotation || 0,
      }));
      return;
    }

    // Nicht im Build-Mode: zuerst Item-Pickup prüfen
    const itemSprite = this._findGroundItemAt(tx, ty);
    if (itemSprite) {
      const dist = Math.abs(tx - this.myTileX) + Math.abs(ty - this.myTileY);
      if (dist <= 1) {
        this.ws.send(JSON.stringify({ type: 'pick_item', item_id: itemSprite._itemId }));
      } else {
        this.showEvent('🤚 Zu weit weg zum Aufheben');
      }
      return;
    }

    // Nicht im Build-Mode: NPC angeklickt?
    const npc = this.findNPCAt(tx, ty);
    if (npc) {
      const kind = npc.npc.kind;
      const isCreature = CREATURE_KINDS.has(kind);
      const dist = Math.abs(npc.tileX - this.myTileX) + Math.abs(npc.tileY - this.myTileY);
      if (isCreature) {
        // Welle 33: Waffen-Range nutzen
        const reach = this.currentWeaponRange();
        if (dist <= reach) {
          this.attackNPC(npc.npc.id);
        } else {
          this.showEvent(`⚔️ Zu weit weg (Reichweite ${reach})`);
        }
      } else if (kind === 'merchant') {
        if (dist <= 2) {
          this.ws.send(JSON.stringify({type: 'open_trade', npc_id: npc.npc.id}));
        } else {
          this.showEvent('🪙 Komm näher zum Händler');
        }
      } else {
        this.openDialog(npc);
      }
      return;
    }
    // Klick auf Struktur (Bed/Well/Chest/Workbench/etc.) → Interaktion
    const s = this.structures[`${tx},${ty}`];
    if (s) {
      const dist = Math.abs(tx - this.myTileX) + Math.abs(ty - this.myTileY);
      // Welle 25: HP-System Click-Routing.
      // - Wenn Hammer equipped UND Struktur beschädigt → repair
      // - Wenn Combat-Struktur ohne Use-Effekt → attack (Range via Waffe)
      // - Wenn interaktive Struktur → use (close range)
      // - Wenn Tür → toggle
      const isUsable = USABLE_STRUCTURE_TYPES.has(s.type);
      const isDoor = s.type.startsWith('door_') || s.type.startsWith('garden_gate_');
      const isCombatStruct = COMBAT_STRUCTURE_TYPES.has(s.type);
      const damaged = (s.durability != null && s.max_durability != null
                       && s.durability < s.max_durability);
      const hasHammer = !!(this.inventory || []).find(
        it => it.equipped_slot === 'tool' && it.kind === 'hammer'
      );
      const isMineForUpgrade = (s.owner === MY_ID);
      // Repair-Mode: Hammer + beschädigt → reparieren (höchste Priorität)
      if (hasHammer && damaged && isCombatStruct) {
        if (dist > 1) { this.showEvent('🤚 Zu weit weg zum Reparieren'); return; }
        this.ws.send(JSON.stringify({ type: 'repair_structure', x: tx, y: ty }));
        return;
      }
      // Welle 25: Upgrade-Mode — Hammer + eigene heile Wand + nicht-top-Material
      if (hasHammer && isCombatStruct && isMineForUpgrade && !damaged
          && s.material && s.material !== 'stone') {
        if (dist > 1) { this.showEvent('🤚 Zu weit weg zum Aufwerten'); return; }
        this.ws.send(JSON.stringify({ type: 'upgrade_structure', x: tx, y: ty }));
        return;
      }
      // Türen togglen
      if (isDoor) {
        if (dist > 1) { this.showEvent('🤚 Zu weit weg'); return; }
        this.ws.send(JSON.stringify({ type: 'toggle_door', x: tx, y: ty }));
        return;
      }
      // Attack: combat-fähig + nicht-usable + (nicht eigene Struktur ODER beschädigt)
      // Eigene volle Strukturen anklicken macht nichts (Frust-vermeidung).
      const isMine = (s.owner === MY_ID);
      if (isCombatStruct && !isUsable && (!isMine || damaged)) {
        const reach = this.currentWeaponRange();
        if (dist > reach) {
          this.showEvent(`⚔️ Zu weit weg (Reichweite ${reach})`);
          return;
        }
        this.ws.send(JSON.stringify({ type: 'attack_structure', x: tx, y: ty }));
        return;
      }
      // Usable (Bed/Well/Chest/Workbench/...) — normaler Interakt
      if (dist > 1) { this.showEvent('🤚 Zu weit weg'); return; }
      this.ws.send(JSON.stringify({ type: 'use_structure', x: tx, y: ty }));
      return;
    }
    // Welle 17: Click auf Wasser-Tile in Reichweite → trinken
    const tileId = this.tileAt(tx, ty);
    if (tileId === 0 /* WATER */) {
      const dist = Math.abs(tx - this.myTileX) + Math.abs(ty - this.myTileY);
      if (dist <= 1) {
        this.ws.send(JSON.stringify({ type: 'drink_water_tile', x: tx, y: ty }));
      } else {
        this.showEvent('💧 Komm näher ans Wasser');
      }
    }
  }

  attackNPC(npcId) {
    this.ws.send(JSON.stringify({ type: 'attack_npc', npc_id: npcId }));
  }

  // Welle 33: Reichweite der aktuell ausgerüsteten Waffe
  // Welle 34: Hotbar
  _loadHotbar() {
    try {
      const raw = localStorage.getItem('liege_hotbar');
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr) && arr.length === 9) return arr;
      }
    } catch (e) {}
    return new Array(9).fill(null);   // null oder item_kind
  }
  _saveHotbar() {
    try { localStorage.setItem('liege_hotbar', JSON.stringify(this.hotbar)); } catch (e) {}
  }
  assignToHotbar(slotIndex, itemKind) {
    if (slotIndex < 0 || slotIndex >= 9) return;
    this.hotbar[slotIndex] = itemKind || null;
    this._saveHotbar();
    this.refreshHotbar();
  }

  // — Drag-and-Drop Helpers ——————————————————————————————————————————————————
  _dndAttach(el, opts) {
    // opts: { dragData? () => object|null, accept? (data) => bool, onDrop (data) }
    if (opts.dragData) {
      el.draggable = true;
      el.addEventListener('dragstart', (ev) => {
        const data = opts.dragData();
        if (!data) { ev.preventDefault(); return; }
        ev.dataTransfer.setData('application/json', JSON.stringify(data));
        ev.dataTransfer.effectAllowed = 'move';
      });
    }
    if (opts.onDrop) {
      el.addEventListener('dragover', (ev) => {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = 'move';
        el.classList.add('drag-over');
      });
      el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
      el.addEventListener('drop', (ev) => {
        ev.preventDefault();
        el.classList.remove('drag-over');
        try {
          const raw = ev.dataTransfer.getData('application/json');
          if (!raw) return;
          const data = JSON.parse(raw);
          if (opts.accept && !opts.accept(data)) return;
          opts.onDrop(data);
        } catch (e) { /* invalid payload */ }
      });
    }
  }

  // Zentrale Drop-Logik: src = {from, slot|item_id, kind}, dst = {to, slot|item_id}
  _handleDndDrop(src, dst) {
    // Hotbar → Hotbar: swap
    if (src.from === 'hotbar' && dst.to === 'hotbar') {
      if (src.slot === dst.slot) return;
      const tmp = this.hotbar[src.slot];
      this.hotbar[src.slot] = this.hotbar[dst.slot];
      this.hotbar[dst.slot] = tmp;
      this._saveHotbar();
      this.refreshHotbar();
      return;
    }
    // Inventory → Hotbar: zuweisen
    if (src.from === 'inventory' && dst.to === 'hotbar') {
      this.assignToHotbar(dst.slot, src.kind);
      return;
    }
    // Hotbar → Inventory: Slot leeren
    if (src.from === 'hotbar' && dst.to === 'inventory') {
      this.assignToHotbar(src.slot, null);
      return;
    }
    // Inventory → Inventory: keine Reorder-Persistenz vorgesehen
  }
  refreshHotbar() {
    const root = document.getElementById('hotbar');
    if (!root) return;
    root.innerHTML = '';
    // Count items per kind
    const counts = {};
    const firstId = {};
    for (const it of (this.inventory || [])) {
      if (it.equipped_slot) continue;
      counts[it.kind] = (counts[it.kind] || 0) + 1;
      if (!firstId[it.kind]) firstId[it.kind] = it.id;
    }
    for (let i = 0; i < 9; i++) {
      const slot = document.createElement('div');
      slot.className = 'hotbar-slot';
      if (i === this.activeHotbar) slot.classList.add('active');
      const key = document.createElement('div');
      key.className = 'hotbar-key';
      key.textContent = (i + 1);
      slot.appendChild(key);
      const kind = this.hotbar[i];
      // Drag-and-Drop: jeder Hotbar-Slot ist Drop-Target; besetzte sind auch
      // Drag-Source. Inventar→Hotbar = zuweisen, Hotbar→Hotbar = swap.
      this._dndAttach(slot, {
        dragData: kind ? () => ({ from: 'hotbar', slot: i, kind }) : null,
        onDrop:   (src) => this._handleDndDrop(src, { to: 'hotbar', slot: i }),
      });
      if (kind && ITEM[kind]) {
        const cfg = ITEM[kind];
        const cnt = counts[kind] || 0;
        // Equipped-Markierung
        const isEquipped = !!(this.inventory || []).find(
          it => it.kind === kind && it.equipped_slot
        );
        if (isEquipped) slot.style.boxShadow = '0 0 8px rgba(120,200,80,0.7)';
        const img = document.createElement('img');
        // Welle 23: Sprite passend zur tatsächlichen Item-Quality wählen,
        // damit Hotbar und Inventar konsistent sind. Equipped hat Vorrang,
        // sonst das Item mit höchster Quality dieses Kinds.
        const QR = { rough: 0, normal: 1, fine: 2, masterwork: 3, legendary: 4 };
        const equippedItem = (this.inventory || []).find(it => it.kind === kind && it.equipped_slot);
        let displayItem = equippedItem;
        if (!displayItem) {
          const stack = (this.inventory || []).filter(it => it.kind === kind && !it.equipped_slot);
          if (stack.length) {
            stack.sort((a, b) => (QR[b.quality || 'normal'] || 0) - (QR[a.quality || 'normal'] || 0));
            displayItem = stack[0];
          }
        }
        img.src = itemAssetPath(displayItem || kind);
        if (cnt === 0 && !isEquipped) slot.classList.add('hotbar-empty');
        slot.appendChild(img);
        if (cnt > 1) {
          const c = document.createElement('div');
          c.className = 'hotbar-count';
          c.textContent = cnt;
          slot.appendChild(c);
        } else if (isEquipped && cfg.slot) {
          // Show equipped indicator
          const e = document.createElement('div');
          e.className = 'hotbar-count';
          e.textContent = '✓';
          e.style.color = '#80f080';
          slot.appendChild(e);
        }
        // Tooltip
        const item = (this.inventory || []).find(it => it.kind === kind && !it.equipped_slot);
        if (item) {
          slot.addEventListener('mouseenter', (ev) => this.showItemTooltip(item, ev));
          slot.addEventListener('mousemove',  (ev) => this.showItemTooltip(item, ev));
          slot.addEventListener('mouseleave', () => this.hideItemTooltip());
        }
        slot.addEventListener('click', () => this.activateHotbarSlot(i));
        slot.addEventListener('contextmenu', (ev) => {
          ev.preventDefault(); this.assignToHotbar(i, null);
        });
      } else {
        slot.addEventListener('click', () => {
          this.showEvent('Slot leer — Rechtsklick im Inventar zum Belegen');
        });
      }
      root.appendChild(slot);
    }
  }
  activateHotbarSlot(idx) {
    if (idx < 0 || idx >= 9) return;
    this.activeHotbar = idx;
    const kind = this.hotbar[idx];
    if (!kind) { this.refreshHotbar(); return; }
    const cfg = ITEM[kind] || {};
    // Toggle für equippable: schon equipped → ablegen; sonst anlegen
    if (cfg.slot) {
      const equipped = (this.inventory || []).find(
        it => it.kind === kind && it.equipped_slot
      );
      if (equipped) {
        this.unequipItem(equipped.id);
      } else {
        const free = (this.inventory || []).find(
          it => it.kind === kind && !it.equipped_slot
        );
        if (free) this.equipItem(free.id);
        else this.showEvent('Nichts mehr von ' + (cfg.name || kind));
      }
      this.refreshHotbar();
      return;
    }
    // Verbrauchsgegenstand / Nahrung / Magie
    const item = (this.inventory || []).find(it => it.kind === kind && !it.equipped_slot);
    if (!item) {
      this.showEvent('Nichts mehr von ' + (cfg.name || kind));
      this.refreshHotbar();
      return;
    }
    if (cfg.category === 'consumable' || cfg.category === 'food') {
      this.useItem(item.id);
    } else if (cfg.category === 'magic') {
      this.castSpell(item.id);
    }
    this.refreshHotbar();
  }

  // Welle 35: Item-Stats-Tooltip
  showItemTooltip(item, ev) {
    const tt = document.getElementById('item-tooltip');
    if (!tt) return;
    // Pinned-Tooltip nicht überschreiben (sonst löscht hover-tooltip die Action-Buttons)
    if (tt.classList.contains('pinned')) return;
    const cfg = ITEM[item.kind] || { name: item.kind };
    const Q_COLOR = { rough: '#888e91', normal: '#4fab58', fine: '#4581e0',
                       masterwork: '#e7c44b', legendary: '#ee772b' };
    const qIcon = QUALITY_ICONS[item.quality] || '';
    const name = item.unique_name || cfg.name;
    const qcol = Q_COLOR[effectiveQuality(item)] || '#ccc';
    let html = `<div class="tt-name" style="color:${qcol}">${qIcon} ${name}</div>`;
    if (item.quality) html += `<div class="tt-quality">Qualität: ${QUALITY_DE[item.quality] || item.quality}</div>`;
    if (item.category) html += `<div class="tt-quality">Kategorie: ${CATEGORY_DE[item.category] || item.category}</div>`;
    // Beschreibung
    const desc = ITEM_DESC[item.kind];
    if (desc) html += `<div class="tt-desc">${desc}</div>`;
    // Compare-Mode: wenn das gehoverte Item nicht equipped ist, aber equip-bar,
    // ziehe den aktuell ausgerüsteten Vergleichs-Slot heran.
    let equippedForCompare = null;
    if (cfg.slot && !item.equipped_slot) {
      equippedForCompare = findEquippedInSlot(this.inventory || [], cfg.slot);
      if (equippedForCompare && equippedForCompare.id === item.id) equippedForCompare = null;
    }
    html += buildItemStatsHtml(item, { equipped: equippedForCompare });
    // Category-spezifische Hinweise (keine WEAPON/ARMOR-Stats)
    const catHints = [];
    if (!WEAPON_STATS[item.kind] && !ARMOR_STATS[item.kind]) {
      if (item.category === 'food')       catHints.push(`🍖 Sättigung beim Essen`);
      else if (item.category === 'consumable') catHints.push(`💊 Verbrauchsgegenstand`);
      else if (item.category === 'tool')       catHints.push(`🔧 Werkzeug — Skill-Bonus beim Equippen`);
      else if (item.category === 'resource')   catHints.push(`📦 Rohstoff`);
    }
    // Stack-Limit anzeigen
    const STACK_LIMITS = { resource:500, food:150, consumable:25, magic:25 };
    if (STACK_LIMITS[item.category]) {
      catHints.push(`📚 Stapel: ${item.quantity || 1} / ${STACK_LIMITS[item.category]}`);
    }
    if (catHints.length > 0) {
      html += `<div class="tt-stats">${catHints.map(s => `<div>${s}</div>`).join('')}</div>`;
    }
    if (equippedForCompare) {
      const eqName = equippedForCompare.unique_name || (ITEM[equippedForCompare.kind]?.name) || equippedForCompare.kind;
      html += `<div class="tt-compare-hint" style="font-size:10px;color:#a09478;margin-top:4px">vs aktuell: ${eqName}</div>`;
    }
    // Flavor
    if (item.flavor) {
      html += `<div class="tt-flavor">"${item.flavor}"</div>`;
    }
    tt.innerHTML = html;
    tt.classList.add('active');
    // Position oberhalb/rechts vom Mauszeiger
    const x = (ev && ev.clientX) ? ev.clientX + 14 : 100;
    const y = (ev && ev.clientY) ? ev.clientY - 8 : 100;
    tt.style.left = Math.min(window.innerWidth - 300, x) + 'px';
    tt.style.top  = Math.max(10, y) + 'px';
  }

  hideItemTooltip() {
    const tt = document.getElementById('item-tooltip');
    if (!tt) return;
    // Pinned-Tooltip nicht auf hover-out schließen
    if (tt.classList.contains('pinned')) return;
    tt.classList.remove('active');
  }

  // Persistenter Rechtsklick-Tooltip mit Aktions-Buttons
  pinItemTooltip(item, ev) {
    const tt = document.getElementById('item-tooltip');
    if (!tt) return;
    const cfg = ITEM[item.kind] || {};
    // Stats wie im normalen Tooltip aufbauen
    const Q_COLOR = { rough: '#888e91', normal: '#4fab58', fine: '#4581e0',
                       masterwork: '#e7c44b', legendary: '#ee772b' };
    const qIcon = QUALITY_ICONS[item.quality] || '';
    const name = item.unique_name || cfg.name || item.kind;
    const qcol = Q_COLOR[effectiveQuality(item)] || '#ccc';
    let html = `<div class="tt-close">×</div>`;
    html += `<div class="tt-name" style="color:${qcol}">${qIcon} ${name}</div>`;
    if (item.quality) html += `<div class="tt-quality">Qualität: ${QUALITY_DE[item.quality] || item.quality}</div>`;
    if (item.category) html += `<div class="tt-quality">Kategorie: ${CATEGORY_DE[item.category] || item.category}</div>`;
    const desc = ITEM_DESC[item.kind];
    if (desc) html += `<div class="tt-desc">${desc}</div>`;
    // Compare gegen aktuell ausgerüstetes Item im selben Slot (nur wenn dieses
    // Item nicht selbst equipped ist)
    let equippedForCompare = null;
    if (cfg.slot && !item.equipped_slot) {
      equippedForCompare = findEquippedInSlot(this.inventory || [], cfg.slot);
      if (equippedForCompare && equippedForCompare.id === item.id) equippedForCompare = null;
    }
    html += buildItemStatsHtml(item, { equipped: equippedForCompare });
    if (equippedForCompare) {
      const eqName = equippedForCompare.unique_name || (ITEM[equippedForCompare.kind]?.name) || equippedForCompare.kind;
      html += `<div class="tt-compare-hint" style="font-size:10px;color:#a09478;margin-top:4px">vs aktuell: ${eqName}</div>`;
    }
    if (item.flavor) html += `<div class="tt-flavor">"${item.flavor}"</div>`;
    // Aktions-Buttons in HTML
    let actionsHtml = '<div class="tt-actions">';
    if (cfg.slot) {
      actionsHtml += `<button data-act="equip">${item.equipped_slot ? '↓ Ablegen' : '↑ Anlegen'}</button>`;
      // Welle 23 — Dual-Wield: 1H-Waffe kann auch in Off-Hand
      if (cfg.category === 'weapon' && !item.equipped_slot) {
        const ws = WEAPON_STATS[item.kind];
        if (ws && !ws.two_h) {
          actionsHtml += `<button data-act="equip_offhand">⚔ Off-Hand</button>`;
        }
      }
    }
    if (cfg.category === 'consumable' || cfg.category === 'food') {
      actionsHtml += `<button data-act="use">${cfg.category === 'food' ? '🍖 Essen' : '🍷 Benutzen'}</button>`;
    }
    if (cfg.category === 'magic') {
      const knows = (this.learnedSpells || []).includes(item.kind);
      actionsHtml += `<button data-act="magic">${knows ? '✨ Wirken' : '📖 Lernen'}</button>`;
    }
    actionsHtml += `<button data-act="hotbar">📌 Hotbar</button>`;
    // Stack-Aktionen: Teilen nur wenn quantity>1, Stapeln nur für stackable Kategorien
    const STACKABLE = new Set(['resource','food','consumable','magic']);
    if ((item.quantity || 1) > 1) {
      actionsHtml += `<button data-act="split">✂️ Teilen</button>`;
    }
    if (STACKABLE.has(cfg.category)) {
      actionsHtml += `<button data-act="merge">🧱 Stapeln</button>`;
    }
    if (!item.equipped_slot) actionsHtml += `<button data-act="drop">🗑️ Wegwerfen</button>`;
    // Welle 17: Wasser-Container-Aktionen
    if (isWaterContainer(item.kind)) {
      const charges = item.charges || 0;
      const cap = containerCapacity(item.kind);
      if (charges > 0) {
        actionsHtml += `<button data-act="drink_container">💧 Trinken (${charges}/${cap})</button>`;
        actionsHtml += `<button data-act="water_plant">🌱 Pflanze gießen</button>`;
      }
      if (charges < cap) {
        actionsHtml += `<button data-act="fill_container">🪣 An Quelle füllen</button>`;
      }
    }
    actionsHtml += '</div>';
    html += actionsHtml;
    tt.innerHTML = html;
    tt.classList.add('active', 'pinned');
    tt.dataset.pinnedAt = String(Date.now());
    // Position
    const x = (ev && ev.clientX) ? ev.clientX + 14 : 100;
    const y = (ev && ev.clientY) ? ev.clientY - 8 : 100;
    tt.style.left = Math.min(window.innerWidth - 300, x) + 'px';
    tt.style.top  = Math.max(10, y) + 'px';
    // Event-Bindings
    tt.querySelector('.tt-close')?.addEventListener('click', () => this.unpinItemTooltip());
    tt.querySelectorAll('.tt-actions button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const act = btn.getAttribute('data-act');
        if (act === 'equip') {
          if (item.equipped_slot) this.unequipItem(item.id);
          else this.equipItem(item.id);
        } else if (act === 'equip_offhand') {
          // Welle 23 — Dual-Wield in Off-Hand
          this.ws.send(JSON.stringify({
            type: 'equip_item', item_id: item.id, to_slot: 'shield',
          }));
          this.unpinItemTooltip();
        } else if (act === 'use') {
          this.useItem(item.id);
        } else if (act === 'magic') {
          const knows = (this.learnedSpells || []).includes(item.kind);
          if (knows) this.castSpell(item.id);
          else this.ws.send(JSON.stringify({ type: 'learn_spell', item_id: item.id }));
        } else if (act === 'hotbar') {
          let s = this.hotbar.findIndex(x => !x);
          if (s < 0) s = 0;
          this.assignToHotbar(s, item.kind);
          this.showEvent(`📌 → Slot ${s+1}`);
        } else if (act === 'drop') {
          this.dropItem(item.id);
        } else if (act === 'drink_container') {
          this.ws.send(JSON.stringify({ type: 'drink_container', item_id: item.id }));
        } else if (act === 'fill_container') {
          this.pendingWaterAction = { type: 'fill_container', item_id: item.id };
          this.showEvent('🪣 Click jetzt auf einen Brunnen oder Wasser-Tile');
          this.unpinItemTooltip();
        } else if (act === 'water_plant') {
          this.pendingWaterAction = { type: 'water_plant', item_id: item.id };
          this.showEvent('🌱 Click jetzt auf einen Acker');
          this.unpinItemTooltip();
        } else if (act === 'split') {
          const maxQ = (item.quantity || 1) - 1;
          const ans = window.prompt(`Wie viele aus dem Stapel teilen? (1–${maxQ})`, String(Math.max(1, Math.floor(maxQ / 2))));
          const n = parseInt(ans || '0', 10);
          if (n >= 1 && n <= maxQ) {
            this.ws.send(JSON.stringify({ type: 'split_stack', item_id: item.id, amount: n }));
          }
        } else if (act === 'merge') {
          this.ws.send(JSON.stringify({ type: 'merge_stacks', kind: item.kind, quality: item.quality || 'normal' }));
        }
        this.unpinItemTooltip();
      });
    });
  }

  unpinItemTooltip() {
    const tt = document.getElementById('item-tooltip');
    if (!tt) return;
    tt.classList.remove('pinned', 'active');
  }

  currentWeaponRange() {
    if (!this.inventory) return 1;
    const w = this.inventory.find(it => it.equipped_slot === 'weapon');
    if (!w) return 1;
    return (WEAPON_RANGE[w.kind] || 1);
  }

  _computeCombatStats() {
    // Frontend-Schätzung der Combat-Stats — spiegelt grob backend/combat.calc_player_damage.
    // Min = ohne Crit, Max = mit Crit. Nicht 100% akkurat (kein RNG/Berserker),
    // aber gut genug für ein Char-Sheet-Display.
    const w = this.inventory.find(it => it.equipped_slot === 'weapon');
    const wKind = w ? w.kind : null;
    const wStats = wKind ? WEAPON_STATS[wKind] : null;
    const qm = _qualityMult(w ? w.quality : 'normal');
    const combatLvl = (this.mySkills && this.mySkills.combat && this.mySkills.combat.level) || 0;

    // Base damage formel (mirror von backend/combat.py calc_player_damage)
    const baseRaw = (wStats ? wStats.dmg : 4);
    const skillAdd = Math.floor(combatLvl / 4);
    const playerBaseHalf = 2;     // PLAYER_BASE_DAMAGE/2 = 4/2
    const baseTotal = baseRaw + skillAdd + playerBaseHalf;
    let dmgNormal = baseTotal * qm;
    // Affix-Damage-Bonus (damage_pct)
    let damagePctBonus = 0;
    let fireBonus = 0, iceBonus = 0, lightningBonus = 0;
    for (const af of (w?.affixes || [])) {
      const st = af.stats || {};
      if (st.damage_pct) damagePctBonus += st.damage_pct;
      if (st.fire_damage) fireBonus += st.fire_damage;
      if (st.ice_damage) iceBonus += st.ice_damage;
      if (st.lightning_damage) lightningBonus += st.lightning_damage;
    }
    dmgNormal *= (1 + damagePctBonus / 100);
    const elemFlat = fireBonus + iceBonus + lightningBonus;
    dmgNormal += elemFlat;

    // Crit
    const baseCrit = wStats ? wStats.crit : 0.05;
    const critChance = baseCrit + combatLvl * 0.005;
    const critMult = wStats ? (wStats.crit_mult || 1.5) : 1.5;
    const dmgCrit = dmgNormal * critMult;

    // Defense aus equipped Armor
    let totalDef = 0;
    for (const it of this.inventory) {
      if (!it.equipped_slot) continue;
      const a = ARMOR_STATS[it.kind];
      if (a) {
        totalDef += Math.round(a.defense * _qualityMult(it.quality));
      }
      // Affix defense_flat
      for (const af of (it.affixes || [])) {
        const st = af.stats || {};
        if (st.defense_flat) totalDef += st.defense_flat;
      }
    }
    const drPct = totalDef > 0 ? Math.round(100 * totalDef / (totalDef + 100)) : 0;

    return {
      weaponName: wKind ? (ITEM[wKind]?.name || wKind) : 'Faust',
      dmgMin:     Math.round(dmgNormal),
      dmgMax:     Math.round(dmgCrit),
      range:      wStats ? wStats.range : 1,
      speed:      wStats ? wStats.speed : 1.0,
      critPct:    Math.round(critChance * 100),
      defense:    totalDef,
      drPct,
    };
  }

  findNPCAt(x, y) {
    for (const id of Object.keys(this.npcs)) {
      const n = this.npcs[id];
      if (n.tileX === x && n.tileY === y) return n;
    }
    return null;
  }

  openDialog(npcEntry) {
    const npc = npcEntry.npc;
    this.activeDialog = { npc_id: npc.id, waiting: false };
    document.getElementById('dialog-npc-name').textContent = npc.name;
    document.getElementById('dialog-npc-kind').textContent = ' — ' + (NPC_SPRITE[npc.kind]?.label || npc.kind);
    document.getElementById('dialog-npc-bg').textContent = npc.backstory;
    document.getElementById('dialog-history').innerHTML = '';
    document.getElementById('dialog-input').value = '';
    document.getElementById('dialog-overlay').classList.add('active');
    // Welle 23: Quest-Offers/Turnins anzeigen (frisch abrufen)
    this._refreshDialogQuestSection(npc.id);
    this._queryNPCQuests(npc.id);
    // Quest-Button nur bei NPC-Kinds die Quests vergeben können
    const QUEST_GIVING_KINDS = new Set([
      'quest_giver','merchant','blacksmith','mage','scholar',
      'guard','soldier','healer',
    ]);
    const canGive = QUEST_GIVING_KINDS.has(npc.kind);
    const qb = document.getElementById('dialog-quest-btn');
    if (qb) qb.style.display = canGive ? 'inline-block' : 'none';
    // Phaser-Keyboard komplett ausschalten + alle Captures freigeben,
    // damit Tasten ans Input-Feld durchkommen
    this.input.keyboard.enabled = false;
    this.input.keyboard.clearCaptures();
    // Focus erst im nächsten Tick — manche Browser klauen Focus zurück
    setTimeout(() => {
      const el = document.getElementById('dialog-input');
      el.focus();
      el.click();  // safety: bei manchen Browsern hilft das mit dem Cursor
    }, 30);
  }

  closeDialog() {
    this.activeDialog = null;
    document.getElementById('dialog-overlay').classList.remove('active');
    // Welle 23: Reset für Quest-Board-Fallthrough
    const inputRow = document.getElementById('dialog-input-row');
    if (inputRow) inputRow.style.display = '';
    this.input.keyboard.enabled = true;
  }

  // ─── Welle 23: Character-Creation ──────────────────────────────────────
  _showCharacterCreation() {
    const overlay = document.getElementById('char-create-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    this._ccState = {
      preset: null,
      alloc: {},
      pool: 20,
      display_name: '',
      name_available: false,
    };
    // Welle 23 — Preset-Defaults: 10 vorvergebene Punkte pro Klasse
    // (Wanderer = frei, alle 20 selbst verteilen).
    const PRESET_DEFAULTS = {
      ember_mage:    { intelligenz: 4, energie: 3, krit_schaden: 2, weisheit: 1 },
      iron_delver:   { stärke: 4, ausdauer: 3, verteidigung: 2, geschick: 1 },
      knife_runner:  { geschick: 4, schleichen: 3, krit_rate: 2, ausweichen: 1 },
      shieldbearer:  { verteidigung: 4, ausdauer: 3, stärke: 2, charisma: 1 },
      wild_ranger:   { geschick: 4, ausweichen: 3, stärke: 2, krit_rate: 1 },
      wanderer_cloak: {},   // frei
    };
    const PRESETS = [
      { id: 'wanderer_cloak', name: 'Wanderer',   desc: 'Frei verteilbar — keine Default-Punkte. Für eigene Builds.', tags: '⚖ Frei / 20 Punkte' },
      { id: 'iron_delver',    name: 'Eisengräber', desc: 'Kräftiger Bergmann. Stark, ausdauernd, gut im Mining.',     tags: '⛏ Stärke / Ausdauer' },
      { id: 'shieldbearer',   name: 'Schildträger',desc: 'Tank-Klasse mit hoher Verteidigung. Beschützer.',           tags: '🛡 Verteidigung / Ausdauer' },
      { id: 'wild_ranger',    name: 'Wildläufer', desc: 'Jäger mit Bogen. Flink, geschickt, gute Ausweichquote.',     tags: '🏹 Geschick / Ausweichen' },
      { id: 'knife_runner',   name: 'Klingengänger', desc: 'Leichtfüßiger Dieb. Schleichen, kritische Treffer.',      tags: '🗡 Geschick / Schleichen' },
      { id: 'ember_mage',     name: 'Glutmagier',  desc: 'Feuermagier. Intelligenz und Energie für Magieschaden.',     tags: '🔮 Intelligenz / Energie' },
    ];
    // Welle 23 — Attribut-Beschreibungen (Tooltips). Erklären was der Stat
    // im Spiel beeinflusst (siehe backend/attributes.py SKILL_CONTRIBUTIONS).
    const ATTRS = [
      { key: 'stärke',       label: 'Stärke',         icon: '💪',
        tip: 'Erhöht Nahkampf-Schaden, Tragkraft, Bergbau- und Holzfäller-Ertrag.' },
      { key: 'ausdauer',     label: 'Ausdauer',       icon: '🛡️',
        tip: 'Erhöht Stamina-Pool, Bau-Geschwindigkeit und Marsch-Reichweite.' },
      { key: 'energie',      label: 'Energie (Mana)', icon: '✨',
        tip: 'Vergrößert den Mana-Pool und verstärkt Magie-Schaden.' },
      { key: 'intelligenz',  label: 'Intelligenz',    icon: '📖',
        tip: 'Beeinflusst Magie-Effizienz, Crafting-Qualität und Heilkunde.' },
      { key: 'weisheit',     label: 'Weisheit',       icon: '🌿',
        tip: 'Bessere NPC-Dialoge, stärkere Heilung, Lebensraub bei Magie.' },
      { key: 'geschick',     label: 'Geschick',       icon: '🤚',
        tip: 'Boni für Dolche, Wurfwaffen und Finesse-Klassen. Crafting-Qualität.' },
      { key: 'ausweichen',   label: 'Ausweichen',     icon: '💨',
        tip: 'Chance, einem feindlichen Treffer komplett auszuweichen (kein Schaden).' },
      { key: 'verteidigung', label: 'Verteidigung',   icon: '🛡',
        tip: 'Reduziert eingehenden physischen Schaden zusätzlich zur Rüstung.' },
      { key: 'charisma',     label: 'Charisma',       icon: '💬',
        tip: 'Bessere Handelspreise, NPC-Stimmung, Quest-Belohnungen, soziale Optionen.' },
      { key: 'krit_rate',    label: 'Krit-Rate',      icon: '🎯',
        tip: 'Erhöht die Chance auf kritische Treffer (Schaden × Krit-Multiplikator).' },
      { key: 'krit_schaden', label: 'Krit-Schaden',   icon: '💥',
        tip: 'Erhöht den Multiplikator bei einem kritischen Treffer (1.5× → 2.5×).' },
      { key: 'schleichen',   label: 'Schleichen',     icon: '🌑',
        tip: 'Reduziert die Aggro-Reichweite von Feinden. Hinterhalt-Schaden.' },
    ];

    // Preset-Karten rendern
    const presetEl = document.getElementById('char-create-presets');
    presetEl.innerHTML = '';
    for (const p of PRESETS) {
      const card = document.createElement('div');
      card.style.cssText = 'background:#2a2018;border:2px solid #5a4828;border-radius:5px;padding:6px;cursor:pointer;text-align:center;transition:border-color 0.15s';
      card.dataset.preset = p.id;
      card.innerHTML = `
        <img src="/assets/characters/player_presets/${p.id}.png" style="width:80px;height:80px;image-rendering:pixelated;background:#1a1410;border-radius:3px"><br>
        <div style="font-weight:bold;font-size:12px;color:#ffd060;margin-top:3px">${p.name}</div>
        <div style="font-size:9px;color:#a08e72;margin-top:2px">${p.tags}</div>
        <div style="font-size:9px;color:#807060;margin-top:3px;line-height:1.3">${p.desc}</div>`;
      card.addEventListener('click', () => {
        this._ccState.preset = p.id;
        // Welle 23: Default-Punkte aus Preset-Map vorbelegen
        const defaults = PRESET_DEFAULTS[p.id] || {};
        this._ccState.alloc = { ...defaults };
        const used = Object.values(defaults).reduce((a, b) => a + b, 0);
        this._ccState.pool = 20 - used;
        presetEl.querySelectorAll('div[data-preset]').forEach(d =>
          d.style.borderColor = d.dataset.preset === p.id ? '#ffd060' : '#5a4828');
        this._updateCharCreateUI();
      });
      presetEl.appendChild(card);
    }

    // Attribute-Spalten rendern
    const attrsEl = document.getElementById('char-create-attrs');
    attrsEl.innerHTML = '';
    for (const a of ATTRS) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:6px;background:#221a14;border-radius:3px;padding:4px 8px;position:relative';
      // Welle 23: Info-Bubble per native title-Attribut + Hilfs-Icon
      row.innerHTML = `
        <span style="width:18px">${a.icon}</span>
        <span style="flex:1;font-size:11px" title="${a.tip}">${a.label}</span>
        <span class="cc-info" title="${a.tip}" style="cursor:help;color:#7a8aa0;font-size:11px;border:1px solid #5a6a78;border-radius:50%;width:14px;height:14px;display:inline-flex;align-items:center;justify-content:center">?</span>
        <button data-act="minus" data-attr="${a.key}" style="width:24px;height:22px;background:#3a2818;border:1px solid #807060;color:#c8b878;cursor:pointer;border-radius:2px">−</button>
        <span data-val="${a.key}" style="display:inline-block;min-width:24px;text-align:center;color:#ffd060;font-weight:bold">0</span>
        <button data-act="plus" data-attr="${a.key}" style="width:24px;height:22px;background:#3a2818;border:1px solid #807060;color:#c8b878;cursor:pointer;border-radius:2px">+</button>`;
      row.querySelector('[data-act="minus"]').addEventListener('click', () => {
        const cur = this._ccState.alloc[a.key] || 0;
        if (cur > 0) {
          this._ccState.alloc[a.key] = cur - 1;
          this._ccState.pool += 1;
          this._updateCharCreateUI();
        }
      });
      row.querySelector('[data-act="plus"]').addEventListener('click', () => {
        const cur = this._ccState.alloc[a.key] || 0;
        if (cur < 5 && this._ccState.pool > 0) {
          this._ccState.alloc[a.key] = cur + 1;
          this._ccState.pool -= 1;
          this._updateCharCreateUI();
        }
      });
      attrsEl.appendChild(row);
    }
    this._updateCharCreateUI();

    document.getElementById('char-create-reset').onclick = () => {
      // Welle 23: Reset stellt Preset-Defaults wieder her (Wanderer = leer)
      const defaults = PRESET_DEFAULTS[this._ccState.preset] || {};
      this._ccState.alloc = { ...defaults };
      const used = Object.values(defaults).reduce((a, b) => a + b, 0);
      this._ccState.pool = 20 - used;
      this._updateCharCreateUI();
    };
    document.getElementById('char-create-confirm').onclick = () => {
      // Welle 23: konkretes Feedback warum disabled
      if (!this._ccState.display_name || !this._ccState.name_available) {
        this.showEvent('⚠ Wähle einen gültigen, freien Spielernamen.');
        return;
      }
      if (!this._ccState.preset) {
        this.showEvent('⚠ Wähle einen Charakter.');
        return;
      }
      if (this._ccState.pool > 0) {
        this.showEvent(`⚠ Verteile noch ${this._ccState.pool} Stat-Punkte.`);
        return;
      }
      this.ws.send(JSON.stringify({
        type: 'character_create',
        preset: this._ccState.preset,
        display_name: this._ccState.display_name,
        allocated: this._ccState.alloc,
      }));
    };
    // Welle 23 — Name-Input mit Live-Check (300ms debounce)
    const nameEl = document.getElementById('char-create-name');
    const statusEl = document.getElementById('char-create-name-status');
    let nameDebounce = null;
    nameEl.addEventListener('input', () => {
      const v = nameEl.value.trim();
      this._ccState.display_name = v;
      this._ccState.name_available = false;
      if (statusEl) { statusEl.textContent = '…'; statusEl.style.color = '#807060'; }
      if (nameDebounce) clearTimeout(nameDebounce);
      if (!v || v.length < 3) {
        if (statusEl) { statusEl.textContent = 'min 3 Zeichen'; statusEl.style.color = '#e85040'; }
        this._updateCharCreateUI();
        return;
      }
      nameDebounce = setTimeout(() => {
        this.ws.send(JSON.stringify({type: 'character_check_name', display_name: v}));
      }, 300);
    });
    if (statusEl) statusEl.textContent = '';
  }

  _updateCharCreateUI() {
    if (!this._ccState) return;
    document.getElementById('char-create-pool').textContent =
      `${this._ccState.pool} Punkte ĂĽbrig`;
    for (const [k, v] of Object.entries(this._ccState.alloc)) {
      const el = document.querySelector(`[data-val="${k}"]`);
      if (el) el.textContent = v;
    }
    // Reset others to 0
    document.querySelectorAll('[data-val]').forEach(el => {
      const k = el.dataset.val;
      if (!(k in this._ccState.alloc)) el.textContent = '0';
    });
    // Confirm-Button aktiv wenn Name OK + preset gewählt + alle 20 Punkte verteilt
    const btn = document.getElementById('char-create-confirm');
    btn.disabled = !this._ccState.preset
      || this._ccState.pool > 0
      || !this._ccState.name_available;
    btn.style.opacity = btn.disabled ? '0.5' : '1';
    // Hint im Button-Title was noch fehlt
    const reasons = [];
    if (!this._ccState.name_available) reasons.push('Name fehlt/vergeben');
    if (!this._ccState.preset) reasons.push('Charakter wählen');
    if (this._ccState.pool > 0) reasons.push(`${this._ccState.pool} Punkte zu verteilen`);
    btn.title = reasons.length ? 'Noch zu tun: ' + reasons.join(', ') : 'Charakter erschaffen';
  }

  _hideCharacterCreation() {
    const overlay = document.getElementById('char-create-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  _refreshDialogQuestSection(npcId) {
    const section = document.getElementById('dialog-quest-section');
    if (!section) return;
    const data = (this._npcQuestData || {})[npcId];
    if (!data || (data.offers.length === 0 && data.turnins.length === 0)) {
      section.style.display = 'none';
      section.innerHTML = '';
      return;
    }
    let html = '';
    // Turn-ins zuerst (wichtiger!)
    if (data.turnins.length > 0) {
      html += `<div style="color:#ffd060;font-weight:bold;margin-bottom:3px">❗ Abzugebende Aufträge:</div>`;
      for (const q of data.turnins) {
        const reward = q.reward || {};
        const rewardText = this._formatQuestReward(reward);
        html += `<div style="margin:2px 0;padding:3px 5px;background:rgba(80,60,20,0.4);border-radius:2px">
          <b>${q.title}</b><br>
          <span style="opacity:0.8;font-size:10px">${q.description}</span><br>
          <span style="color:#9fc890;font-size:10px">Belohnung: ${rewardText}</span><br>
          <button data-act="turnin" data-qid="${q.id}" style="margin-top:3px;background:#5a8a4a;border:1px solid #8fc88f;color:#fff;padding:3px 10px;border-radius:2px;cursor:pointer;font-size:11px">✅ Abgeben</button>
        </div>`;
      }
    }
    // Offers
    if (data.offers.length > 0) {
      html += `<div style="color:#ffe080;font-weight:bold;margin:6px 0 3px">❓ Verfügbare Aufträge:</div>`;
      for (const o of data.offers) {
        const rewardText = this._formatQuestReward(o.reward || {});
        const tierIcon = '★'.repeat(o.tier || 1);
        html += `<div style="margin:2px 0;padding:3px 5px;background:rgba(40,30,15,0.4);border-radius:2px">
          <b>${o.title}</b> <span style="color:#c8a868;font-size:10px">${tierIcon}</span><br>
          <span style="opacity:0.8;font-size:10px">${o.description}</span><br>
          <span style="color:#9fc890;font-size:10px">Belohnung: ${rewardText}</span><br>
          <button data-act="accept" data-tid="${o.template_id}" style="margin-top:3px;background:#5a6a8a;border:1px solid #8fa8c8;color:#fff;padding:3px 10px;border-radius:2px;cursor:pointer;font-size:11px">📜 Annehmen</button>
        </div>`;
      }
    }
    section.style.display = 'block';
    section.innerHTML = html;
    // Bind buttons
    section.querySelectorAll('button[data-act]').forEach(btn => {
      btn.addEventListener('click', () => {
        const act = btn.dataset.act;
        if (act === 'accept') {
          this.ws.send(JSON.stringify({
            type: 'accept_quest_template',
            template_id: btn.dataset.tid,
            npc_id: npcId,
          }));
        } else if (act === 'turnin') {
          this.ws.send(JSON.stringify({
            type: 'quest_turn_in',
            quest_id: parseInt(btn.dataset.qid, 10),
            npc_id: npcId,
          }));
        }
        // Nach Aktion neu laden
        setTimeout(() => this._queryNPCQuests(npcId), 200);
      });
    });
  }

  _formatQuestReward(reward) {
    const parts = [];
    if (reward.gold) parts.push(`${reward.gold} Gold`);
    if (reward.xp) parts.push(`${reward.xp} XP`);
    for (const [k, v] of Object.entries(reward.items || {})) {
      const name = (ITEM[k] && ITEM[k].name) || k;
      parts.push(`${v}× ${name}`);
    }
    for (const [fac, delta] of Object.entries(reward.faction || {})) {
      const sign = delta >= 0 ? '+' : '';
      parts.push(`${sign}${delta} Ruf (${fac})`);
    }
    return parts.join(' · ') || '—';
  }

  appendDialogBubble(role, text, isTyping = false) {
    const list = document.getElementById('dialog-history');
    const div = document.createElement('div');
    div.className = 'bubble ' + role + (isTyping ? ' typing' : '');
    div.textContent = text;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
    return div;
  }

  sendDialog() {
    if (!this.activeDialog || this.activeDialog.waiting) return;
    const input = document.getElementById('dialog-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this.appendDialogBubble('user', text);
    this.activeDialog.typingEl = this.appendDialogBubble('npc', '…', true);
    this.activeDialog.waiting = true;
    this.ws.send(JSON.stringify({
      type: 'talk_to_npc',
      npc_id: this.activeDialog.npc_id,
      message: text,
    }));
  }

  receiveDialogReply(text) {
    if (!this.activeDialog) return;
    if (this.activeDialog.typingEl) {
      this.activeDialog.typingEl.className = 'bubble npc';
      this.activeDialog.typingEl.textContent = text;
      this.activeDialog.typingEl = null;
    } else {
      this.appendDialogBubble('npc', text);
    }
    this.activeDialog.waiting = false;
    document.getElementById('dialog-input').focus();
  }

  onPointerMove(pointer) {
    // Long-Press abbrechen wenn Finger sich zu weit bewegt
    if (this._longPress && this._longPress.pid === pointer.id && !this._longPress.fired) {
      const ddx = pointer.x - this._longPress.x;
      const ddy = pointer.y - this._longPress.y;
      if (Math.hypot(ddx, ddy) > 18) {
        clearTimeout(this._longPress.timer);
        this._longPress = null;
      }
    }
    if (!this.buildMode) return;
    if (!this.hoverGfx) {
      this.hoverGfx = this.add.graphics();
      this.hoverGfx.setDepth(5);
    }
    const wp = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
    const tx = Math.floor(wp.x / TILE_SIZE);
    const ty = Math.floor(wp.y / TILE_SIZE);
    this.hoverGfx.clear();
    this.hoverGfx.lineStyle(2, 0xe8d870, 0.9);
    this.hoverGfx.strokeRect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE);
    this._updatePlaceGhost(tx, ty);
  }

  _spriteKeyForStruct(type, material) {
    // Wand/Floor haben material-spezifische Sprites — sonst fall auf den
    // Default-Sprite-Key aus den STRUCTURE-Definitionen (z.B. 'struct_workbench',
    // 'door_wood', 'fence_straight_ns') zurück.
    if (type === 'wall' && this.textures.exists(`wall_${material}_straight_ns`)) {
      return `wall_${material}_straight_ns`;
    }
    if (type === 'floor' && this.textures.exists(`floor_${material}`)) {
      return `floor_${material}`;
    }
    const cfg = STRUCTURE[type];
    if (cfg && cfg.sprite && this.textures.exists(cfg.sprite)) {
      return cfg.sprite;
    }
    // Last resort: vielleicht ist der Type selbst der Texture-Key (Türen,
    // Garden-Gates haben sprite==type)
    if (this.textures.exists(type)) return type;
    return null;
  }

  _updatePlaceGhost(tx, ty) {
    if (!this.buildMode || !this.selectedStruct) {
      if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
      return;
    }
    const key = this._spriteKeyForStruct(this.selectedStruct, this.selectedMaterial);
    if (!key) {
      if (this.placeGhost) { this.placeGhost.destroy(); this.placeGhost = null; }
      return;
    }
    const cx = tx * TILE_SIZE + TILE_SIZE / 2;
    const cy = ty * TILE_SIZE + TILE_SIZE / 2;
    if (!this.placeGhost || this.placeGhost.texture.key !== key) {
      if (this.placeGhost) this.placeGhost.destroy();
      this.placeGhost = this.add.image(cx, cy, key).setOrigin(0.5);
      this.placeGhost.setDepth(4.5);
      this.placeGhost.setAlpha(0.55);
    } else {
      this.placeGhost.setPosition(cx, cy);
    }
    const structScale = STRUCTURE_DISPLAY_SCALE[this.selectedStruct] || 1.0;
    this.placeGhost.setDisplaySize(TILE_SIZE * structScale, TILE_SIZE * structScale);
    this.placeGhost.setAngle(this.placeRotation || 0);
  }

  _refreshPlaceGhost() {
    if (!this.placeGhost) return;
    this.placeGhost.setAngle(this.placeRotation || 0);
  }

  onPointerUp(pointer) {
    // Long-Press im Build-Mode: wenn nicht gefeuert → war ein Tap → place
    if (this._longPress && this._longPress.pid === pointer.id) {
      clearTimeout(this._longPress.timer);
      if (!this._longPress.fired) {
        const { tx, ty } = this._longPress;
        this.ws.send(JSON.stringify({
          type: 'place_structure',
          x: tx, y: ty,
          structure_type: this.selectedStruct,
          material: this.selectedMaterial,
          rotation: this.placeRotation || 0,
        }));
      }
      this._longPress = null;
    }
  }

  connectWS() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${proto}//${window.location.host}/ws`);
    window.GAME_WS = this.ws;
    const statusEl = document.getElementById('conn-status');

    this.ws.onopen = () => {
      if (statusEl) statusEl.textContent = 'Verbunden';
      this._reconnectAttempt = 0;
    };

    this.ws.onerror = (ev) => {
      console.error('WS error:', ev);
      if (statusEl) statusEl.textContent = '⚠️ Verbindungsfehler';
    };

    this.ws.onclose = (ev) => {
      if (statusEl) statusEl.textContent = '❌ Getrennt – Reconnect …';
      // Auth-Failure (1008) und Policy-Violation: kein endloser Retry-Loop
      if (ev && (ev.code === 1008 || ev.code === 4401)) {
        if (statusEl) statusEl.textContent = '❌ Nicht autorisiert – bitte neu einloggen';
        return;
      }
      this._reconnectAttempt = (this._reconnectAttempt || 0) + 1;
      const delay = Math.min(30000, 500 * Math.pow(2, this._reconnectAttempt - 1));
      setTimeout(() => this.connectWS(), delay);
    };

    this.ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        console.error('Invalid WS message:', e, ev.data);
        return;
      }
      try {
        this.handleMsg(msg);
      } catch (e) {
        console.error('handleMsg crashed on', msg && msg.type, e);
      }
    };
  }

  handleMsg(msg) {
    switch (msg.type) {
      case 'init':
        this.worldData.width = 999999;
        this.worldData.height = 999999;
        // Welle 23: Player-Preset speichern für Sprite-Resolution
        this.myPreset = msg.preset || null;
        // Welle 23: Character-Creation-Flow wenn nötig
        this.needsCharCreation = !!msg.needs_character_creation;
        if (this.needsCharCreation) {
          this._showCharacterCreation();
        }
        // Chunks aus init aufnehmen
        for (const c of (msg.chunks || [])) {
          this.chunks[`${c.cx},${c.cy}`] = c.tiles;
        }
        this.drawWorld();
        this.drawMinimap();
        // Strukturen aus Init laden — Floor und Object getrennt
        this.structures = {};
        this.floors = {};
        for (const s of (msg.structures || [])) {
          const target = (s.layer === 'floor') ? this.floors : this.structures;
          target[`${s.x},${s.y}`] = s;
        }
        this.drawStructures();
        // Chronik mit vergangenen Events füllen
        this.loadInitialEvents(msg.events || []);
        // NPCs in die Welt setzen
        this.loadNPCs(msg.npcs || []);
        // Items am Boden
        this.loadGroundItems(msg.items_ground || []);
        // Inventar
        this.inventory = msg.inventory || [];
        this.refreshInventoryUI();
        this.refreshHotbar();
        // HP / Mana / Hunger / Stamina / Skills
        this.myHp        = msg.hp         ?? 100;
        this.myMaxHp     = msg.max_hp     ?? 100;
        this.myMana      = msg.mana       ?? 50;
        this.myMaxMana   = msg.max_mana   ?? 50;
        this.myHunger    = msg.hunger     ?? 100;
        this.myMaxHunger = msg.max_hunger ?? 100;
        this.myThirst    = msg.thirst     ?? 100;
        this.myMaxThirst = msg.max_thirst ?? 100;
        this.myStamina   = msg.stamina    ?? 100;
        this.myMaxStamina = msg.max_stamina ?? 100;
        this.mySkills    = msg.skills || {};
        this.myBodyParts = msg.body_parts || { legs: 100, arms: 100, torso: 100 };
        // Welle 22: research kommt jetzt als {nodes, pool} statt direkt nodes-dict
        if (msg.research && msg.research.nodes) {
          this.myResearch = msg.research.nodes;
          this.myResearchPool = msg.research.pool || 0;
        } else {
          this.myResearch = msg.research || {};
          this.myResearchPool = 0;
        }
        if (msg.time) this.updateTimeOfDay(msg.time);
        this.myQuests = msg.quests || [];
        this.myTalents = msg.talents || { learned: [], points: 0, tree: {} };
        this.myFactions = msg.factions || [];
        this.myAttributes = msg.attributes || { values: {}, labels: {} };
        // Welle 24: Aktive Disaster-Overlays bei Verbindung anzeigen
        if (Array.isArray(msg.active_disasters)) {
          for (const d of msg.active_disasters) {
            try { this._onDisasterStarted(d.kind, d.metadata || {}); } catch (e) {}
          }
        }
        this.statSheet = msg.stats || null;   // Welle 15: vollständiges Char-Sheet
        this.learnedSpells = msg.learned_spells || [];
        this.refreshHpBar();
        this.refreshManaBar();
        this.refreshNeedsBars();
        this.refreshBodyParts();
        this.refreshSkillsUI();
        this.myTileX = msg.spawn.x;
        this.myTileY = msg.spawn.y;
        this.myPx = msg.spawn.x * TILE_SIZE + TILE_SIZE / 2;
        this.myPy = msg.spawn.y * TILE_SIZE + TILE_SIZE / 2;
        this.mySprite = this.spawnSprite(MY_ID, msg.spawn.x, msg.spawn.y, true);
        this.cameras.main.startFollow(this.mySprite.container, true, 0.15, 0.15);
        // Welle 23: Sprite unsichtbar bis Character-Creation abgeschlossen
        if (this.needsCharCreation && this.mySprite.container) {
          this.mySprite.container.setVisible(false);
        }
        this._applyAdaptiveZoom();
        // Re-apply zoom bei Viewport-Änderungen (Orientation, Resize)
        if (!this._zoomListener) {
          this._zoomListener = () => this._applyAdaptiveZoom();
          window.addEventListener('resize', this._zoomListener);
          window.addEventListener('orientationchange',
            () => setTimeout(this._zoomListener, 200));
        }
        // Keine Camera-Bounds — Welt ist effektiv unendlich (chunked)

        // Bestehende Spieler spawnen
        for (const [id, data] of Object.entries(msg.players)) {
          if (id !== MY_ID) this.spawnOther(id, data.x, data.y);
        }
        this.updatePlayerCount();
        break;

      case 'chat':
        if (window.chatConsole) {
          window.chatConsole.addMessage('player', msg.from, msg.text);
        }
        break;

      case 'player_joined':
        this.spawnOther(msg.player_id, msg.x, msg.y);
        this.updatePlayerCount();
        this.showEvent(`🧙 ${msg.player_id.substr(0,8)} betritt die Welt`);
        break;

      case 'player_moved':
        if (this.otherPlayers[msg.player_id]) {
          const p = this.otherPlayers[msg.player_id];
          const dx = msg.x - p.tileX;
          p.tileX = msg.x;
          p.tileY = msg.y;
          this.movePlayerSmooth(p, msg.x, msg.y, dx);
          this.drawMinimap();
        }
        break;

      case 'player_left':
        if (this.otherPlayers[msg.player_id]) {
          const p = this.otherPlayers[msg.player_id];
          if (p.tween) p.tween.stop();
          p.container.destroy();
          delete this.otherPlayers[msg.player_id];
          this.updatePlayerCount();
        }
        break;

      case 'structure_placed': {
        const s = msg.structure;
        const target = (s.layer === 'floor') ? this.floors : this.structures;
        target[`${s.x},${s.y}`] = s;
        this.addStructureSprite(s);
        break;
      }

      case 'structure_replaced': {
        // Type-Change am gleichen Tile (z.B. Tür auf/zu). Sprite neu zeichnen.
        const s = msg.structure;
        const key = `${s.x},${s.y}`;
        const target = (s.layer === 'floor') ? this.floors : this.structures;
        target[key] = s;
        // Altes Sprite entfernen, neues setzen
        if (this.structSprites[key]) { this.structSprites[key].destroy(); delete this.structSprites[key]; }
        if (this.doorFrameSprites && this.doorFrameSprites[key]) {
          this.doorFrameSprites[key].destroy(); delete this.doorFrameSprites[key];
        }
        this.addStructureSprite(s);
        break;
      }

      case 'structure_removed': {
        const layer = msg.layer || 'object';
        const key = `${msg.x},${msg.y}`;
        if (layer === 'floor') {
          delete this.floors[key];
        } else {
          delete this.structures[key];
        }
        this.removeStructureSprite(msg.x, msg.y, layer);
        // Welle 25: HP-Bar mit aufräumen
        this._removeStructureHpBar(msg.x, msg.y);
        break;
      }

      case 'structure_damaged': {
        // Welle 25: HP-Update + Tint + HP-Bar
        const key = `${msg.x},${msg.y}`;
        const s = this.structures[key] || this.floors[key];
        if (s && msg.durability != null) {
          s.durability = msg.durability;
          if (msg.max_durability != null) s.max_durability = msg.max_durability;
          this._refreshStructureHpVisual(s);
        }
        this.shakeStructure(msg.x, msg.y);
        // Floating-Damage-Number
        if (msg.dmg != null) {
          const px = msg.x * TILE_SIZE + TILE_SIZE / 2;
          const py = msg.y * TILE_SIZE + TILE_SIZE / 2;
          this._floatingDamage(px, py, msg.dmg, { color: '#c0c0c0' });
        }
        break;
      }

      case 'structure_repaired': {
        // Welle 25: durability hoch + Tint/Bar refresh
        const key = `${msg.x},${msg.y}`;
        const s = this.structures[key] || this.floors[key];
        if (s && msg.durability != null) {
          s.durability = msg.durability;
          if (msg.max_durability != null) s.max_durability = msg.max_durability;
          this._refreshStructureHpVisual(s);
        }
        break;
      }

      case 'structure_upgraded': {
        // Welle 25: Material geändert → Sprite neu rendern. Wir entfernen
        // den alten Sprite und addStructureSprite() pickt das neue material-key.
        const key = `${msg.x},${msg.y}`;
        const s = this.structures[key] || this.floors[key];
        if (s) {
          const layer = s.layer || 'object';
          s.material       = msg.material;
          s.durability     = msg.durability;
          s.max_durability = msg.max_durability;
          this._removeStructureHpBar(msg.x, msg.y);
          this.removeStructureSprite(msg.x, msg.y, layer);
          this.addStructureSprite(s, /*refreshNeighbors=*/ true);
          // Kleiner Upgrade-Effekt (gelber Schimmer)
          const cx = msg.x * TILE_SIZE + TILE_SIZE / 2;
          const cy = msg.y * TILE_SIZE + TILE_SIZE / 2;
          this._floatingDamage(cx, cy, '⬆️', { color: '#ffe070' });
        }
        break;
      }

      case 'event':
        this.addEventToChronik(msg.event);
        this.showStoryEvent(msg.event);
        // Welle 21: Map-Marker für Event-Position
        if (msg.event.marker) {
          this._addEventMarker(msg.event.marker);
        }
        break;

      case 'npc_spawned':
        this.spawnNPCSprite(msg.npc);
        this.showEvent(`🌿 ${msg.npc.name} ist in der Welt erschienen`);
        this.drawMinimap();
        break;

      case 'npc_moved':
        if (this.npcs[msg.npc_id]) {
          const n = this.npcs[msg.npc_id];
          const dx = msg.x - n.tileX;
          n.tileX = msg.x;
          n.tileY = msg.y;
          this.movePlayerSmooth(n, msg.x, msg.y, dx);
          this.drawMinimap();
        }
        break;

      case 'npc_reply':
        this.receiveDialogReply(msg.text);
        break;

      case 'item_spawned':
        this.addItemSprite(msg.item);
        break;

      case 'item_picked_up': {
        // Welle 50: Pickup-Pop bevor das Sprite verschwindet, damit es an der
        // Item-Position erscheint und nicht im Nichts.
        const sp = this.itemSprites[msg.item_id];
        if (sp && msg.by === MY_ID) {
          this.playOverlayAnim('item_pickup_pop', sp.x, sp.y, { scale: 0.75, depth: 6 });
        }
        this.removeItemSprite(msg.item_id);
        break;
      }

      case 'weather':
        this.setWeather(msg.phase, msg.intensity);
        break;

      case 'inventory_add': {
        // Upsert: bei Stack-Merge gibt create_for_player die existing-stack-id
        // zurück — wenn die schon im Inventar ist, updaten statt zusätzlich
        // pushen (sonst gibt's doppelte Slots mit identischer id).
        const idx = this.inventory.findIndex(it => it.id === msg.item.id);
        if (idx >= 0) this.inventory[idx] = msg.item;
        else          this.inventory.push(msg.item);
        this.refreshInventoryUI();
        this.showEvent(`🎒 ${msg.item.name} aufgehoben`);
        break;
      }

      case 'inventory_update':
        // Format A: voll {item: {...}} — z.B. equipped_slot Change
        // Format B: schlank {item_id, quantity} — z.B. Stack-Decrement nach Consume / Stack-Merge nach Pickup
        if (msg.item) {
          for (let i = 0; i < this.inventory.length; i++) {
            if (this.inventory[i].id === msg.item.id) {
              this.inventory[i] = msg.item;
            } else if (msg.item.equipped_slot &&
                       this.inventory[i].equipped_slot === msg.item.equipped_slot) {
              this.inventory[i].equipped_slot = null;
            }
          }
        } else if (msg.item_id != null && msg.quantity != null) {
          for (let i = 0; i < this.inventory.length; i++) {
            if (this.inventory[i].id === msg.item_id) {
              this.inventory[i].quantity = msg.quantity;
              break;
            }
          }
        }
        this.refreshInventoryUI();
        break;

      case 'inventory_remove':
        this.inventory = this.inventory.filter(it => it.id !== msg.item_id);
        this.refreshInventoryUI();
        break;

      case 'player_damaged':
        this.myHp = msg.hp;
        this.myMaxHp = msg.max_hp;
        this.refreshHpBar(true);
        this.showEvent(`💢 -${msg.dmg} HP`);
        this.flashScreenDamage();
        if (this.mySprite) {
          this.knockbackSprite(this.mySprite);
          // Welle 18: Floating-Damage-Number über dem Player
          this._floatingDamage(this.myPx, this.myPy, msg.dmg, { color: '#ff4040' });
        }
        break;

      case 'player_respawned':
        this.myHp = msg.hp;
        this.myMaxHp = msg.max_hp;
        this.setLocalPositionFromTile(msg.x, msg.y);
        this.refreshHpBar();
        this.showStoryEvent({ kind: 'natural', title: '💀 Du bist gefallen', body: 'Die Welt setzt dich wieder am Spawn ab.' });
        break;

      case 'player_died':
        // Andere Spieler sehen das nur als Toast
        this.showEvent(`💀 ${msg.player_id} ist gefallen`);
        break;

      case 'npc_damaged':
        if (this.npcs[msg.npc_id]) {
          const n = this.npcs[msg.npc_id];
          n.npc.hp = msg.hp;
          n.npc.max_hp = msg.max_hp;
          this.updateNPCHpBar(msg.npc_id);
          this.flashNPCHit(msg.npc_id);
          // Welle 18: Floating-Damage-Number über dem NPC (gelb = wir schaden)
          if (n.container && msg.dmg != null) {
            this._floatingDamage(n.container.x, n.container.y, msg.dmg,
              { color: msg.by === MY_ID ? '#ffe070' : '#d8c89a' });
          }
        }
        break;

      case 'npc_died':
        if (this.npcs[msg.npc_id]) {
          const n = this.npcs[msg.npc_id];
          if (n.tween) n.tween.stop();
          if (n.speech && n.speech.timer) clearTimeout(n.speech.timer);
          n.container.destroy();
          delete this.npcs[msg.npc_id];
          this.drawMinimap();
        }
        this.showEvent(`☠️ ${msg.name} wurde besiegt`);
        break;

      case 'npc_attacked':
        if (msg.target === MY_ID) {
          // player_damaged kommt eh separat
        }
        break;

      case 'npc_goal':
        // Welle 20: friendly NPC bekommt ein neues Tages-Goal
        if (this.npcs[msg.npc_id]) {
          this.npcs[msg.npc_id]._goal = msg.goal;
          this._updateNPCGoalIcon(msg.npc_id, msg.emoji);
        }
        break;

      case 'npc_speech':
        // Welle 20: NPC-Sprechblase über Kopf für ~6 Sekunden
        {
          const delay = msg.delay_ms || 0;
          if (delay > 0) {
            setTimeout(() => this._showNPCSpeech(msg.npc_id, msg.text), delay);
          } else {
            this._showNPCSpeech(msg.npc_id, msg.text);
          }
        }
        break;

      case 'visual_effect':
        this.showVisualEffect(msg.kind, msg.x, msg.y);
        break;

      case 'player_healed':
        this.myHp = msg.hp;
        this.myMaxHp = msg.max_hp;
        this.refreshHpBar();
        this.showEvent(`✨ +${msg.amount} HP`);
        break;

      case 'player_mana':
        this.myMana = msg.mana;
        this.myMaxMana = msg.max_mana;
        this.refreshManaBar();
        break;

      case 'toast':
        this.showEvent(msg.text);
        break;

      // ─── Welle 24 — Disaster-Effekte ────────────────────────────────────
      case 'disaster_started':
        this._onDisasterStarted(msg.kind, msg);
        break;
      case 'disaster_ended':
        this._onDisasterEnded(msg.kind);
        break;
      case 'earthquake_shake':
        this._onEarthquakeShake(msg.duration_ms || 6000, msg.magnitude || 6);
        break;
      case 'lightning_strike':
        this._onLightningStrike(msg.x, msg.y);
        break;

      case 'chest_open':
        this.openChest(msg.chest_id, msg.items);
        break;

      case 'chest_add':
        if (this.activeChest && this.activeChest.chest_id === msg.chest_id) {
          this.activeChest.items.push(msg.item);
          this.refreshChestUI();
        }
        break;

      case 'chest_remove':
        if (this.activeChest && this.activeChest.chest_id === msg.chest_id) {
          this.activeChest.items = this.activeChest.items.filter(it => it.id !== msg.item_id);
          this.refreshChestUI();
        }
        break;

      case 'crafting_open':
        this.openCrafting(msg.station, msg.recipes);
        break;

      case 'sign_inspect':
        this.openSignInspect(msg.slug);
        break;

      case 'inventory_full_refresh':
        this.inventory = msg.inventory;
        this.refreshInventoryUI();
        if (this.activeChest) this.refreshChestUI();
        if (this.activeCrafting) this.refreshCraftingUI();
        if (this.activeTrade) this.refreshTradeUI();
        break;

      case 'chunks':
        for (const c of msg.chunks) {
          this.chunks[`${c.cx},${c.cy}`] = c.tiles;
          this.drawChunkTiles(c.cx, c.cy);
        }
        this.drawMinimap();
        break;

      case 'player_needs':
        this.myHunger     = msg.hunger;
        this.myMaxHunger  = msg.max_hunger;
        if (msg.thirst != null) this.myThirst = msg.thirst;
        if (msg.max_thirst != null) this.myMaxThirst = msg.max_thirst;
        this.myStamina    = msg.stamina;
        this.myMaxStamina = msg.max_stamina;
        this.refreshNeedsBars();
        break;

      case 'status_effects':
        this.renderStatusEffects(msg.effects || []);
        break;

      case 'time_update':
        this.updateTimeOfDay(msg);
        break;

      case 'dungeon_enter':
        this.enterDungeonMode(msg);
        break;

      case 'dungeon_exit':
        this.exitDungeonMode(msg);
        break;

      case 'factions_update':
        this.myFactions = msg.factions || [];
        if (this.factionsOpen) this.refreshFactionsUI();
        break;

      case 'attributes_update':
        this.myAttributes = { values: msg.values || {}, labels: msg.labels || {} };
        if (this.attributesOpen) this.refreshAttributesUI();
        break;

      case 'attrs_update':
        // Welle 15: vollständiges Stat-Sheet (Attribute + Allokation + Resistances)
        this.statSheet = msg.stats || null;
        if (this.inventoryOpen) this._refreshInventoryStats();
        break;

      case 'spell_learned':
        this.learnedSpells = msg.learned || this.learnedSpells;
        break;

      case 'talent_learned':
      case 'talents_update': {
        this.myTalents.learned = msg.learned || this.myTalents.learned;
        this.myTalents.points  = msg.points  ?? this.myTalents.points;
        this.myTalents.tree    = msg.tree    || this.myTalents.tree;
        if (this.talentsOpen) this.refreshTalentsUI();
        break;
      }

      case 'quests_update':
        this.myQuests = msg.quests || [];
        this.myReputation = msg.reputation || {};
        if (this.questsOpen) this.refreshQuestsUI();
        break;

      case 'character_name_check': {
        // Welle 23: Name-Verfügbarkeits-Feedback
        const statusEl = document.getElementById('char-create-name-status');
        if (this._ccState && this._ccState.display_name === msg.name) {
          this._ccState.name_available = !!msg.available;
        }
        if (statusEl) {
          statusEl.textContent = (msg.available ? '✓ ' : '✗ ') + msg.reason;
          statusEl.style.color = msg.available ? '#9fc890' : '#e85040';
        }
        this._updateCharCreateUI();
        break;
      }

      case 'character_created': {
        // Welle 23: Character-Creation abgeschlossen — Modal schließen + Sprite-Update
        this.myPreset = msg.preset;
        this.needsCharCreation = false;
        this._hideCharacterCreation();
        // Player-Sprite umschalten auf preset + sichtbar machen
        if (this.mySprite) {
          if (this.mySprite.container) this.mySprite.container.setVisible(true);
          if (this.mySprite.body) {
            const key = `preset_${msg.preset}`;
            if (this.textures.exists(key)) {
              this.mySprite.body.setTexture(key);
              this.mySprite.body.setDisplaySize(TILE_SIZE * 0.95, TILE_SIZE * 0.95);
            }
          }
        }
        this.showEvent(`⚔ Charakter erschaffen: ${msg.preset}`);
        break;
      }

      case 'quest_board_open': {
        // Welle 23: Quest-Board zeigt verfügbare Welt-Quests via Quest-Dialog
        const offers = msg.offers || [];
        // Fake NPC-Entry für die Dialog-UI
        const boardId = msg.board_id;
        this.activeDialog = { npc_id: -boardId, waiting: false, isBoard: true };
        document.getElementById('dialog-npc-name').textContent = '📜 Aufgabentafel';
        document.getElementById('dialog-npc-kind').textContent = ' — Königreich';
        document.getElementById('dialog-npc-bg').textContent =
          'Aushänge mit offenen Aufträgen aus der ganzen Region.';
        document.getElementById('dialog-history').innerHTML = '';
        document.getElementById('dialog-overlay').classList.add('active');
        // dialog-input-row + quest-btn ausblenden (kein Talk auf Board)
        const inputRow = document.getElementById('dialog-input-row');
        if (inputRow) inputRow.style.display = 'none';
        const qb = document.getElementById('dialog-quest-btn');
        if (qb) qb.style.display = 'none';
        // Quest-Section direkt füllen mit board-offers
        this._npcQuestData = this._npcQuestData || {};
        this._npcQuestData[-boardId] = { offers, turnins: [] };
        this._refreshDialogQuestSection(-boardId);
        this.input.keyboard.enabled = false;
        break;
      }

      case 'npc_quest_status': {
        // Welle 23: Backend hat Quest-Offers + Turnins für einen NPC geschickt
        const offers = msg.offers || [];
        const turnins = msg.turnins || [];
        this._npcQuestData = this._npcQuestData || {};
        this._npcQuestData[msg.npc_id] = { offers, turnins };
        // Marker setzen: ❗ wenn turn-in vorhanden, sonst ❓ wenn offers
        const marker = turnins.length > 0 ? '❗'
          : offers.length > 0 ? '❓' : '';
        this._setNPCQuestMarker(msg.npc_id, marker);
        // Offenen Dialog refreshen wenn dieser NPC
        if (this.activeDialog && this.activeDialog.npc_id === msg.npc_id) {
          this._refreshDialogQuestSection(msg.npc_id);
        }
        break;
      }

      case 'quest_new':
        this.myQuests.push(msg.quest);
        if (this.questsOpen) this.refreshQuestsUI();
        break;

      case 'quest_progress': {
        const i = this.myQuests.findIndex(q => q.id === msg.quest.id);
        if (i >= 0) this.myQuests[i] = msg.quest; else this.myQuests.push(msg.quest);
        if (this.questsOpen) this.refreshQuestsUI();
        if (msg.quest.status === 'completed') this.showEvent(`📜 Quest erfüllt: ${msg.quest.title}`);
        break;
      }

      case 'quest_closed':
        this.myQuests = this.myQuests.filter(q => q.id !== msg.quest_id);
        if (this.questsOpen) this.refreshQuestsUI();
        break;

      case 'research_update': {
        if (msg.error === 'not_enough_points') {
          this.showEvent(`🔬 Nicht genug Pool-Punkte (${msg.pool || 0} vorhanden)`);
          if (msg.pool != null) this.myResearchPool = msg.pool;
          if (this.researchOpen) this.refreshResearchUI();
          break;
        }
        const n = this.myResearch[msg.node_id];
        if (n) {
          n.points = msg.points;
          n.done   = msg.done;
        }
        if (msg.pool != null) this.myResearchPool = msg.pool;
        if (msg.done) {
          for (const [id, other] of Object.entries(this.myResearch)) {
            if (other.prereq === msg.node_id) other.available = true;
          }
          this.showEvent(`🔬 Forschung abgeschlossen: ${n?.name || msg.node_id}`);
        }
        if (this.researchOpen) this.refreshResearchUI();
        break;
      }

      case 'research_pool_update':
        // Welle 22: Pool-Update (Skill-XP / Craft / Item-Use / Time-Tick)
        this.myResearchPool = msg.pool || 0;
        if (msg.gained > 0 && msg.reason) {
          this.showEvent(`🔬 +${msg.gained} (${msg.reason})`);
        }
        if (this.researchOpen) this.refreshResearchUI();
        break;

      case 'bills_update':
        this.bills = msg.bills || [];
        if (this.activeCrafting) this.refreshBillsUI();
        break;

      case 'bill_progress': {
        const b = (this.bills || []).find(x => x.id === msg.bill_id);
        if (b) {
          b.completed = msg.completed;
          b.target_count = msg.target;
          b.status = 'active';
        }
        if (this.activeCrafting) this.refreshBillsUI();
        break;
      }

      case 'bill_done':
        this.bills = (this.bills || []).filter(x => x.id !== msg.bill_id);
        if (this.activeCrafting) this.refreshBillsUI();
        this.showEvent(`✅ Auftrag fertig: ${msg.recipe_id}`);
        break;

      case 'bill_blocked': {
        const b = (this.bills || []).find(x => x.id === msg.bill_id);
        if (b) b.status = 'blocked';
        if (this.activeCrafting) this.refreshBillsUI();
        break;
      }

      case 'npc_mood': {
        const entry = this.npcs[msg.npc_id];
        if (entry) {
          const prev = entry.npc?.mental_state || 'normal';
          if (!entry.npc) entry.npc = {};
          entry.npc.mental_state = msg.mental_state;
          entry.npc.mood_value = msg.mood_value;
          this.refreshNPCMood(msg.npc_id);
          // Welle 50: One-shot Pulse beim Wechsel auf negativen Zustand
          const NEG = new Set(['sad','fleeing','berserk']);
          if (NEG.has(msg.mental_state) && prev !== msg.mental_state && entry.container) {
            this.playOverlayAnim('negative_mood_pulse',
                                  entry.container.x, entry.container.y,
                                  { scale: 0.95, depth: 11, once: true });
          }
        }
        break;
      }

      case 'body_part_damaged':
        if (!this.myBodyParts) this.myBodyParts = { legs:100, arms:100, torso:100 };
        this.myBodyParts[msg.part] = msg.remaining;
        this.refreshBodyParts();
        // Kleiner Toast bei stärkerem Treffer
        if (msg.dmg >= 10) {
          const label = { torso:'Torso', arms:'Arme', legs:'Beine' }[msg.part] || msg.part;
          this.showEvent(`💢 ${label} getroffen (-${msg.dmg})`);
        }
        break;

      case 'skill_xp':
        if (!this.mySkills[msg.skill]) this.mySkills[msg.skill] = {xp:0, level:0};
        this.mySkills[msg.skill] = { xp: msg.xp, level: msg.level };
        if (msg.leveled_up) {
          this.showEvent(`🎉 ${msg.skill} Level ${msg.level}!`);
          // Welle 50: Level-Up-Ring am Player (einmalig, kein Loop)
          if (this.mySprite) {
            this.playOverlayAnim('level_up_ring', this.mySprite.x, this.mySprite.y,
                                 { scale: 1.3, depth: 12, once: true });
          }
        }
        if (this.skillsOpen) this.refreshSkillsUI();
        break;

      case 'trade_open':
        this.openTrade(msg);
        break;

      case 'trade_coins':
        if (this.activeTrade) {
          this.activeTrade.coins = msg.coins;
          this.refreshTradeUI();
        }
        break;
    }
  }

  // — Trade —
  openTrade(payload) {
    if (this.activeDialog || this.inventoryOpen || this.activeChest || this.activeCrafting) return;
    this.activeTrade = {
      npc_id: payload.npc_id,
      npc_name: payload.npc_name,
      offerings: payload.offerings,
      coins: payload.coins,
    };
    document.getElementById('trade-npc-name').textContent = payload.npc_name;
    document.getElementById('trade-overlay').classList.add('active');
    this.input.keyboard.enabled = false;
    this.input.keyboard.clearCaptures();
    this.refreshTradeUI();
  }

  closeTrade() {
    this.activeTrade = null;
    document.getElementById('trade-overlay').classList.remove('active');
    this.input.keyboard.enabled = true;
  }

  refreshTradeUI() {
    if (!this.activeTrade) return;
    document.getElementById('trade-coins').textContent = this.activeTrade.coins;
    // Welle 38: Stacking-aware sellable list
    const left = document.getElementById('trade-player-items');
    left.innerHTML = '';
    left.className = 'trade-col';
    const sellable = this.inventory.filter(it => !it.equipped_slot && it.kind !== 'gold_ore');
    for (const it of sellable) {
      const cfg = ITEM[it.kind] || {};
      const row = document.createElement('div');
      row.className = 'trade-row';
      const img = document.createElement('img'); img.src = itemAssetPath(it); row.appendChild(img);
      const name = document.createElement('div');
      const nm = document.createElement('div');
      nm.className = 'name';
      nm.textContent = it.unique_name || it.name;
      name.appendChild(nm);
      if ((it.quantity || 1) > 1) {
        const q = document.createElement('div');
        q.className = 'qty';
        q.textContent = `× ${it.quantity}`;
        name.appendChild(q);
      }
      row.appendChild(name);
      const price = document.createElement('span'); price.className = 'price';
      price.textContent = '?'; row.appendChild(price);
      const btn = document.createElement('button');
      btn.textContent = '→ Verkaufen';
      btn.title = (it.quantity || 1) > 1 ? 'Verkauft 1 Stück (Stack bleibt)' : '';
      btn.addEventListener('click', () => {
        this.ws.send(JSON.stringify({type: 'sell_item', item_id: it.id}));
      });
      row.appendChild(btn);
      // Tooltip
      row.addEventListener('mouseenter', (ev) => this.showItemTooltip(it, ev));
      row.addEventListener('mousemove',  (ev) => this.showItemTooltip(it, ev));
      row.addEventListener('mouseleave', () => this.hideItemTooltip());
      left.appendChild(row);
    }
    if (sellable.length === 0) {
      const e = document.createElement('div');
      e.style.cssText = 'color:#807060;font-size:11px;padding:10px;text-align:center;';
      e.textContent = '(nichts zu verkaufen)';
      left.appendChild(e);
    }
    // Händler-Angebot
    const right = document.getElementById('trade-offerings');
    right.innerHTML = '';
    right.className = 'trade-col';
    for (const off of this.activeTrade.offerings) {
      const row = document.createElement('div');
      row.className = 'trade-row';
      const canAfford = this.activeTrade.coins >= off.price;
      if (!canAfford) row.classList.add('unaffordable');
      const img = document.createElement('img'); img.src = off.sprite_path; row.appendChild(img);
      const name = document.createElement('span'); name.className = 'name';
      name.textContent = off.name; row.appendChild(name);
      const price = document.createElement('span'); price.className = 'price';
      price.textContent = `${off.price} 🪙`; row.appendChild(price);
      const btn = document.createElement('button');
      btn.textContent = '← Kaufen';
      btn.disabled = !canAfford;
      btn.addEventListener('click', () => {
        this.ws.send(JSON.stringify({type: 'buy_item', kind: off.kind}));
      });
      row.appendChild(btn);
      // Tooltip mit fake-item Daten
      const fakeItem = { kind: off.kind, name: off.name, category: ITEM[off.kind]?.category, quality: 'normal' };
      row.addEventListener('mouseenter', (ev) => this.showItemTooltip(fakeItem, ev));
      row.addEventListener('mousemove',  (ev) => this.showItemTooltip(fakeItem, ev));
      row.addEventListener('mouseleave', () => this.hideItemTooltip());
      right.appendChild(row);
    }
  }

  // — Chunked World ——————————————————————————————————————————————————————————
  tileAt(x, y) {
    const cx = Math.floor(x / CHUNK_SIZE);
    const cy = Math.floor(y / CHUNK_SIZE);
    const chunk = this.chunks[`${cx},${cy}`];
    if (!chunk) return null;
    const lx = x - cx * CHUNK_SIZE;
    const ly = y - cy * CHUNK_SIZE;
    return chunk[ly][lx];
  }

  drawChunkTiles(cx, cy) {
    const chunk = this.chunks[`${cx},${cy}`];
    if (!chunk) return;
    for (let ly = 0; ly < CHUNK_SIZE; ly++) {
      for (let lx = 0; lx < CHUNK_SIZE; lx++) {
        const wx = cx * CHUNK_SIZE + lx;
        const wy = cy * CHUNK_SIZE + ly;
        const key = `${wx},${wy}`;
        if (this.tileSprites[key]) continue;  // schon gerendert
        const t = TILE_BY_ID[chunk[ly][lx]];
        if (!t) continue;
        const img = this.add.image(wx * TILE_SIZE, wy * TILE_SIZE, t.sprite).setOrigin(0, 0);
        img.setDisplaySize(TILE_SIZE, TILE_SIZE);
        img.setDepth(0);
        this.tileSprites[key] = img;
      }
    }
  }

  // — Chest —
  openChest(chestId, items) {
    if (this.activeDialog || this.inventoryOpen || this.activeCrafting) return;
    this.activeChest = { chest_id: chestId, items };
    document.getElementById('chest-overlay').classList.add('active');
    this.input.keyboard.enabled = false;
    this.input.keyboard.clearCaptures();
    this.refreshChestUI();
  }

  closeChest() {
    this.activeChest = null;
    document.getElementById('chest-overlay').classList.remove('active');
    this.input.keyboard.enabled = true;
  }

  refreshChestUI() {
    if (!this.activeChest) return;
    const left = document.getElementById('chest-player-items');
    const right = document.getElementById('chest-chest-items');
    left.innerHTML = ''; right.innerHTML = '';
    const playerItems = this.inventory.filter(it => !it.equipped_slot);
    const mkRow = (item, btnLabel, onClick) => {
      const cfg = ITEM[item.kind] || {};
      const row = document.createElement('div');
      row.className = 'chest-item-row';
      const img = document.createElement('img'); img.src = itemAssetPath(item); row.appendChild(img);
      const name = document.createElement('span'); name.className = 'name';
      name.textContent = item.name; row.appendChild(name);
      const btn = document.createElement('button'); btn.textContent = btnLabel;
      btn.addEventListener('click', onClick); row.appendChild(btn);
      return row;
    };
    for (const it of playerItems) {
      left.appendChild(mkRow(it, '→ Truhe', () => this.transferToChest(it.id)));
    }
    for (const it of this.activeChest.items) {
      right.appendChild(mkRow(it, '↑ Beutel', () => this.transferFromChest(it.id)));
    }
    if (playerItems.length === 0) {
      const e = document.createElement('div'); e.className = 'inv-empty';
      e.textContent = '(leer)'; left.appendChild(e);
    }
    if (this.activeChest.items.length === 0) {
      const e = document.createElement('div'); e.className = 'inv-empty';
      e.textContent = '(leer)'; right.appendChild(e);
    }
  }

  transferToChest(itemId) {
    this.ws.send(JSON.stringify({
      type: 'chest_transfer_to', chest_id: this.activeChest.chest_id, item_id: itemId,
    }));
  }
  transferFromChest(itemId) {
    this.ws.send(JSON.stringify({
      type: 'chest_transfer_from', chest_id: this.activeChest.chest_id, item_id: itemId,
    }));
  }

  // — Crafting —
  openCrafting(station, recipeList) {
    if (this.activeDialog || this.inventoryOpen || this.activeChest) return;
    this.activeCrafting = { station, recipes: recipeList, activeCategory: 'all' };
    if (!this.bills) this.bills = [];     // initial leer; Server schickt bills_update
    const labels = { workbench: 'Werkbank', furnace: 'Schmelze', anvil: 'Amboss', hand: '🛠 Handwerken' };
    document.getElementById('crafting-station-label').textContent = labels[station] || station;
    document.getElementById('crafting-overlay').classList.add('active');
    this.input.keyboard.enabled = false;
    this.input.keyboard.clearCaptures();
    // Beim Öffnen frische Bill-Liste vom Server abrufen
    this.ws.send(JSON.stringify({ type: 'list_bills', station_type: station }));
    this.refreshCraftingUI();
    this.refreshBillsUI();
  }

  closeCrafting() {
    this.activeCrafting = null;
    document.getElementById('crafting-overlay').classList.remove('active');
    this.input.keyboard.enabled = true;
  }

  refreshCraftingUI() {
    if (!this.activeCrafting) return;
    const list = document.getElementById('crafting-recipes');
    list.innerHTML = '';
    // Welle 36: Stacking-aware counts
    const counts = {};
    for (const it of this.inventory) {
      if (it.equipped_slot) continue;
      counts[it.kind] = (counts[it.kind] || 0) + (it.quantity || 1);
    }

    // Welle 50: Kategorie-Tabs. Rezepte ohne 'category' fallen auf 'material'.
    const CAT_ORDER  = ['weapon','armor','tool','jewelry','consumable','food','material','magic'];
    const CAT_LABELS = {
      weapon:'⚔️ Waffen', armor:'🛡️ Rüstung', tool:'🔧 Werkzeug',
      jewelry:'💎 Schmuck', consumable:'🧪 Verbrauch', food:'🍞 Speisen',
      material:'📦 Material', magic:'📜 Magie',
    };
    const byCat = {};
    for (const r of this.activeCrafting.recipes) {
      const c = r.category || 'material';
      (byCat[c] = byCat[c] || []).push(r);
    }
    const presentCats = CAT_ORDER.filter(c => byCat[c]);
    // Falls bisher aktive Kategorie nicht mehr vorhanden → auf 'all' resetten
    if (this.activeCrafting.activeCategory !== 'all'
        && !presentCats.includes(this.activeCrafting.activeCategory)) {
      this.activeCrafting.activeCategory = 'all';
    }
    // Tabs nur rendern wenn mehr als 1 Kategorie vorhanden ist
    if (presentCats.length > 1) {
      const tabs = document.createElement('div');
      tabs.className = 'crafting-tabs';
      const mkTab = (key, label, count) => {
        const t = document.createElement('button');
        t.className = 'crafting-tab' + (this.activeCrafting.activeCategory === key ? ' active' : '');
        t.textContent = count != null ? `${label} (${count})` : label;
        t.addEventListener('click', () => {
          this.activeCrafting.activeCategory = key;
          this.refreshCraftingUI();
        });
        return t;
      };
      tabs.appendChild(mkTab('all', 'Alle', this.activeCrafting.recipes.length));
      for (const c of presentCats) tabs.appendChild(mkTab(c, CAT_LABELS[c] || c, byCat[c].length));
      list.appendChild(tabs);
    }

    const activeCat = this.activeCrafting.activeCategory || 'all';
    // In 'all'-Ansicht nach Kategorie sortiert (CAT_ORDER); in Einzel-
    // Kategorie nach Output-Kind gruppiert (alle Schwerter zusammen etc.).
    let recipesToShow;
    if (activeCat === 'all') {
      recipesToShow = [];
      for (const c of presentCats) recipesToShow.push(...byCat[c]);
    } else {
      recipesToShow = byCat[activeCat] || [];
    }

    let lastSubcat = null;
    for (const recipe of recipesToShow) {
      // Subcat-Divider: in 'all' nach Kategorie, sonst nach Output-Kind.
      const subKey = activeCat === 'all' ? (recipe.category || 'material') : recipe.output;
      if (subKey !== lastSubcat) {
        const sub = document.createElement('div');
        sub.className = 'crafting-subcat';
        if (activeCat === 'all') {
          sub.textContent = CAT_LABELS[subKey] || subKey;
        } else {
          const outCfg = ITEM[recipe.output] || { name: recipe.output };
          sub.textContent = outCfg.name || recipe.output;
        }
        list.appendChild(sub);
        lastSubcat = subKey;
      }
      const row = document.createElement('div');
      row.className = 'recipe-row';
      // Welle 22: Research-Gate
      const reqNode = recipe.requires;
      const reqMet = !reqNode || (this.myResearch && this.myResearch[reqNode]?.done);
      const canCraft = reqMet && recipe.inputs.every(([k, n]) => (counts[k] || 0) >= n);
      if (canCraft) row.classList.add('craftable');
      if (!reqMet) {
        row.classList.add('research-locked');
        const reqName = this.myResearch?.[reqNode]?.name || reqNode;
        row.title = `🔒 Erst forschen: ${reqName}`;
      }
      // Output-Icon mit Tooltip auf Hover
      const outItem = ITEM[recipe.output] || { name: recipe.output };
      const icon = document.createElement('div');
      icon.className = 'recipe-icon';
      if (outItem.path) {
        const img = document.createElement('img');
        img.src = outItem.path;
        icon.appendChild(img);
      }
      // Welle 18: Tooltip auf das Output-Item (was wird gecraftet)
      const outItemDesc = { kind: recipe.output, name: outItem.name, category: outItem.category, quality: 'normal' };
      icon.addEventListener('mouseenter', (ev) => this.showItemTooltip(outItemDesc, ev));
      icon.addEventListener('mousemove',  (ev) => this.showItemTooltip(outItemDesc, ev));
      icon.addEventListener('mouseleave', () => this.hideItemTooltip());
      row.appendChild(icon);
      // Info: Name + Ingredient-Chips
      const info = document.createElement('div'); info.className = 'recipe-info';
      const name = document.createElement('div');
      name.className = 'recipe-name';
      name.textContent = recipe.name;
      info.appendChild(name);
      const ing = document.createElement('div');
      ing.className = 'recipe-ingredients';
      for (const [k, n] of recipe.inputs) {
        const has = counts[k] || 0;
        const ok = has >= n;
        const chip = document.createElement('span');
        chip.className = 'ingredient-chip ' + (ok ? 'ok' : 'missing');
        if (ITEM[k]?.path) {
          const img = document.createElement('img');
          img.src = ITEM[k].path;
          chip.appendChild(img);
        }
        const txt = document.createElement('span');
        txt.textContent = `${has}/${n}`;
        chip.appendChild(txt);
        chip.title = ITEM[k]?.name || k;
        // Welle 18: Tooltip auf den Input-Zutaten — zeigt was die Ressource ist
        const ingDesc = { kind: k, name: ITEM[k]?.name || k, category: ITEM[k]?.category, quality: 'normal' };
        chip.addEventListener('mouseenter', (ev) => this.showItemTooltip(ingDesc, ev));
        chip.addEventListener('mousemove',  (ev) => this.showItemTooltip(ingDesc, ev));
        chip.addEventListener('mouseleave', () => this.hideItemTooltip());
        ing.appendChild(chip);
      }
      info.appendChild(ing);
      row.appendChild(info);
      // Controls
      const ctrls = document.createElement('div');
      ctrls.className = 'recipe-controls';
      const btn = document.createElement('button');
      btn.textContent = '🔨';
      const lockTitle = !reqMet ? `🔒 Erst forschen: ${this.myResearch?.[reqNode]?.name || reqNode}` : null;
      btn.title = lockTitle || 'Herstellen';
      btn.disabled = !canCraft;
      btn.addEventListener('click', () => this.craft(recipe.id));
      ctrls.appendChild(btn);
      const b5 = document.createElement('button');
      b5.className = 'bill-btn';
      b5.textContent = '×5';
      b5.title = lockTitle || 'Auftrag für 5 Stück (Bills-Queue)';
      b5.disabled = !reqMet;
      b5.addEventListener('click', () => this.addBill(recipe.id, 5));
      ctrls.appendChild(b5);
      row.appendChild(ctrls);
      list.appendChild(row);
    }
  }

  refreshBillsUI() {
    const list = document.getElementById('crafting-bills-list');
    if (!list || !this.activeCrafting) return;
    list.innerHTML = '';
    const stationBills = (this.bills || [])
      .filter(b => b.station_type === this.activeCrafting.station);
    if (stationBills.length === 0) {
      list.innerHTML = '<div style="font-size:10px;color:#806040;">— keine Aufträge —</div>';
      return;
    }
    for (const bill of stationBills) {
      const row = document.createElement('div');
      row.className = 'bill-row';
      // Rezept-Name suchen
      const rec = this.activeCrafting.recipes.find(r => r.id === bill.recipe_id);
      const recName = rec ? rec.name : bill.recipe_id;
      const name = document.createElement('span');
      name.className = 'bill-name';
      name.textContent = recName;
      row.appendChild(name);
      const prog = document.createElement('span');
      prog.className = 'bill-progress';
      prog.textContent = `${bill.completed}/${bill.target_count}`;
      row.appendChild(prog);
      const st = document.createElement('span');
      st.className = 'bill-status ' + (bill.status || '');
      st.textContent = bill.status || '';
      row.appendChild(st);
      const rm = document.createElement('button');
      rm.className = 'bill-remove';
      rm.textContent = '×';
      rm.addEventListener('click', () => this.removeBill(bill.id));
      row.appendChild(rm);
      list.appendChild(row);
    }
  }

  addBill(recipeId, count) {
    if (!this.activeCrafting) return;
    this.ws.send(JSON.stringify({
      type: 'add_bill',
      station_type: this.activeCrafting.station,
      recipe_id: recipeId,
      count: count,
    }));
  }

  removeBill(billId) {
    this.ws.send(JSON.stringify({ type: 'remove_bill', bill_id: billId }));
  }

  // Welle 51 — Sign-Inspect Modal
  openSignInspect(slug) {
    const variant = SIGN_VARIANTS.find(([s]) => s === slug);
    const label = variant ? variant[1] : slug;
    document.getElementById('sign-inspect-label').textContent = `🪧 ${label}`;
    // Master-Version (512) für scharfe Darstellung, fällt auf 256 zurück falls fehlt
    document.getElementById('sign-inspect-img').src =
      `/assets/props/settlement/signs/professional/masters_512/${slug}_sign.png`;
    document.getElementById('sign-inspect-overlay').classList.add('active');
    this.signInspectOpen = true;
    if (this.input && this.input.keyboard) this.input.keyboard.enabled = false;
  }

  closeSignInspect() {
    document.getElementById('sign-inspect-overlay').classList.remove('active');
    this.signInspectOpen = false;
    if (this.input && this.input.keyboard) this.input.keyboard.enabled = true;
  }

  craft(recipeId) {
    // Welle 50: Funken am Player anzeigen während der Craft läuft.
    // Bei Hand-Crafting am Player; bei Station-Crafting (workbench/furnace/
    // anvil) wäre die Station selbst die korrektere Position — die ist
    // aber nicht zentral indiziert, deshalb erstmal generisch am Player.
    if (this.mySprite) {
      this.playOverlayAnim('crafting_sparks', this.mySprite.x, this.mySprite.y - TILE_SIZE * 0.3,
                           { scale: 1.1, depth: 11, once: true });
    }
    this.ws.send(JSON.stringify({
      type: 'craft', station: this.activeCrafting.station, recipe_id: recipeId,
    }));
  }

  // Welle 50: Hilfsfunktion für world_polish-Overlays.
  // worldX/worldY in PIXELN (nicht Tiles). opts.scale: Multiplikator (Sprite ist
  // 192px; default macht das ~2 Tiles breit). opts.once erzwingt eine einzelne
  // Wiedergabe auch bei looping anims. Liefert das Sprite zurück; bei one-shot
  // räumt es sich selbst weg, bei loop muss der Aufrufer destroy() rufen.
  playOverlayAnim(animName, worldX, worldY, opts = {}) {
    const key = `wp_${animName}`;
    if (!this.anims.exists(key)) return null;
    const scale = opts.scale ?? 1.0;
    const depth = opts.depth ?? 9;
    const sprite = this.add.sprite(worldX, worldY, key, 0)
      .setOrigin(0.5, 0.5)
      .setDepth(depth);
    sprite.setDisplaySize(TILE_SIZE * 2 * scale, TILE_SIZE * 2 * scale);
    if (opts.alpha != null) sprite.setAlpha(opts.alpha);
    const spec = WORLD_POLISH_ANIMS.find(a => `wp_${a.key}` === key);
    const willLoop = spec?.looping && !opts.once;
    sprite.play({ key, repeat: opts.once ? 0 : undefined });
    if (!willLoop) sprite.on('animationcomplete', () => sprite.destroy());
    return sprite;
  }

  showVisualEffect(kind, x, y) {
    // Welle 50: world_polish Overlays — Backend sendet kind: 'wp_<anim>'.
    if (typeof kind === 'string' && kind.startsWith('wp_')) {
      const animName = kind.slice(3);
      const cx = x * TILE_SIZE + TILE_SIZE / 2;
      const cy = y * TILE_SIZE + TILE_SIZE / 2;
      // Persistent loop für gepflanzte Felder zwischen Sow und Harvest.
      if (!this._growingCrops) this._growingCrops = {};
      const tileKey = `${x},${y}`;
      if (animName === 'sow_seeds') {
        // One-shot Pop + loop-Marker an dem Tile
        this.playOverlayAnim('sow_seeds', cx, cy, { scale: 1.0, depth: 8, once: true });
        if (this._growingCrops[tileKey]) this._growingCrops[tileKey].destroy();
        this._growingCrops[tileKey] = this.playOverlayAnim(
          'crop_growth_sparkle', cx, cy,
          { scale: 0.8, depth: 1.5, alpha: 0.55 }
        );
        return;
      }
      if (animName === 'harvest_crop') {
        // Sparkle stoppen + Pop einmalig
        if (this._growingCrops[tileKey]) {
          this._growingCrops[tileKey].destroy();
          delete this._growingCrops[tileKey];
        }
        this.playOverlayAnim('harvest_crop', cx, cy, { scale: 1.0, depth: 8, once: true });
        return;
      }
      this.playOverlayAnim(animName, cx, cy, { scale: 1.0, depth: 8, once: true });
      return;
    }
    // Welle 40: Multi-Frame-Sequenzen für Spell-Effekte
    const SEQUENCES = {
      fireball_explosion: ['fx_fireball_1','fx_fireball_2','fx_fireball_3'],
      heal_glow:          ['fx_heal_1','fx_heal_2'],
      lightning_strike:   ['fx_lightning_1','fx_lightning_2'],
      magic_circle:       ['fx_magic_circle_1','fx_magic_circle_2'],
      sword_slash:        ['fx_sword_slash_1','fx_sword_slash_2','fx_sword_slash_3'],
      axe_swing:          ['fx_axe_swing_1','fx_axe_swing_2','fx_axe_swing_3'],
      mace_hit:           ['fx_mace_hit_1','fx_mace_hit_2'],
      arrow_hit:          ['fx_arrow_hit'],
      ice_impact:         ['fx_ice_impact'],
    };
    const cx = x * TILE_SIZE + TILE_SIZE / 2;
    const cy = y * TILE_SIZE + TILE_SIZE / 2;
    const seq = SEQUENCES[kind];
    if (seq) {
      // Frame-Sequenz abspielen
      const firstKey = seq.find(k => this.textures.exists(k));
      if (!firstKey) return;
      const img = this.add.image(cx, cy, firstKey).setOrigin(0.5).setDepth(8);
      img.setDisplaySize(TILE_SIZE * 1.3, TILE_SIZE * 1.3);
      let frame = 0;
      const frameTime = 90;
      const advance = () => {
        frame++;
        if (frame >= seq.length || !this.textures.exists(seq[frame])) {
          // Fade-out
          this.tweens.add({
            targets: img, alpha: 0, duration: 180,
            onComplete: () => img.destroy(),
          });
          return;
        }
        img.setTexture(seq[frame]);
        this.time.delayedCall(frameTime, advance);
      };
      this.time.delayedCall(frameTime, advance);
      return;
    }
    // Single-Frame-Fallback (hit_spark etc.)
    const key = `fx_${kind}`;
    if (!this.textures.exists(key)) return;
    const img = this.add.image(cx, cy, key).setOrigin(0.5).setDepth(8);
    img.setDisplaySize(TILE_SIZE, TILE_SIZE);
    img.setAlpha(0.95);
    this.tweens.add({
      targets: img,
      alpha: 0,
      scale: { from: img.scale * 1.0, to: img.scale * 1.3 },
      duration: 600,
      ease: 'Quad.easeOut',
      onComplete: () => img.destroy(),
    });
  }

  refreshHpBar(flash = false) {
    const fill = document.getElementById('hp-fill');
    const text = document.getElementById('hp-text');
    const bar = document.getElementById('hp-bar');
    const ratio = this.myMaxHp > 0 ? this.myHp / this.myMaxHp : 0;
    fill.style.width = (ratio * 100) + '%';
    text.textContent = `${this.myHp} / ${this.myMaxHp}`;
    if (flash) {
      bar.classList.remove('damage-flash');
      void bar.offsetWidth;
      bar.classList.add('damage-flash');
    }
  }

  refreshManaBar() {
    const fill = document.getElementById('mana-fill');
    const text = document.getElementById('mana-text');
    const ratio = this.myMaxMana > 0 ? this.myMana / this.myMaxMana : 0;
    fill.style.width = (ratio * 100) + '%';
    text.textContent = `${this.myMana} / ${this.myMaxMana}`;
  }

  refreshBodyParts() {
    const bp = this.myBodyParts || { legs: 100, arms: 100, torso: 100 };
    for (const part of ['torso', 'arms', 'legs']) {
      const val = bp[part] ?? 100;
      const fill = document.getElementById(`bp-${part}-fill`);
      const text = document.getElementById(`bp-${part}-text`);
      if (!fill || !text) continue;
      fill.style.width = val + '%';
      const icon = { torso: '🫀', arms: '💪', legs: '🦵' }[part];
      const label = { torso: 'Torso', arms: 'Arme', legs: 'Beine' }[part];
      text.textContent = `${icon} ${label} ${val}/100`;
    }
  }

  refreshNeedsBars() {
    const hf = document.getElementById('hunger-fill');
    const ht = document.getElementById('hunger-text');
    const hr = this.myMaxHunger > 0 ? this.myHunger / this.myMaxHunger : 0;
    hf.style.width = (hr * 100) + '%';
    ht.textContent = `🍖 ${this.myHunger}/${this.myMaxHunger}`;
    // Welle 17 — Durst
    const tf = document.getElementById('thirst-fill');
    const tt = document.getElementById('thirst-text');
    if (tf && tt) {
      const tr = this.myMaxThirst > 0 ? this.myThirst / this.myMaxThirst : 0;
      tf.style.width = (tr * 100) + '%';
      tt.textContent = `💧 ${this.myThirst}/${this.myMaxThirst}`;
    }
    const sf = document.getElementById('stamina-fill');
    const st = document.getElementById('stamina-text');
    const sr = this.myMaxStamina > 0 ? this.myStamina / this.myMaxStamina : 0;
    sf.style.width = (sr * 100) + '%';
    st.textContent = `⚡ ${this.myStamina}/${this.myMaxStamina}`;
  }

  refreshSkillsUI() {
    const list = document.getElementById('skills-list');
    if (!list) return;
    const skills = [
      ['mining',       '⛏️', 'Bergbau'],
      ['woodcutting',  '🪓', 'Holzfällen'],
      ['gathering',    '🌿', 'Sammeln'],
      ['construction', '🔨', 'Bauen'],
      ['crafting',     '⚒️', 'Handwerk'],
      ['combat',       '⚔️', 'Kampf'],
      ['magic',        '✨', 'Magie'],
      ['cooking',      '🍳', 'Kochen'],
      ['medical',      '❤️‍🩹', 'Heilkunde'],
      ['farming',      '🌾', 'Landwirtschaft'],
      ['social',       '💬', 'Sozial'],
    ];
    list.innerHTML = '';
    for (const [key, icon, label] of skills) {
      const s = this.mySkills[key] || {xp:0, level:0};
      // approx xp-to-next-level
      const xpForLevel = (n) => Math.floor(100 * Math.pow(n, 1.5));
      const totalForLevel = (lv) => { let c=0; for (let i=1;i<=lv;i++) c+=xpForLevel(i); return c; };
      const cur = s.xp - totalForLevel(s.level);
      const need = xpForLevel(s.level + 1);
      const pct = need > 0 ? (cur / need) * 100 : 100;
      const row = document.createElement('div');
      row.className = 'skill-row';
      row.innerHTML = `
        <span class="skill-icon">${icon}</span>
        <span class="skill-name">${label}</span>
        <span class="skill-level">Lv ${s.level}</span>
        <div class="skill-progress">
          <div class="skill-progress-fill" style="width:${pct}%"></div>
          <div class="skill-progress-text">${cur} / ${need} XP</div>
        </div>
      `;
      list.appendChild(row);
    }
  }

  toggleSkills() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.skillsOpen = !this.skillsOpen;
    const overlay = document.getElementById('skills-overlay');
    if (this.skillsOpen) {
      overlay.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.refreshSkillsUI();
    } else {
      overlay.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  toggleResearch() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.researchOpen = !this.researchOpen;
    const overlay = document.getElementById('research-overlay');
    if (this.researchOpen) {
      overlay.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.refreshResearchUI();
    } else {
      overlay.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshResearchUI() {
    const list = document.getElementById('research-list');
    if (!list) return;
    list.innerHTML = '';
    // Welle 22: Pool-Banner oben
    const pool = this.myResearchPool || 0;
    const banner = document.createElement('div');
    banner.style.cssText = 'background:rgba(60,40,15,0.6);border:1px solid #a07840;padding:8px 12px;margin-bottom:8px;font-size:14px;';
    banner.innerHTML = `<b style="color:#ffd060">🔬 Forschungs-Pool: ${pool}</b> ` +
      `<span style="color:#a09060;font-size:11px">  · gefüllt durch Skill-XP (1/10), Crafting (+1), Forschungs-Items, alle 5min +1</span>`;
    list.appendChild(banner);
    const order = Object.entries(this.myResearch || {});
    if (order.length === 0) {
      list.innerHTML += '<div style="padding:14px;color:#807060">Noch keine Forschungs-Knoten verfügbar.</div>';
      return;
    }
    for (const [nodeId, node] of order) {
      const row = document.createElement('div');
      row.className = 'research-row';
      if (!node.available) row.classList.add('locked');
      if (node.done) row.classList.add('done');
      const icon = document.createElement('div');
      icon.className = 'research-icon';
      icon.textContent = node.icon || '🔬';
      row.appendChild(icon);
      const info = document.createElement('div');
      const prereqText = node.prereq && !node.available
        ? `<div class="research-desc">benötigt: ${node.prereq}</div>` : '';
      const unlocksText = node.unlocks?.length
        ? `<div class="research-desc">schaltet frei: ${node.unlocks.join(', ')}</div>` : '';
      info.innerHTML = `<div class="research-name">${node.name}</div>${prereqText}${unlocksText}`;
      row.appendChild(info);
      const bar = document.createElement('div');
      bar.className = 'research-bar';
      const fill = document.createElement('div');
      fill.className = 'research-bar-fill';
      const ratio = node.points_max > 0 ? Math.min(1, node.points / node.points_max) : 0;
      fill.style.width = (ratio * 100) + '%';
      const txt = document.createElement('div');
      txt.className = 'research-bar-text';
      txt.textContent = node.done ? '✓ fertig' : `${node.points}/${node.points_max}`;
      bar.appendChild(fill); bar.appendChild(txt);
      row.appendChild(bar);
      const acts = document.createElement('div');
      acts.className = 'research-actions';
      const b1 = document.createElement('button');
      b1.textContent = '+1';
      b1.disabled = node.done || !node.available || pool < 1;
      b1.title = pool < 1 ? 'Nicht genug Pool-Punkte' : `Investiere 1 Pool-Punkt`;
      b1.addEventListener('click', () => this.investResearch(nodeId, 1));
      acts.appendChild(b1);
      const b5 = document.createElement('button');
      b5.textContent = '+5';
      b5.disabled = node.done || !node.available || pool < 5;
      b5.title = pool < 5 ? 'Nicht genug Pool-Punkte' : `Investiere 5 Pool-Punkte`;
      b5.addEventListener('click', () => this.investResearch(nodeId, 5));
      acts.appendChild(b5);
      row.appendChild(acts);
      list.appendChild(row);
    }
  }

  investResearch(nodeId, points) {
    this.ws.send(JSON.stringify({
      type: 'invest_research', node_id: nodeId, points: points,
    }));
  }

  toggleAttributes() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.attributesOpen = !this.attributesOpen;
    const ov = document.getElementById('attributes-overlay');
    if (this.attributesOpen) {
      ov.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      // Frisch berechnen lassen
      this.ws.send(JSON.stringify({ type: 'list_attributes' }));
      this.refreshAttributesUI();
    } else {
      ov.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshAttributesUI() {
    const list = document.getElementById('attributes-list');
    if (!list) return;
    list.innerHTML = '';
    const values = this.myAttributes?.values || {};
    const labels = this.myAttributes?.labels || {};
    // Reihenfolge wie definiert
    const ORDER = ['stärke','ausdauer','energie','intelligenz','weisheit',
                   'verteidigung','geschick','ausweichen','schleichen',
                   'krit_rate','krit_schaden','charisma'];
    for (const key of ORDER) {
      const v = values[key] ?? 0;
      const [label, desc] = labels[key] || [key, ''];
      const row = document.createElement('div');
      row.className = 'attr-row';
      const lbl = document.createElement('div');
      lbl.className = 'attr-label';
      lbl.textContent = label;
      row.appendChild(lbl);
      const d = document.createElement('div');
      d.className = 'attr-desc';
      d.textContent = desc;
      row.appendChild(d);
      const val = document.createElement('div');
      val.className = 'attr-value';
      val.textContent = v;
      row.appendChild(val);
      list.appendChild(row);
    }
  }

  toggleFactions() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.factionsOpen = !this.factionsOpen;
    const ov = document.getElementById('factions-overlay');
    if (this.factionsOpen) {
      ov.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.refreshFactionsUI();
    } else {
      ov.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshFactionsUI() {
    const list = document.getElementById('factions-list');
    if (!list) return;
    list.innerHTML = '';
    if (!this.myFactions || this.myFactions.length === 0) {
      list.innerHTML = '<div style="padding:14px;color:#807060">Keine Faktion-Beziehungen.</div>';
      return;
    }
    const TIER_LABEL = {
      hostile: 'Feindlich', unfriendly: 'Unfreundlich',
      neutral: 'Neutral', friendly: 'Freundlich', allied: 'Verbündet',
    };
    for (const f of this.myFactions) {
      const row = document.createElement('div');
      row.className = 'faction-row';
      const dot = document.createElement('div');
      dot.className = 'faction-dot';
      dot.style.background = f.color || '#888';
      row.appendChild(dot);
      const name = document.createElement('div');
      name.className = 'faction-name';
      name.textContent = f.name;
      row.appendChild(name);
      // Bar: -100..+100 → 0..100% Position
      const bar = document.createElement('div');
      bar.className = 'faction-bar';
      const fill = document.createElement('div');
      fill.className = 'faction-bar-fill';
      const pct = Math.abs(f.goodwill);
      if (f.goodwill >= 0) {
        fill.style.left = '50%';
        fill.style.width = (pct/2) + '%';
        fill.style.background = '#50a050';
      } else {
        fill.style.right = '50%';
        fill.style.width = (pct/2) + '%';
        fill.style.background = '#a05050';
      }
      bar.appendChild(fill);
      row.appendChild(bar);
      const tier = document.createElement('div');
      tier.className = 'faction-tier ' + (f.tier || 'neutral');
      tier.textContent = `${TIER_LABEL[f.tier] || f.tier} ${f.goodwill>=0?'+':''}${f.goodwill}`;
      row.appendChild(tier);
      list.appendChild(row);
    }
  }

  toggleTalents() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.talentsOpen = !this.talentsOpen;
    const overlay = document.getElementById('talents-overlay');
    if (this.talentsOpen) {
      overlay.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.ws.send(JSON.stringify({ type: 'list_talents' }));
      this.refreshTalentsUI();
    } else {
      overlay.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshTalentsUI() {
    const tree = this.myTalents.tree || {};
    const points = this.myTalents.points || 0;
    document.getElementById('talents-points').textContent = `${points} Punkte`;
    // Tabs (1 pro Skill)
    const tabs = document.getElementById('talents-tabs');
    const skills = Object.keys(tree);
    const SKILL_LABEL = {
      mining:'⛏️ Bergbau', woodcutting:'🪓 Holzfällen', gathering:'🌿 Sammeln',
      construction:'🔨 Bauen', crafting:'⚒️ Handwerk', combat:'⚔️ Kampf',
      magic:'✨ Magie', cooking:'🍳 Kochen', medical:'❤️‍🩹 Heilkunde',
      farming:'🌾 Landwirtschaft', social:'💬 Sozial',
    };
    tabs.innerHTML = '';
    for (const sk of skills) {
      const btn = document.createElement('button');
      btn.className = 'talents-tab' + (sk === this.activeTalentTab ? ' active' : '');
      btn.textContent = SKILL_LABEL[sk] || sk;
      btn.addEventListener('click', () => {
        this.activeTalentTab = sk;
        this.refreshTalentsUI();
      });
      tabs.appendChild(btn);
    }
    // Talents im aktiven Tab
    const list = document.getElementById('talents-list');
    list.innerHTML = '';
    const items = tree[this.activeTalentTab] || [];
    if (items.length === 0) {
      list.innerHTML = '<div style="padding:14px;color:#807060">Keine Talente in dieser Kategorie.</div>';
      return;
    }
    // Nach Tier gruppiert
    const tiers = [1, 2, 3];
    for (const tier of tiers) {
      const tierItems = items.filter(it => it.tier === tier);
      if (tierItems.length === 0) continue;
      const sep = document.createElement('div');
      sep.style.cssText = 'color:#806040;font-size:10px;padding:6px 0 2px;border-bottom:1px solid #4a3a20;';
      sep.textContent = `— Stufe ${tier} —`;
      list.appendChild(sep);
      for (const t of tierItems) {
        const row = document.createElement('div');
        row.className = 'talent-row ' + (t.status || 'locked');
        const icon = document.createElement('div');
        icon.className = 'talent-icon';
        icon.textContent = t.icon || '🌟';
        row.appendChild(icon);
        const info = document.createElement('div');
        const prereqText = t.prereq ? ` · braucht: ${t.prereq}` : '';
        info.innerHTML = `<div class="talent-name">${t.name}</div>
                          <div class="talent-desc">${t.desc}</div>
                          <div class="talent-meta">Skill Lvl ${t.skill_min}${prereqText}</div>`;
        row.appendChild(info);
        const act = document.createElement('div');
        act.className = 'talent-action';
        if (t.status === 'available') {
          const btn = document.createElement('button');
          btn.textContent = 'Lernen (1 P)';
          btn.addEventListener('click', () => this.learnTalent(t.id));
          act.appendChild(btn);
        } else {
          const stat = document.createElement('div');
          stat.className = 'talent-status ' + (t.status || '');
          stat.textContent = ({
            learned: '✓ Gelernt', locked: 'Gesperrt',
            needs_points: 'Brauche Punkte',
          })[t.status] || t.status;
          act.appendChild(stat);
        }
        row.appendChild(act);
        list.appendChild(row);
      }
    }
  }

  learnTalent(talent_id) {
    this.ws.send(JSON.stringify({ type: 'learn_talent', talent_id }));
  }

  toggleQuests() {
    if (this.activeDialog || this.activeChest || this.activeCrafting || this.activeTrade) return;
    this.questsOpen = !this.questsOpen;
    const overlay = document.getElementById('quests-overlay');
    if (this.questsOpen) {
      overlay.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.refreshQuestsUI();
    } else {
      overlay.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshQuestsUI() {
    const list = document.getElementById('quests-list');
    if (!list) return;
    list.innerHTML = '';
    // Welle 23: Faction-Reputation-Übersicht oben
    const rep = this.myReputation || {};
    if (Object.keys(rep).length > 0) {
      const repBox = document.createElement('div');
      repBox.style.cssText = 'padding:6px 10px;background:rgba(40,30,15,0.6);border-radius:3px;margin-bottom:8px;font-size:11px';
      const entries = Object.entries(rep).map(([fac, val]) => {
        const col = val >= 10 ? '#9fc890' : val <= -10 ? '#e85040' : '#c8b878';
        return `<span style="color:${col};margin-right:10px">${fac}: ${val >= 0 ? '+' : ''}${val}</span>`;
      });
      repBox.innerHTML = `<b style="color:#c8a868">🤝 Ruf:</b> ${entries.join('')}`;
      list.appendChild(repBox);
    }
    if (!this.myQuests || this.myQuests.length === 0) {
      const empty = document.createElement('div');
      empty.style.cssText = 'padding:14px;color:#807060';
      empty.textContent = 'Keine aktiven Quests. Sprich mit Bewohnern (❓), um Aufträge zu erhalten.';
      list.appendChild(empty);
      return;
    }
    for (const q of this.myQuests) {
      const row = document.createElement('div');
      row.className = 'quest-row ' + (q.status || '');
      const title = document.createElement('div');
      title.className = 'quest-title';
      title.textContent = (q.status === 'completed' ? '✓ ' : '') + q.title;
      row.appendChild(title);
      const desc = document.createElement('div');
      desc.className = 'quest-desc';
      desc.textContent = q.description;
      row.appendChild(desc);
      const obj = document.createElement('div');
      obj.className = 'quest-objective';
      if (q.quest_type === 'fetch') {
        const have = q.progress?.collected || 0;
        const need = q.objective?.count || 0;
        const kind = q.objective?.item_kind || '';
        const itemName = (ITEM[kind] || { name: kind }).name;
        obj.textContent = `🎯 Sammle ${itemName}: ${have}/${need}`;
      } else if (q.quest_type === 'kill') {
        const have = q.progress?.killed || 0;
        const need = q.objective?.count || 0;
        obj.textContent = `⚔️ Erlege ${q.objective?.creature_kind}: ${have}/${need}`;
      } else if (q.quest_type === 'deliver') {
        const ok = q.progress?.delivered;
        const toKind = q.objective?.to_kind || 'NPC';
        obj.textContent = `📦 Bring Item zu ${toKind}: ${ok ? '✓ erledigt' : '○ offen'}`;
      } else if (q.quest_type === 'talk') {
        const ok = q.progress?.talked;
        const toKind = q.objective?.to_kind || 'NPC';
        obj.textContent = `💬 Sprich mit ${toKind}: ${ok ? '✓ erledigt' : '○ offen'}`;
      } else if (q.quest_type === 'visit') {
        const ok = q.progress?.visited;
        const where = q.objective?.location_struct || 'Ort';
        obj.textContent = `🗺️ Besuche ${where}: ${ok ? '✓ erledigt' : '○ offen'}`;
      } else if (q.quest_type === 'defend') {
        const elapsed = q.progress?.elapsed_s || 0;
        const need = q.objective?.duration_s || 60;
        obj.textContent = `🛡️ Halte Position: ${elapsed}/${need}s`;
      } else if (q.quest_type === 'escort') {
        const dist = q.progress?.distance || 0;
        const need = q.objective?.distance_min || 20;
        obj.textContent = `🚶 Eskortiere ${q.objective?.npc_kind}: ${dist}/${need} Tiles`;
      } else if (q.quest_type === 'multi_stage') {
        // Welle 28: Stages anzeigen
        const stages = q.objective?.stages || [];
        const lines = stages.map(s => {
          const icon = s.state === 'completed' ? '✓' :
                       s.state === 'locked' ? '🔒' :
                       s.state === 'in_progress' ? '⏳' : '▷';
          let progTxt = '';
          if (s.type === 'collect' && s.data?.count) {
            const have = s.progress?.collected || 0;
            progTxt = ` (${have}/${s.data.count})`;
          } else if (s.type === 'kill' && s.data?.count) {
            const have = s.progress?.killed || 0;
            progTxt = ` (${have}/${s.data.count})`;
          }
          return `${icon} ${s.description}${progTxt}`;
        });
        obj.innerHTML = lines.map(l => `<div style="margin-top:2px">${l}</div>`).join('');
      } else {
        obj.textContent = JSON.stringify(q.objective);
      }
      row.appendChild(obj);
      const rwd = document.createElement('div');
      rwd.className = 'quest-reward';
      rwd.textContent = '🎁 ' + Object.entries(q.reward || {}).map(([k, v]) => {
        if (k === 'xp') return `${v} XP`;
        const name = (ITEM[k] || { name: k }).name;
        return `${v}× ${name}`;
      }).join(', ');
      row.appendChild(rwd);
      if (q.status === 'completed') {
        const claim = document.createElement('button');
        claim.className = 'quest-claim';
        claim.textContent = 'Belohnung einsammeln';
        claim.addEventListener('click', () => this.claimQuest(q.id));
        row.appendChild(claim);
      }
      list.appendChild(row);
    }
  }

  claimQuest(quest_id) {
    this.ws.send(JSON.stringify({ type: 'claim_quest_reward', quest_id }));
  }

  acceptQuestFromNPC(npc_id) {
    this.ws.send(JSON.stringify({ type: 'accept_quest_from_npc', npc_id }));
  }

  renderStatusEffects(effects) {
    const row = document.getElementById('status-effects-row');
    if (!row) return;
    row.innerHTML = '';
    const ICON = {
      burning: '🔥', poisoned: '☠️', bleeding: '🩸',
      blessed: '✨', shielded: '🛡️', slowed: '🐢',
    };
    for (const eff of effects) {
      const exp = new Date(eff.expires_at);
      const remaining = Math.max(0, Math.round((exp - new Date()) / 1000));
      const chip = document.createElement('span');
      chip.className = 'status-chip';
      chip.textContent = `${ICON[eff.effect] || '•'} ${eff.effect} ${remaining}s`;
      row.appendChild(chip);
    }
  }

  // Welle 9b: Dungeon-Welt-Wechsel
  enterDungeonMode(msg) {
    this.inDungeon    = true;
    this.dungeonTiles = msg.tiles;
    this.dungeonSize  = msg.size;
    // Alle Overworld-Tiles + Structures + NPCs verstecken
    for (const k in this.tileSprites) { this.tileSprites[k].setVisible(false); }
    for (const k in this.structSprites) { this.structSprites[k]?.setVisible(false); }
    for (const id in this.npcs) {
      if (this.npcs[id].container) this.npcs[id].container.setVisible(false);
    }
    for (const id in this.otherPlayers) {
      if (this.otherPlayers[id].container) this.otherPlayers[id].container.setVisible(false);
    }
    // Items am Boden verstecken
    for (const k in this.groundItemSprites || {}) { this.groundItemSprites[k]?.setVisible(false); }
    // Dungeon-Tiles rendern
    this.renderDungeonTiles();
    // Spieler-Position setzen
    this.setLocalPositionFromTile(msg.spawn.x, msg.spawn.y);
    this.showStoryEvent({
      kind: 'natural',
      title: '🏚️ ' + msg.name.split(':')[0],
      body: 'Du betrittst die Tiefen. Suche den Aufstieg.',
    });
  }

  renderDungeonTiles() {
    // Cleanup vorheriger dungeon-sprites
    for (const k in this.dungeonSprites) { this.dungeonSprites[k].destroy(); }
    this.dungeonSprites = {};
    if (!this.dungeonTiles) return;
    const DUNG_TILE = {
      0: 'dungeon_dungeon_wall',
      1: 'dungeon_dungeon_floor',
      2: 'dungeon_dungeon_floor',
      3: 'dungeon_stairs_down',  // stairs_up zeigt das stairs-Asset
    };
    for (let y = 0; y < this.dungeonSize; y++) {
      for (let x = 0; x < this.dungeonSize; x++) {
        const tile = this.dungeonTiles[y][x];
        const key = DUNG_TILE[tile];
        if (!key || !this.textures.exists(key)) continue;
        const img = this.add.image(x * TILE_SIZE, y * TILE_SIZE, key).setOrigin(0, 0);
        img.setDisplaySize(TILE_SIZE, TILE_SIZE);
        img.setDepth(0);
        this.dungeonSprites[`${x},${y}`] = img;
      }
    }
  }

  exitDungeonMode(msg) {
    this.inDungeon = false;
    this.dungeonTiles = null;
    // Dungeon-Sprites abräumen
    for (const k in this.dungeonSprites) { this.dungeonSprites[k].destroy(); }
    this.dungeonSprites = {};
    // Overworld-Tiles wieder einblenden
    for (const k in this.tileSprites) { this.tileSprites[k].setVisible(true); }
    for (const k in this.structSprites) { this.structSprites[k]?.setVisible(true); }
    for (const id in this.npcs) {
      if (this.npcs[id].container) this.npcs[id].container.setVisible(true);
    }
    for (const id in this.otherPlayers) {
      if (this.otherPlayers[id].container) this.otherPlayers[id].container.setVisible(true);
    }
    for (const k in this.groundItemSprites || {}) { this.groundItemSprites[k]?.setVisible(true); }
    // Frische Chunks anwenden
    if (msg.chunks) {
      for (const c of msg.chunks) {
        this.chunks[`${c.cx},${c.cy}`] = c.tiles;
        this.drawChunkTiles(c.cx, c.cy);
      }
      this.drawMinimap();
    }
    // Spieler-Position
    if (msg.spawn) this.setLocalPositionFromTile(msg.spawn.x, msg.spawn.y);
  }

  // Overrides für Dungeon-Mode: tileAt liest aus Dungeon-Tiles statt Chunks
  dungeonTileAt(x, y) {
    if (!this.dungeonTiles || x < 0 || y < 0
        || x >= this.dungeonSize || y >= this.dungeonSize) return 0;
    return this.dungeonTiles[y][x];
  }

  updateTimeOfDay(t) {
    const phase = t.phase || 'day';
    const hour = t.hour ?? 12;
    const minute = (t.minute_of_day ?? hour * 60) % 60;
    const display = document.getElementById('time-display');
    const icon = { morning: '🌅', day: '☀️', evening: '🌇', night: '🌙' }[phase] || '☀️';
    if (display) display.textContent = `${icon} ${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`;
    const tint = document.getElementById('time-tint');
    if (tint) {
      const colors = {
        morning: 'rgba(255,180, 80,0.10)',
        day:     'rgba(0,0,0,0)',
        evening: 'rgba(180, 80, 40,0.20)',
        night:   'rgba(10, 20, 60,0.55)',
      };
      tint.style.background = colors[phase] || 'transparent';
    }
  }

  flashScreenDamage() {
    const el = document.getElementById('screen-damage');
    el.classList.add('active');
    setTimeout(() => el.classList.remove('active'), 200);
  }

  _addEventMarker(marker) {
    // marker: { x, y, label, color, ttl_s }
    if (!this.eventMarkers) this.eventMarkers = [];
    const ttlMs = (marker.ttl_s || 600) * 1000;
    this.eventMarkers.push({
      x: marker.x, y: marker.y,
      label: marker.label || '',
      color: marker.color || '#ffe070',
      expires_at: Date.now() + ttlMs,
    });
    // Limit: max 12 gleichzeitig (älteste rausschmeißen)
    if (this.eventMarkers.length > 12) {
      this.eventMarkers.sort((a, b) => a.expires_at - b.expires_at);
      this.eventMarkers = this.eventMarkers.slice(-12);
    }
    this.drawMinimap();
    // Sicherstellen dass die Minimap regelmäßig neu gezeichnet wird, damit
    // der Pulse-Effekt + Ablauf sichtbar ist.
    if (!this._minimapTicker) {
      this._minimapTicker = setInterval(() => {
        if (this.eventMarkers && this.eventMarkers.length > 0) {
          this.drawMinimap();
        } else {
          clearInterval(this._minimapTicker);
          this._minimapTicker = null;
        }
      }, 200);
    }
  }

  _floatingDamage(worldX, worldY, dmg, opts = {}) {
    // Welle 18: Schwebende Schadens-Zahl die nach oben tweent + ausblendet.
    // color: rot = Spieler-Schaden, gelb = du triffst, grün = Heal (Future).
    const color = opts.color || '#ff5040';
    const fontSize = opts.fontSize || 22;
    const txt = this.add.text(worldX, worldY - 12, `-${dmg}`, {
      fontFamily: 'monospace',
      fontSize: `${fontSize}px`,
      fontStyle: 'bold',
      color,
      stroke: '#000',
      strokeThickness: 4,
    }).setOrigin(0.5).setDepth(10);
    // Leichter zufälliger X-Versatz, damit mehrere Hits nicht übereinander stapeln
    const driftX = worldX + (Math.random() * 24 - 12);
    this.tweens.add({
      targets: txt,
      x: driftX,
      y: worldY - 56,
      alpha: 0,
      duration: 900,
      ease: 'Cubic.easeOut',
      onComplete: () => txt.destroy(),
    });
  }

  knockbackSprite(p) {
    if (!p || !p.container) return;
    const originalX = p.container.x;
    const originalY = p.container.y;
    // Kleine sin-Vibration
    this.tweens.add({
      targets: p.container,
      x: originalX + 4,
      duration: 60,
      yoyo: true,
      repeat: 2,
    });
  }

  flashNPCHit(npcId) {
    const entry = this.npcs[npcId];
    if (!entry || !entry.body) return;
    const originalTint = entry.body.tintTopLeft;
    entry.body.setTint(0xff4040);
    setTimeout(() => {
      if (entry.body && entry.body.scene) {
        // Originalfarbe wiederherstellen — friendly NPCs hatten Tint, Creatures hatten 0xffffff
        const cfg = NPC_SPRITE[entry.npc.kind];
        if (cfg) entry.body.setTint(cfg.tint);
        else entry.body.clearTint();
      }
    }, 250);
  }

  updateNPCHpBar(npcId) {
    const entry = this.npcs[npcId];
    if (!entry) return;
    const ratio = entry.npc.max_hp > 0 ? entry.npc.hp / entry.npc.max_hp : 0;
    if (!entry.hpBar) {
      entry.hpBar = this.add.graphics();
      entry.container.add(entry.hpBar);
    }
    entry.hpBar.clear();
    if (ratio >= 1) return;  // volle HP — kein Balken
    const w = 36;
    entry.hpBar.y = -TILE_SIZE * 0.65;
    entry.hpBar.fillStyle(0x000000, 0.7);
    entry.hpBar.fillRect(-w / 2, 0, w, 4);
    entry.hpBar.fillStyle(0xc83020, 1);
    entry.hpBar.fillRect(-w / 2, 0, w * ratio, 4);
  }

  loadGroundItems(itemList) {
    // Bestehende Item-Sprites entfernen (inkl. Welle-50 Loot-Twinkles)
    for (const id of Object.keys(this.itemSprites)) {
      const s = this.itemSprites[id];
      if (s._twinkle) s._twinkle.destroy();
      s.destroy();
    }
    this.itemSprites = {};
    for (const item of itemList) this.addItemSprite(item);
  }

  addItemSprite(item) {
    const cfg = ITEM[item.kind];
    if (!cfg) return;
    if (this.itemSprites[item.id]) return;
    const cx = item.x * TILE_SIZE + TILE_SIZE / 2;
    const cy = item.y * TILE_SIZE + TILE_SIZE / 2;
    const img = this.add.image(cx, cy, itemSpriteKey(this, item)).setOrigin(0.5);
    // Per-Item-Scale: Münzen klein, Schwerter groß — siehe itemGroundScale.
    const scale = itemGroundScale(item);
    img.setDisplaySize(TILE_SIZE * scale, TILE_SIZE * scale);
    img.setDepth(2);  // über Strukturen (1), unter Charakteren (3)
    // Für Pickup-Click: Item-ID und Tile-Koordinaten am Sprite hinterlegen
    img._itemId = item.id;
    img._tileX = item.x;
    img._tileY = item.y;
    // Welle 50: Loot-Twinkle als loop auf hochwertigen Ground-Items
    // (Equipment + Magic). Ressourcen / Food bleiben unmarkiert.
    const SHINY_CATEGORIES = new Set(['weapon','armor','jewelry','magic']);
    if (SHINY_CATEGORIES.has(cfg.category)) {
      img._twinkle = this.playOverlayAnim('loot_twinkle', cx, cy,
                                          { scale: 0.85, depth: 3, alpha: 0.85 });
    }
    this.itemSprites[item.id] = img;
  }

  // Findet das (oberste) Ground-Item auf dem gegebenen Tile, oder null.
  _findGroundItemAt(tx, ty) {
    for (const id of Object.keys(this.itemSprites)) {
      const s = this.itemSprites[id];
      if (s._tileX === tx && s._tileY === ty) return s;
    }
    return null;
  }

  removeItemSprite(itemId) {
    const s = this.itemSprites[itemId];
    if (s) {
      if (s._twinkle) s._twinkle.destroy();
      s.destroy();
      delete this.itemSprites[itemId];
    }
  }

  // — Wetter ——————————————————————————————————————————————————————
  // Stapelbares Layer-System: stärkeres Wetter = mehr Layer übereinander.
  //   rain    intensity 1=light, 2=+medium, 3=+heavy, 4=+downpour (+lightning)
  //   snow    intensity 1=light, 2=+medium, 3=+heavy, 4=+blizzard
  //   fog     intensity 1=light, 2=+dense
  //   swamp_mist intensity 1+ = single layer
  setWeather(phase, intensity) {
    // Vom Server kommendes Wetter merken — Rendering passiert in _applyWeather,
    // welches zusätzlich das Biome unter dem Player berücksichtigt.
    this.weatherPhase = phase || 'clear';
    this.weatherIntensity = Math.max(0, Math.min(4, intensity || 0));
    this._applyWeather();
  }

  _applyWeather() {
    this._clearWeatherLayers();
    if (this.weatherPhase === 'clear' || this.weatherIntensity === 0) return;
    // Biome-Filter: in der Wüste schneit/regnet es nicht, Lava-Tiles haben
    // gar kein Wetter, Schnee-Tiles bekommen keinen Regen, etc.
    // tile-ids siehe TILES const (WATER=0, SAND=1, GRASS=2, FOREST=3,
    // MOUNTAIN=4, DESERT=5, JUNGLE=6, LAVA=7, SNOW=8, SWAMP=9)
    const WEATHER_ALLOWED_BY_BIOME = {
      0: ['rain','fog','swamp_mist'],
      1: ['rain','fog'],
      2: ['rain','snow','fog'],
      3: ['rain','snow','fog'],
      4: ['snow','fog'],
      5: [],                          // Wüste: kein Standard-Niederschlag
      6: ['rain','fog','swamp_mist'],
      7: [],                          // Lava: nichts
      8: ['snow','fog'],
      9: ['rain','fog','swamp_mist'],
    };
    const tile = this.tileAt(this.myTileX, this.myTileY);
    const allowed = WEATHER_ALLOWED_BY_BIOME[tile];
    if (allowed && !allowed.includes(this.weatherPhase)) return;
    const stack = {
      rain: ['rain_light','rain_medium','rain_heavy','rain_downpour'],
      snow: ['snow_light','snow_medium','snow_heavy','snow_blizzard'],
      fog:  ['fog_light','fog_dense'],
      swamp_mist: ['swamp_mist'],
    }[this.weatherPhase] || [];
    for (let i = 0; i < Math.min(this.weatherIntensity, stack.length); i++) {
      this._addWeatherLayer(stack[i], 6, 0.35 + 0.15 * i);
    }
    if (this.weatherPhase === 'rain' && this.weatherIntensity >= 4) {
      this._addLightningLayer();
    }
  }

  _addWeatherLayer(name, _legacyFrameCount, alpha) {
    // Pro-Set: 16-Frame fullscreen overlay (768×512, gestretcht auf Viewport).
    // Kein tileSprite mehr — die Pro-Overlays sind als camera-space-Layer designt.
    const w = this.scale.width, h = this.scale.height;
    const key0 = `pw_${name}_01`;
    if (!this.textures.exists(key0)) {
      // Falls Pro-Frames noch nicht da → silently skip statt crashen
      return;
    }
    const img = this.add.image(0, 0, key0).setOrigin(0, 0);
    img.setScrollFactor(0).setDepth(200).setAlpha(alpha);
    img.setDisplaySize(w, h);
    const state = { img, frame: 1, count: 16, name };
    // Re-stretch bei Resize (Orientation-Change)
    state.onResize = () => {
      if (state.img && state.img.active) {
        state.img.setDisplaySize(this.scale.width, this.scale.height);
      }
    };
    this.scale.on('resize', state.onResize);
    const timer = this.time.addEvent({
      delay: 60, loop: true,
      callback: () => {
        if (!state.img.active) return;
        state.frame = state.frame % state.count + 1;
        const ff = String(state.frame).padStart(2, '0');
        state.img.setTexture(`pw_${name}_${ff}`);
      },
    });
    state.timer = timer;
    this.weatherLayers[name] = state;
  }

  _addLightningLayer() {
    // Blitze: meiste Zeit unsichtbar (alpha=0), dann seltener Strike mit
    // kurzem schnellen Flash, gefolgt von 6-15s Stille. Nutzt das neue
    // Pro-storm_cell-Set für die Blitz-Frames.
    const w = this.scale.width, h = this.scale.height;
    const key0 = 'pw_storm_cell_01';
    if (!this.textures.exists(key0)) return;
    const img = this.add.image(0, 0, key0).setOrigin(0, 0);
    img.setScrollFactor(0).setDepth(201).setAlpha(0);
    img.setDisplaySize(w, h);
    const state = { img, frame: 1, count: 16 };
    state.onResize = () => {
      if (state.img && state.img.active) {
        state.img.setDisplaySize(this.scale.width, this.scale.height);
      }
    };
    this.scale.on('resize', state.onResize);
    const scheduleNext = () => {
      const delay = 6000 + Math.random() * 9000;
      state.scheduler = this.time.delayedCall(delay, () => {
        if (!state.img.active) return;
        this._playLightningStrike(state, scheduleNext);
      });
    };
    state.scheduler = null;
    scheduleNext();
    this.weatherLayers['storm_lightning'] = state;
  }

  _playLightningStrike(state, onDone) {
    // Pro-Set storm_cell hat 16 Frames mit der Blitz-Animation drin. Wir
    // spielen einen Teilbereich (Frame 4-12) ab — Anfang/Ende sind subtle,
    // Mitte ist der hellste Flash.
    state.img.setAlpha(0.75);
    let i = 4;
    const endFrame = 12;
    const stepDelay = 40;
    const tick = () => {
      if (!state.img.active) return;
      const ff = String(i).padStart(2, '0');
      state.img.setTexture(`pw_storm_cell_${ff}`);
      i++;
      if (i <= endFrame) {
        this.time.delayedCall(stepDelay, tick);
      } else {
        this.tweens.add({
          targets: state.img, alpha: 0, duration: 280,
          onComplete: () => onDone && onDone(),
        });
      }
    };
    tick();
  }

  _clearWeatherLayers() {
    for (const k of Object.keys(this.weatherLayers)) {
      const s = this.weatherLayers[k];
      s.timer && s.timer.remove();
      s.scheduler && s.scheduler.remove();
      s.onResize && this.scale.off('resize', s.onResize);
      s.img && s.img.destroy();
    }
    this.weatherLayers = {};
  }

  toggleInventory() {
    if (this.activeDialog) return;
    this.inventoryOpen = !this.inventoryOpen;
    const overlay = document.getElementById('inventory-overlay');
    if (this.inventoryOpen) {
      overlay.classList.add('active');
      this.input.keyboard.enabled = false;
      this.input.keyboard.clearCaptures();
      this.refreshInventoryUI();
    } else {
      overlay.classList.remove('active');
      this.input.keyboard.enabled = true;
    }
  }

  refreshInventoryUI() {
    // Welle 34: Hotbar mit aktualisieren
    this.refreshHotbar();
    // Equipment-Slots (RimWorld-Style: 2-Spalten-Grid)
    const equipGrid = document.getElementById('inventory-equip-grid');
    equipGrid.innerHTML = '';
    for (const slot of EQUIP_SLOTS) {
      const equipped = this.inventory.find(it => it.equipped_slot === slot.key);
      const div = document.createElement('div');
      div.className = 'equip-slot';
      if (equipped) {
        const effQ = effectiveQuality(equipped);
        if (effQ && effQ !== 'normal') div.classList.add(effQ);
        const img = document.createElement('img');
        img.src = itemAssetPath(equipped);
        div.appendChild(img);
        const lbl = document.createElement('div');
        lbl.className = 'slot-label';
        lbl.textContent = slot.label;
        div.appendChild(lbl);
        const itemName = document.createElement('div');
        itemName.className = 'slot-item';
        const cfg = ITEM[equipped.kind] || {};
        itemName.textContent = equipped.unique_name || cfg.name || equipped.name || equipped.kind;
        div.appendChild(itemName);
        div.title = 'Klick zum Ablegen';
        div.addEventListener('click', () => this.unequipItem(equipped.id));
        div.addEventListener('mouseenter', (ev) => this.showItemTooltip(equipped, ev));
        div.addEventListener('mousemove',  (ev) => this.showItemTooltip(equipped, ev));
        div.addEventListener('mouseleave', () => this.hideItemTooltip());
      } else {
        div.classList.add('empty');
        const ph = document.createElement('div');
        ph.className = 'placeholder';
        ph.textContent = '∅';
        div.appendChild(ph);
        const lbl = document.createElement('div');
        lbl.className = 'slot-label';
        lbl.textContent = slot.label;
        div.appendChild(lbl);
      }
      equipGrid.appendChild(div);
    }

    // Stats-Panel unter Equipment
    this._refreshInventoryStats();
  }

  _refreshInventoryStats() {
    const el = document.getElementById('inventory-stats');
    if (!el) return;
    el.innerHTML = '';
    // ── 1. Vitals (HP/Mana/Hunger/Stamina) ───────────────────────────────
    const vitalRows = [
      ['❤️ HP',      `${this.myHp ?? '?'} / ${this.myMaxHp ?? '?'}`],
      ['💧 Mana',    `${this.myMana ?? '?'} / ${this.myMaxMana ?? '?'}`],
      ['🍗 Hunger',  `${this.myHunger ?? '?'} / ${this.myMaxHunger ?? '?'}`],
      ['⚡ Stamina', `${this.myStamina ?? '?'} / ${this.myMaxStamina ?? '?'}`],
    ];
    el.innerHTML += vitalRows.map(([k, v]) =>
      `<div class="stat-row"><span>${k}</span><span class="stat-val">${v}</span></div>`
    ).join('');

    // ── 1b. Kampf (Schaden / Verteidigung mit aktueller Ausrüstung) ──────
    const combatStats = this._computeCombatStats();
    el.innerHTML += `<div class="stat-section-title">Kampf</div>`;
    el.innerHTML += `<div class="stat-row" title="Basis-Waffenschaden × Quality + Skill + Crit-Boni">
      <span>⚔️ Schaden</span>
      <span class="stat-val">${combatStats.dmgMin} – ${combatStats.dmgMax}</span>
    </div>`;
    el.innerHTML += `<div class="stat-row" title="Waffenart und Eigenschaften">
      <span>🗡 Waffe</span>
      <span class="stat-val">${combatStats.weaponName}</span>
    </div>`;
    el.innerHTML += `<div class="stat-row" title="Reichweite in Tiles">
      <span>🎯 Reichweite</span>
      <span class="stat-val">${combatStats.range} Tiles</span>
    </div>`;
    el.innerHTML += `<div class="stat-row" title="Angriffe pro Sekunde (Multiplikator)">
      <span>⚡ Speed</span>
      <span class="stat-val">${combatStats.speed.toFixed(2)}×</span>
    </div>`;
    el.innerHTML += `<div class="stat-row" title="Kritische-Treffer-Chance">
      <span>💥 Krit</span>
      <span class="stat-val">${combatStats.critPct}%</span>
    </div>`;
    el.innerHTML += `<div class="stat-row" title="Summe Defense aus allen Rüstungs-Teilen + Affixe">
      <span>🛡️ Defense</span>
      <span class="stat-val">${combatStats.defense} <span class="stat-bonus">(-${combatStats.drPct}% DR)</span></span>
    </div>`;

    // ── 2. Attribute + Allokation (nur wenn statSheet vorhanden) ─────────
    const sheet = this.statSheet;
    if (sheet && sheet.attributes) {
      const unspent = sheet.unspent_points || 0;
      el.innerHTML += `<div class="stat-section-title">Attribute</div>`;
      if (unspent > 0) {
        el.innerHTML += `<div class="unspent-banner">✨ ${unspent} freie Punkte zum Verteilen</div>`;
      }
      const attrRows = Object.entries(sheet.attributes).map(([key, baseVal]) => {
        const lab = (sheet.labels && sheet.labels[key]) || [key, ''];
        const labText = Array.isArray(lab) ? lab[0] : lab;
        const tooltip = Array.isArray(lab) ? lab[1] : '';
        const alloc = (sheet.allocated && sheet.allocated[key]) || 0;
        const total = (sheet.totals && sheet.totals[key]) ?? baseVal + alloc;
        const allocStr = alloc > 0 ? `<span class="stat-bonus">+${alloc}</span>` : '';
        const plusDisabled = unspent <= 0 ? 'disabled' : '';
        const minusDisabled = alloc <= 0 ? 'disabled' : '';
        return `<div class="stat-row" title="${tooltip}">
          <span>${labText}</span>
          <span>
            <span class="stat-val">${total}</span> ${allocStr}
            <button class="alloc-btn minus" data-attr="${key}" data-n="-1" ${minusDisabled}>−</button>
            <button class="alloc-btn" data-attr="${key}" data-n="1" ${plusDisabled}>+</button>
          </span>
        </div>`;
      }).join('');
      el.innerHTML += attrRows;

      // ── 3. Resistances ───────────────────────────────────────────────────
      const r = sheet.resistances || {};
      const resistList = [
        ['🔥 Feuer',  r.fire || 0],
        ['❄️ Eis',    r.ice || 0],
        ['⚡ Blitz',  r.lightning || 0],
        ['☠️ Nekrot.', r.necrotic || 0],
        ['✨ Magie',  r.magic || 0],
      ];
      el.innerHTML += `<div class="stat-section-title">Resistenzen</div>`;
      el.innerHTML += resistList.map(([label, val]) => {
        const cls = val > 0 ? 'pos' : (val < 0 ? 'neg' : 'zero');
        const sign = val > 0 ? '+' : '';
        return `<div class="resist-row"><span>${label}</span>` +
               `<span class="resist-val ${cls}">${sign}${val}%</span></div>`;
      }).join('');

      // Click-Handler für Allocation-Buttons (Event-Delegation)
      el.querySelectorAll('.alloc-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const attr = btn.dataset.attr;
          const n = parseInt(btn.dataset.n, 10);
          if (!attr || isNaN(n)) return;
          this.ws.send(JSON.stringify({ type: 'allocate_attr', attr, n }));
        });
      });
    }
    // Inventar-Footer mit Gewicht (Welle 21)
    const equippedCount = this.inventory.filter(it => it.equipped_slot).length;
    const totalWeight = this.inventory.reduce((sum, it) => sum + itemWeight(it), 0);
    // Max-Gewicht: 80 Basis + 2 pro Stärke-Punkt
    const staerke = (sheet && sheet.totals && sheet.totals['stärke']) || 0;
    const maxWeight = 80 + staerke * 2;
    const overloaded = totalWeight > maxWeight;
    const weightColor = overloaded ? '#e85040'
                      : (totalWeight > maxWeight * 0.8 ? '#e8c860' : '#7aad6a');
    el.innerHTML += `<div class="stat-section-title">Beutel</div>`;
    el.innerHTML += `<div class="stat-row"><span>🎒 Slots</span><span class="stat-val">${this.inventory.length} (${equippedCount} ausgerüstet)</span></div>`;
    el.innerHTML += `<div class="stat-row" title="Basis 80 + 2 pro Stärke-Punkt">
      <span>⚖️ Gewicht</span>
      <span class="stat-val" style="color:${weightColor}">${totalWeight.toFixed(1)} / ${maxWeight}</span>
    </div>`;
    if (overloaded) {
      el.innerHTML += `<div style="color:#e85040;font-size:12px;text-align:center;padding:4px;">
        ⚠️ Überladen — drop items oder steigere Stärke
      </div>`;
    }
    // Re-attach handler — innerHTML+= killt vorherige listeners
    el.querySelectorAll('.alloc-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const attr = btn.dataset.attr;
        const n = parseInt(btn.dataset.n, 10);
        if (!attr || isNaN(n)) return;
        this.ws.send(JSON.stringify({ type: 'allocate_attr', attr, n }));
      });
    });

    // Welle 36: Beutel als Slot-Grid (40 Slots)
    const listDiv = document.getElementById('inventory-list');
    listDiv.innerHTML = '';
    const unequipped = this.inventory.filter(it => !it.equipped_slot);
    // Welle 21: Auto-wachsender Slot-Count damit Items nicht unsichtbar werden
    const SLOT_COUNT = Math.max(80, unequipped.length + 10);
    for (let i = 0; i < SLOT_COUNT; i++) {
      const slot = document.createElement('div');
      slot.className = 'inv-slot';
      const item = unequipped[i];
      if (!item) {
        slot.classList.add('inv-slot-empty');
        // Leerer Slot ist trotzdem Drop-Target für Hotbar→Inventar (= Slot leeren)
        this._dndAttach(slot, {
          onDrop: (src) => this._handleDndDrop(src, { to: 'inventory', slot: i }),
        });
        listDiv.appendChild(slot);
        continue;
      }
      // Besetzter Slot: Drag-Source (kind nach Hotbar ziehen) + Drop-Target
      this._dndAttach(slot, {
        dragData: () => ({ from: 'inventory', item_id: item.id, kind: item.kind }),
        onDrop:   (src) => this._handleDndDrop(src, { to: 'inventory', slot: i }),
      });
      const cfg = ITEM[item.kind] || {};
      const effQ = effectiveQuality(item);
      if (effQ && effQ !== 'normal') slot.classList.add(effQ);
      const img = document.createElement('img');
      img.src = itemAssetPath(item);
      slot.appendChild(img);
      // Quality-Icon top-left (nur bei expliziter Equipment-Quality)
      if (QUALITY_ICONS[item.quality]) {
        const q = document.createElement('div');
        q.className = 'inv-slot-quality';
        q.textContent = QUALITY_ICONS[item.quality];
        slot.appendChild(q);
      }
      // Count (nur wenn > 1)
      const qty = item.quantity || 1;
      if (qty > 1) {
        const c = document.createElement('div');
        c.className = 'inv-slot-count';
        c.textContent = qty;
        slot.appendChild(c);
      }
      // Welle 17: Wasser-Container-Charges als Badge unten-rechts
      if (isWaterContainer(item.kind)) {
        const ch = item.charges || 0;
        const cap = containerCapacity(item.kind);
        const c = document.createElement('div');
        c.className = 'inv-slot-count';
        c.style.cssText = 'background: rgba(40,80,140,0.85); color: #ade8ff;';
        c.textContent = `💧${ch}/${cap}`;
        slot.appendChild(c);
      }
      // Hover-Tooltip
      slot.addEventListener('mouseenter', (ev) => this.showItemTooltip(item, ev));
      slot.addEventListener('mousemove',  (ev) => this.showItemTooltip(item, ev));
      slot.addEventListener('mouseleave', () => this.hideItemTooltip());
      // Linksklick: kontext-passende Aktion (use/equip/learn/cast)
      slot.addEventListener('click', () => {
        if (cfg.slot) this.equipItem(item.id);
        else if (cfg.category === 'consumable' || cfg.category === 'food') this.useItem(item.id);
        else if (cfg.category === 'magic') {
          // Wenn schon gelernt → casten; sonst → lernen
          if ((this.learnedSpells || []).includes(item.kind)) {
            this.castSpell(item.id);
          } else {
            this.ws.send(JSON.stringify({ type: 'learn_spell', item_id: item.id }));
          }
        }
        else this.showEvent(`${cfg.name || item.kind} (kein Effekt)`);
      });
      // Rechtsklick: persistenter Tooltip mit Beschreibung + Aktions-Menü
      slot.addEventListener('contextmenu', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        this.pinItemTooltip(item, ev);
      });
      // Shift+Klick: Drop
      slot.addEventListener('auxclick', (ev) => {
        if (ev.button === 1) {
          ev.preventDefault(); this.dropItem(item.id);
        }
      });
      listDiv.appendChild(slot);
    }
  }

  equipItem(itemId) {
    this.ws.send(JSON.stringify({ type: 'equip_item',   item_id: itemId }));
  }
  unequipItem(itemId) {
    this.ws.send(JSON.stringify({ type: 'unequip_item', item_id: itemId }));
  }
  useItem(itemId) {
    this.ws.send(JSON.stringify({ type: 'use_item',     item_id: itemId }));
  }
  dropItem(itemId) {
    this.ws.send(JSON.stringify({ type: 'drop_item',    item_id: itemId }));
  }
  castSpell(itemId) {
    this.ws.send(JSON.stringify({ type: 'cast_spell',   item_id: itemId }));
  }

  loadNPCs(npcList) {
    for (const id of Object.keys(this.npcs)) {
      const n = this.npcs[id];
      if (n.tween) n.tween.stop();
      n.container.destroy();
    }
    this.npcs = {};
    for (const npc of npcList) this.spawnNPCSprite(npc);
  }

  // Resolver: Sprite-Key für einen NPC — variant überschreibt den kind-default,
  // fällt zurück auf cfg.sprite wenn die variant-texture nicht geladen ist.
  // Welle 19: weiteres Fallback auf 'monster_unknown' wenn legacy-mob-Sprite
  // entfernt wurde (commit 1fb41c5).
  _npcSpriteKey(npc) {
    const cfg = NPC_SPRITE[npc.kind] || NPC_SPRITE.wanderer;
    // sprite_variant (z.B. bandit_axe) hat Vorrang — keine Animation für Variants.
    if (npc.sprite_variant) {
      const key = `npc_${npc.sprite_variant}`;
      if (this.textures.exists(key)) return key;
    }
    // Welle 23: wenn Walk-Cycle-Animation existiert, start mit anim-idle.
    // _updateWalkFrame swappt dann durch walk_<dir>_<frame> bei Bewegung.
    const chaKey = `cha_${npc.kind}_idle_1`;
    if (this.textures.exists(chaKey)) return chaKey;
    const mobKey = `mob_${npc.kind}_idle_1`;
    if (this.textures.exists(mobKey)) return mobKey;
    // Fallback: statisches NPC- bzw. Monster-Sprite.
    if (cfg.sprite && this.textures.exists(cfg.sprite)) return cfg.sprite;
    return 'monster_unknown';
  }

  spawnNPCSprite(npc) {
    if (this.npcs[npc.id]) return;
    const cfg = NPC_SPRITE[npc.kind] || NPC_SPRITE.wanderer;
    const cx = npc.x * TILE_SIZE + TILE_SIZE / 2;
    const cy = npc.y * TILE_SIZE + TILE_SIZE / 2;

    const shadow = this.add.image(0, 14, 'fx_shadow')
      .setOrigin(0.5)
      .setAlpha(0.55);

    const body = this.add.image(0, 0, this._npcSpriteKey(npc)).setOrigin(0.5, 0.55);
    body.setDisplaySize(TILE_SIZE * 0.95, TILE_SIZE * 0.95);
    body.setTint(cfg.tint);

    const label = this.add.text(0, -TILE_SIZE * 0.55, npc.name.substr(0, 20), {
      fontSize: '10px', color: '#ffeec0', stroke: '#000', strokeThickness: 2,
    }).setOrigin(0.5);

    // Mental-State-Icon (über NPC) — Welle 4
    const moodIcon = this.add.text(0, -TILE_SIZE * 0.78, '', {
      fontSize: '13px',
    }).setOrigin(0.5);
    // Welle 20: Goal-Icon links vom Mood-Icon (zeigt Tagesplan: 💤/⚒️/🍞/💬)
    const goalIcon = this.add.text(-12, -TILE_SIZE * 0.78, '', {
      fontSize: '13px',
    }).setOrigin(0.5);
    // Welle 23: Quest-Marker rechts vom Mood-Icon. Wird via _setNPCQuestMarker
    // dynamisch befüllt (❓ = Offer verfügbar, ❗ = Turn-In wartet).
    const questIcon = this.add.text(12, -TILE_SIZE * 0.78, '', {
      fontSize: '15px',
    }).setOrigin(0.5);

    const container = this.add.container(cx, cy,
      [shadow, body, label, moodIcon, goalIcon, questIcon]);
    container.setDepth(3);

    this.npcs[npc.id] = {
      container, body, shadow, label, moodIcon, goalIcon, questIcon,
      speech: null,    // ephemeral speech bubble (created on demand)
      tween: null,
      tileX: npc.x, tileY: npc.y,
      npc,  // raw data für späteren Dialog-Kontext
    };
    this.refreshNPCMood(npc.id);
    // Welle 23: Quest-Status nachfragen falls Friendly-NPC
    if (npc.kind && !CREATURE_KINDS.has(npc.kind)) {
      this._queryNPCQuests(npc.id);
    }
  }

  _queryNPCQuests(npcId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    try {
      this.ws.send(JSON.stringify({type: 'query_npc_quests', npc_id: npcId}));
    } catch (e) { /* ignore */ }
  }

  _setNPCQuestMarker(npcId, marker) {
    const entry = this.npcs[npcId];
    if (!entry || !entry.questIcon) return;
    entry.questIcon.setText(marker || '');
    if (marker) {
      entry.questIcon.setColor(marker === '❗' ? '#ffd060' : '#fff080');
    }
  }

  _updateNPCGoalIcon(npcId, emoji) {
    const entry = this.npcs[npcId];
    if (!entry || !entry.goalIcon) return;
    const prevEmoji = entry.goalIcon.text;
    entry.goalIcon.setText(emoji || '');
    // Welle 50: kurze thought_bubble_work, wenn NPC zu „arbeitet"-Zustand wechselt.
    // 1× Loop-Cycle (~1.2s) reicht als Übergangs-Indikator.
    if (emoji === '⚒️' && prevEmoji !== '⚒️' && entry.container) {
      const bubble = this.add.sprite(20, -TILE_SIZE * 0.85,
                                     'wp_thought_bubble_work', 0)
        .setOrigin(0.5, 0.5)
        .setDisplaySize(TILE_SIZE * 0.5, TILE_SIZE * 0.5)
        .setAlpha(0.85);
      entry.container.add(bubble);
      if (this.anims.exists('wp_thought_bubble_work')) bubble.play('wp_thought_bubble_work');
      // Nach ~1.5s wieder weg (Loop läuft währenddessen)
      this.time.delayedCall(1500, () => {
        this.tweens.add({
          targets: bubble, alpha: 0, duration: 300,
          onComplete: () => bubble.destroy(),
        });
      });
    }
  }

  _showNPCSpeech(npcId, text) {
    const entry = this.npcs[npcId];
    if (!entry || !entry.container) return;
    // Vorhandene Bubble destroyen falls noch da
    if (entry.speech) {
      if (entry.speech.timer) clearTimeout(entry.speech.timer);
      entry.speech.bg.destroy();
      entry.speech.txt.destroy();
      if (entry.speech.icon) entry.speech.icon.destroy();
      entry.speech = null;
    }
    // Bubble: weißer Text, dunkler bg, oberhalb des NPCs
    const txt = this.add.text(0, -TILE_SIZE * 1.05, text, {
      fontFamily: 'monospace',
      fontSize: '12px',
      color:    '#fff',
      backgroundColor: 'rgba(20,18,14,0.85)',
      padding:  { x: 6, y: 3 },
      align:    'center',
      wordWrap: { width: 180, useAdvancedWrap: true },
    }).setOrigin(0.5, 1);
    entry.container.add(txt);
    // Welle 50: Speech-Bubble-Icon (animiert) als „Sprecher-Marker" über Text
    const variant = (() => {
      if (/\?/.test(text)) return 'speech_bubble_question';
      if (/!/.test(text)) return 'speech_bubble_alert';
      if (/(münze|geld|preis|gold|silber|salz|markt|handel|kost)/i.test(text))
        return 'speech_bubble_trade';
      return 'speech_bubble_talk';
    })();
    let icon = null;
    if (this.anims.exists(`wp_${variant}`)) {
      icon = this.add.sprite(0, -TILE_SIZE * 1.6, `wp_${variant}`, 0)
        .setOrigin(0.5, 0.5)
        .setDisplaySize(TILE_SIZE * 0.5, TILE_SIZE * 0.5)
        .setAlpha(0.9);
      icon.play(`wp_${variant}`);
      entry.container.add(icon);
    }
    entry.speech = { txt, bg: txt, icon, timer: null };
    // 6 Sek sichtbar, dann verblassen
    entry.speech.timer = setTimeout(() => {
      if (!entry.speech) return;
      const targets = [entry.speech.txt];
      if (entry.speech.icon) targets.push(entry.speech.icon);
      this.tweens.add({
        targets, alpha: 0, duration: 400,
        onComplete: () => {
          if (entry.speech) {
            entry.speech.txt.destroy();
            if (entry.speech.icon) entry.speech.icon.destroy();
            entry.speech = null;
          }
        },
      });
    }, 6000);
  }

  refreshNPCMood(npcId) {
    const entry = this.npcs[npcId];
    if (!entry || !entry.moodIcon) return;
    const state = entry.npc?.mental_state || 'normal';
    const ICON = { normal: '', sad: '😢', fleeing: '😨', berserk: '💢' };
    entry.moodIcon.setText(ICON[state] || '');
  }

  // Beim init: Chronik mit vorhandenen Events füllen (älteste zuerst, da scroll-down zeigt neueste)
  loadInitialEvents(events) {
    const list = document.getElementById('chronik-list');
    list.innerHTML = '';
    for (const ev of events) this.addEventToChronik(ev, false);
    list.scrollTop = list.scrollHeight;
  }

  addEventToChronik(ev, autoscroll = true) {
    const list = document.getElementById('chronik-list');
    // Welle 20: tier ist optional (im neuen Format als separates Feld), fällt
    // auf ev.kind zurück für Legacy-Events
    const tier = ev.tier || ev.kind;
    const icon = EVENT_ICON[tier] || EVENT_ICON[ev.kind] || '•';
    const tierClass = TIER_CLASS[tier] || '';
    const div = document.createElement('div');
    div.className = `ev ${tierClass}`;
    div.innerHTML = `
      <div class="ev-title">${icon} ${this.escapeHtml(ev.title)}</div>
      <div class="ev-body">${this.escapeHtml(ev.body)}</div>
      <div class="ev-meta">${relativeTime(ev.created_at)}</div>
    `;
    list.appendChild(div);
    if (autoscroll) list.scrollTop = list.scrollHeight;
  }

  showStoryEvent(ev) {
    const tier = ev.tier || ev.kind;
    const icon = EVENT_ICON[tier] || EVENT_ICON[ev.kind] || '•';
    const tierClass = TIER_CLASS[tier] || '';
    const el = document.createElement('div');
    el.className = `story-toast ${tierClass}`;
    el.innerHTML = `
      <div class="st-title">${icon} ${this.escapeHtml(ev.title)}</div>
      <div>${this.escapeHtml(ev.body)}</div>
    `;
    document.body.appendChild(el);
    // Bosse/Cataclysm bleiben länger sichtbar
    const ttl = (tier === 'boss' || tier === 'cataclysm') ? 18000 : 10000;
    setTimeout(() => el.remove(), ttl);
  }

  escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  drawStructures() {
    // Full-redraw: alle bestehenden Sprites entfernen, dann neu zeichnen
    for (const s of Object.values(this.floorSprites))  s.destroy();
    for (const s of Object.values(this.structSprites)) {
      if (s._embers) s._embers.destroy();
      s.destroy();
    }
    for (const s of Object.values(this.doorFrameSprites || {})) s.destroy();
    this.floorSprites = {};
    this.structSprites = {};
    this.doorFrameSprites = {};
    // Floors zuerst (depth 0), dann Objects (depth 1) → Objects oben drauf
    for (const s of Object.values(this.floors))     this.addStructureSprite(s, false);
    for (const s of Object.values(this.structures)) this.addStructureSprite(s, false);
    // Wand-/Fence-Orientierungen ausrichten
    for (const s of Object.values(this.structures)) {
      if (s.type === 'wall')  this.updateWallOrientation(s.x, s.y);
      if (s.type === 'fence') this.updateFenceOrientation(s.x, s.y);
    }
  }

  addStructureSprite(s, refreshNeighbors = true) {
    const cfg = STRUCTURE[s.type];
    if (!cfg) return;
    const cx = s.x * TILE_SIZE + TILE_SIZE / 2;
    const cy = s.y * TILE_SIZE + TILE_SIZE / 2;

    // Sprite-Key bestimmen — material-spezifisch für walls/floor, fix für andere
    const material = s.material || 'stone';
    let initialKey;
    if (s.type === 'wall') {
      initialKey = this.pickWallSprite(material, 0);
    } else if (s.type === 'floor') {
      initialKey = this.textures.exists(`floor_${material}`)
        ? `floor_${material}` : cfg.sprite;
    } else {
      initialKey = cfg.sprite;
    }

    // Tür-Rahmen: bei doors zuerst ein Wall-Sprite hinten dran, damit die
    // Tür sichtbar in der Wand sitzt. Orientation aus Nachbar-Wänden.
    const isDoor = s.type.startsWith('door_');
    let doorRotation = 0;  // wird unten am Tür-Sprite angewandt
    if (isDoor) {
      const wallMat = s.material || 'wood';
      const isWallish = (t) => t === 'wall'
                            || (t && (t.startsWith('door_') || t.startsWith('garden_gate_')));
      let mask = 0;
      if (isWallish(this.structures[`${s.x},${s.y - 1}`]?.type)) mask |= 1;
      if (isWallish(this.structures[`${s.x + 1},${s.y}`]?.type)) mask |= 2;
      if (isWallish(this.structures[`${s.x},${s.y + 1}`]?.type)) mask |= 4;
      if (isWallish(this.structures[`${s.x - 1},${s.y}`]?.type)) mask |= 8;
      const variant = WALL_MASK_TO_VARIANT[mask] || 'straight_ns';
      const wallKey = this.textures.exists(`wall_${wallMat}_${variant}`)
        ? `wall_${wallMat}_${variant}`
        : `wall_stone_${variant}`;
      const frame = this.add.image(cx, cy, wallKey).setOrigin(0.5);
      frame.setDisplaySize(TILE_SIZE, TILE_SIZE);
      frame.setDepth(0.9);   // unter dem Tür-Sprite (1.0), über Floor (0.5)
      this.doorFrameSprites[`${s.x},${s.y}`] = frame;
      // Tür-Sprites sind nativ horizontal (E-W) gezeichnet — bei vertikalen
      // Wänden (N-S) Sprite um 90° drehen, damit das Türblatt zur Wand passt.
      const isVerticalWall = variant === 'straight_ns'
                          || variant === 'end_n' || variant === 'end_s';
      if (isVerticalWall) doorRotation = 90;
    }

    const img = this.add.image(cx, cy, initialKey).setOrigin(0.5);
    // Größen-Override für Strukturen die größer als ein Tile aussehen sollen
    // (Zelte, Schiffe, große Statuen). Default = 1.0 × TILE_SIZE.
    const structScale = STRUCTURE_DISPLAY_SCALE[s.type] || 1.0;
    img.setDisplaySize(TILE_SIZE * structScale, TILE_SIZE * structScale);
    // User-gesetzte Rotation hat Vorrang. Nur wenn keine (rotation==0) UND es ist
    // eine Tür → fällt's auf die automatische Door-Wand-Orientation zurück.
    const userRot = Number(s.rotation || 0);
    if (userRot) {
      img.setAngle(userRot);
    } else if (doorRotation) {
      img.setAngle(doorRotation);
    }
    // Floor liegt UNTER Objects (zwei separate Sprite-Maps + Depth-Levels)
    const isFloor = (s.layer === 'floor') || (s.type === 'floor');
    if (isFloor) {
      img.setDepth(0.5);    // über Tiles (0), unter Objects (1)
      this.floorSprites[`${s.x},${s.y}`] = img;
    } else {
      img.setDepth(1);      // über Floors, unter Charakteren (3)
      this.structSprites[`${s.x},${s.y}`] = img;
    }

    // Welle 50: Lagerfeuer bekommt einen leise loopenden Ember-Overlay
    if (s.type === 'campfire') {
      img._embers = this.playOverlayAnim('campfire_embers', cx, cy - TILE_SIZE * 0.25,
                                         { scale: 0.9, depth: 4, alpha: 0.85 });
    }

    if (s.type === 'wall') {
      this.updateWallOrientation(s.x, s.y);
      if (refreshNeighbors) {
        // Direkte 4-Nachbarn — kanonisch
        this.updateWallOrientation(s.x - 1, s.y);
        this.updateWallOrientation(s.x + 1, s.y);
        this.updateWallOrientation(s.x, s.y - 1);
        this.updateWallOrientation(s.x, s.y + 1);
        // Defensive: zweite Welle einen Frame später falls die erste
        // Aktualisierung wegen schnellem Platzieren übersprungen wurde.
        // (Verhindert "Wände stehen einzeln nebeneinander" bei Schnellbau)
        this.time.delayedCall(30, () => {
          this.updateWallOrientation(s.x, s.y);
          this.updateWallOrientation(s.x - 1, s.y);
          this.updateWallOrientation(s.x + 1, s.y);
          this.updateWallOrientation(s.x, s.y - 1);
          this.updateWallOrientation(s.x, s.y + 1);
        });
      }
    } else if (s.type === 'fence') {
      this.updateFenceOrientation(s.x, s.y);
      if (refreshNeighbors) {
        this.updateFenceOrientation(s.x - 1, s.y);
        this.updateFenceOrientation(s.x + 1, s.y);
        this.updateFenceOrientation(s.x, s.y - 1);
        this.updateFenceOrientation(s.x, s.y + 1);
      }
    } else if (isDoor || s.type.startsWith('garden_gate_')) {
      // Türen/Tore zählen als Wall-Connector — Nachbarn neu ausrichten damit
      // angrenzende Mauer-Ecken/Endungen korrekt bleiben.
      if (refreshNeighbors) {
        this.updateWallOrientation(s.x - 1, s.y);
        this.updateWallOrientation(s.x + 1, s.y);
        this.updateWallOrientation(s.x, s.y - 1);
        this.updateWallOrientation(s.x, s.y + 1);
      }
    }
    // Welle 25: HP-Damage-Visualisierung
    this._refreshStructureHpVisual(s);
  }

  // Rote Tint bei < 30% HP + HP-Bar über Struktur wenn dur < max.
  _refreshStructureHpVisual(s) {
    if (s.max_durability == null || s.durability == null) return;
    const max = s.max_durability, cur = s.durability;
    if (max <= 0 || cur >= max) {
      // Heile — tint cleanen + HP-Bar entfernen
      const sprite = this.structSprites[`${s.x},${s.y}`] || this.floorSprites[`${s.x},${s.y}`];
      if (sprite) sprite.clearTint();
      this._removeStructureHpBar(s.x, s.y);
      return;
    }
    const sprite = this.structSprites[`${s.x},${s.y}`] || this.floorSprites[`${s.x},${s.y}`];
    if (sprite) {
      // Damage-Tint: 30% HP = sichtbar rot, 100% HP = nicht getintet
      const pct = cur / max;
      if (pct < 0.3) {
        sprite.setTint(0xff5050);
      } else if (pct < 0.6) {
        sprite.setTint(0xffaa70);
      } else {
        sprite.clearTint();
      }
    }
    // HP-Bar darüber
    this._renderStructureHpBar(s);
  }

  _renderStructureHpBar(s) {
    const key = `${s.x},${s.y}`;
    if (!this._structHpBars) this._structHpBars = {};
    let bar = this._structHpBars[key];
    const cx = s.x * TILE_SIZE + TILE_SIZE / 2;
    const cy = s.y * TILE_SIZE - 4;
    const w = TILE_SIZE * 0.85;
    const h = 4;
    const pct = Math.max(0, Math.min(1, s.durability / s.max_durability));
    if (!bar) {
      const bg = this.add.rectangle(cx, cy, w, h, 0x000000, 0.65).setDepth(2.5);
      const fg = this.add.rectangle(cx - w/2, cy, w * pct, h, 0x60c060)
        .setOrigin(0, 0.5).setDepth(2.6);
      bar = { bg, fg, w };
      this._structHpBars[key] = bar;
    } else {
      bar.fg.width = bar.w * pct;
    }
    // Farbe: grün > orange > rot
    bar.fg.fillColor = pct > 0.5 ? 0x60c060 : (pct > 0.25 ? 0xe8a040 : 0xe04030);
  }

  _removeStructureHpBar(x, y) {
    if (!this._structHpBars) return;
    const key = `${x},${y}`;
    const bar = this._structHpBars[key];
    if (bar) {
      bar.bg.destroy(); bar.fg.destroy();
      delete this._structHpBars[key];
    }
  }

  removeStructureSprite(x, y, layer = 'object') {
    const key = `${x},${y}`;
    if (layer === 'floor') {
      if (this.floorSprites[key]) {
        this.floorSprites[key].destroy();
        delete this.floorSprites[key];
      }
      return;
    }
    if (this.structSprites[key]) {
      const ss = this.structSprites[key];
      if (ss._embers) ss._embers.destroy();
      ss.destroy();
      delete this.structSprites[key];
    }
    if (this.doorFrameSprites && this.doorFrameSprites[key]) {
      this.doorFrameSprites[key].destroy();
      delete this.doorFrameSprites[key];
    }
    // Nachbar-Wände/Fences neu ausrichten, jetzt wo diese weg ist
    this.updateWallOrientation(x - 1, y);
    this.updateWallOrientation(x + 1, y);
    this.updateWallOrientation(x, y - 1);
    this.updateWallOrientation(x, y + 1);
    this.updateFenceOrientation(x - 1, y);
    this.updateFenceOrientation(x + 1, y);
    this.updateFenceOrientation(x, y - 1);
    this.updateFenceOrientation(x, y + 1);
  }

  shakeStructure(x, y) {
    const sprite = this.structSprites[`${x},${y}`];
    if (!sprite) return;
    const origX = sprite.x;
    this.tweens.add({
      targets: sprite,
      x: origX + 3,
      duration: 50,
      yoyo: true,
      repeat: 1,
      onComplete: () => sprite.x = origX,
    });
  }

  updateWallOrientation(x, y) {
    const s = this.structures[`${x},${y}`];
    if (!s || s.type !== 'wall') return;
    const img = this.structSprites[`${x},${y}`];
    if (!img) return;

    // Türen und Tore zählen als Wand-Nachbarn, damit Ecken neben einer Tür
    // korrekt als corner_* (nicht als end_*) gerendert bleiben.
    const isConnector = (t) => t === 'wall'
                            || (t && t.startsWith('door_'))
                            || (t && t.startsWith('garden_gate_'));
    let mask = 0;
    if (isConnector(this.structures[`${x},${y - 1}`]?.type)) mask |= 1;  // N
    if (isConnector(this.structures[`${x + 1},${y}`]?.type)) mask |= 2;  // E
    if (isConnector(this.structures[`${x},${y + 1}`]?.type)) mask |= 4;  // S
    if (isConnector(this.structures[`${x - 1},${y}`]?.type)) mask |= 8;  // W

    const material = s.material || 'stone';
    img.setTexture(this.pickWallSprite(material, mask));
    img.setAngle(0);
  }

  pickWallSprite(material, mask) {
    const variant = WALL_MASK_TO_VARIANT[mask] || 'straight_ns';
    const primary = `wall_${material}_${variant}`;
    if (this.textures.exists(primary)) return primary;
    // Fallback: Stone-Variante
    const stone = `wall_stone_${variant}`;
    if (this.textures.exists(stone)) return stone;
    // Legacy-Fallback
    return 'struct_wall';
  }

  updateFenceOrientation(x, y) {
    const s = this.structures[`${x},${y}`];
    if (!s || s.type !== 'fence') return;
    const img = this.structSprites[`${x},${y}`];
    if (!img) return;
    // Mask wie bei Walls — Fences connecten auch an garden_gates
    const isConnector = (t) => t === 'fence'
                            || t === 'garden_gate_ew_closed' || t === 'garden_gate_ew_open'
                            || t === 'garden_gate_ns_closed' || t === 'garden_gate_ns_open';
    let mask = 0;
    if (isConnector(this.structures[`${x},${y - 1}`]?.type)) mask |= 1;  // N
    if (isConnector(this.structures[`${x + 1},${y}`]?.type)) mask |= 2;  // E
    if (isConnector(this.structures[`${x},${y + 1}`]?.type)) mask |= 4;  // S
    if (isConnector(this.structures[`${x - 1},${y}`]?.type)) mask |= 8;  // W
    const variant = WALL_MASK_TO_VARIANT[mask] || 'straight_ns';
    const key = `fence_${variant}`;
    if (this.textures.exists(key)) img.setTexture(key);
  }

  drawWorld() {
    // Alle bekannten Chunks rendern
    for (const key of Object.keys(this.chunks)) {
      const [cx, cy] = key.split(',').map(Number);
      this.drawChunkTiles(cx, cy);
    }
  }

  drawMinimap() {
    const canvas = document.getElementById('minimap');
    const ctx    = canvas.getContext('2d');
    if (!this.mySprite) return;
    // Welle 21: Größere Minimap zeigt jetzt ~64×44 Tiles (statt 30×20 = 4× Sichtbarkeit)
    const VIEW_W = 64, VIEW_H = 44;
    const scaleX = canvas.width  / VIEW_W;
    const scaleY = canvas.height / VIEW_H;
    const ox = this.myTileX - VIEW_W / 2;
    const oy = this.myTileY - VIEW_H / 2;
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let dy = 0; dy < VIEW_H; dy++) {
      for (let dx = 0; dx < VIEW_W; dx++) {
        const wx = Math.floor(ox + dx);
        const wy = Math.floor(oy + dy);
        const t = this.tileAt(wx, wy);
        if (t === null) continue;
        const cfg = TILE_BY_ID[t];
        if (!cfg) continue;
        ctx.fillStyle = cfg.miniColor;
        ctx.fillRect(Math.floor(dx * scaleX), Math.floor(dy * scaleY),
                     Math.ceil(scaleX), Math.ceil(scaleY));
      }
    }

    // NPCs
    const dotSize = Math.max(3, Math.floor(Math.min(scaleX, scaleY)));
    for (const id of Object.keys(this.npcs)) {
      const n = this.npcs[id];
      ctx.fillStyle = CREATURE_KINDS.has(n.npc.kind) ? '#e84040' : '#ffe070';
      const px = (n.tileX - ox) * scaleX;
      const py = (n.tileY - oy) * scaleY;
      if (px >= 0 && px < canvas.width && py >= 0 && py < canvas.height) {
        ctx.fillRect(Math.floor(px) - 1, Math.floor(py) - 1, dotSize, dotSize);
      }
    }
    for (const id of Object.keys(this.otherPlayers)) {
      const p = this.otherPlayers[id];
      ctx.fillStyle = '#a0c8ff';
      const px = (p.tileX - ox) * scaleX;
      const py = (p.tileY - oy) * scaleY;
      if (px >= 0 && px < canvas.width && py >= 0 && py < canvas.height) {
        ctx.fillRect(Math.floor(px) - 1, Math.floor(py) - 1, dotSize, dotSize);
      }
    }

    // Welle 21: Event-Marker — bunte pulsierende Punkte mit Richtungspfeil
    // wenn der Marker außerhalb des Sichtfelds liegt.
    if (this.eventMarkers && this.eventMarkers.length > 0) {
      const now = Date.now();
      this.eventMarkers = this.eventMarkers.filter(m => m.expires_at > now);
      const pulse = (Math.sin(now / 200) + 1) / 2;   // 0..1
      const cx = canvas.width / 2, cy = canvas.height / 2;
      for (const m of this.eventMarkers) {
        const px = (m.x - ox) * scaleX;
        const py = (m.y - oy) * scaleY;
        const inView = px >= 0 && px < canvas.width && py >= 0 && py < canvas.height;
        ctx.fillStyle = m.color || '#ffe070';
        if (inView) {
          // Pulsierender Marker am tatsächlichen Tile
          const r = 4 + pulse * 3;
          ctx.beginPath();
          ctx.arc(px, py, r, 0, Math.PI * 2);
          ctx.fill();
          // Border
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          // Pfeil am Rand der Minimap in Richtung Marker
          const dx = px - cx, dy = py - cy;
          const len = Math.hypot(dx, dy) || 1;
          const ex = cx + (dx / len) * (Math.min(cx, cy) - 6);
          const ey = cy + (dy / len) * (Math.min(cx, cy) - 6);
          const ang = Math.atan2(dy, dx);
          ctx.save();
          ctx.translate(ex, ey);
          ctx.rotate(ang);
          ctx.fillStyle = m.color || '#ffe070';
          ctx.beginPath();
          ctx.moveTo(6, 0);
          ctx.lineTo(-4, -4);
          ctx.lineTo(-4, 4);
          ctx.closePath();
          ctx.fill();
          ctx.strokeStyle = '#000';
          ctx.lineWidth = 0.8;
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // Eigener Spieler: zentral
    ctx.fillStyle = '#000';
    ctx.fillRect(canvas.width / 2 - 2, canvas.height / 2 - 2, 5, 5);
    ctx.fillStyle = '#fff';
    ctx.fillRect(canvas.width / 2 - 1, canvas.height / 2 - 1, 3, 3);
  }

  // Player-Sprite: Container mit shadow+body als Kinder. So kann der ganze
  // Container per Tween smooth zwischen Tile-Positionen animiert werden.
  // Welle 32: Facing — flip horizontal + leichter tilt
  _applyFacing(entry, vx, vy) {
    if (!entry || !entry.body) return;
    if (vx < 0) entry.body.flipX = true;
    else if (vx > 0) entry.body.flipX = false;
    // Leichter tilt: nach unten 0°, nach oben −3°, sideways 0°
    if (vy < 0) entry.body.setRotation(-0.05);
    else if (vy > 0) entry.body.setRotation(0.05);
    else entry.body.setRotation(0);
  }

  spawnSprite(id, tileX, tileY, isMe) {
    const px = tileX * TILE_SIZE + TILE_SIZE / 2;
    const py = tileY * TILE_SIZE + TILE_SIZE / 2;

    const shadow = this.add.image(0, 14, 'fx_shadow')
      .setOrigin(0.5)
      .setAlpha(0.55);

    // Welle 23: Wenn Player ein Preset gewählt hat → preset-sprite,
    // sonst Walk-Animation, sonst char_player Fallback.
    let startKey = 'char_player';
    if (isMe && this.myPreset && this.textures.exists(`preset_${this.myPreset}`)) {
      startKey = `preset_${this.myPreset}`;
    } else if (this.textures.exists('player_walk_down_1')) {
      startKey = 'player_walk_down_1';
    }
    const body = this.add.image(0, 0, startKey).setOrigin(0.5, 0.55);
    body.setDisplaySize(TILE_SIZE * 0.95, TILE_SIZE * 0.95);

    if (!isMe) body.setTint(0xb8c8ff);

    const container = this.add.container(px, py, [shadow, body]);
    container.setDepth(3);

    return {
      container, body, shadow, label: null, tween: null,
      facing: 'down', walkFrame: 0, walkTimer: 0, moving: false,
      isPlayer: true,
    };
  }

  // Welle 40: Walk-Animation update — vom Pixel-Movement aufgerufen
  _updateWalkFrame(entry, vx, vy, delta) {
    if (!entry || !entry.body) return;
    // Reset hängengebliebene Transformations-States
    entry.body.flipX = false;
    entry.body.setRotation(0);
    // Animation-Prefix wählen:
    //   Player    → 'player' (assets/animations/player/walk_*)
    //   NPC kind  → 'cha_<kind>' wenn /animations/characters/<kind>/ existiert
    //   Monster   → 'mob_<kind>' wenn /animations/monsters/<kind>/ existiert
    // Wenn Variant (z.B. bandit_axe) → keine Animation (Variant ist statisch).
    // Welle 23: Player mit Preset → keine Animation, Preset-Sprite bleibt.
    let prefix = null;
    if (entry.isPlayer && !this.myPreset) {
      prefix = 'player';
    } else if (entry.npc && !entry.npc.sprite_variant) {
      const k = entry.npc.kind;
      if (this.textures.exists(`cha_${k}_idle_1`)) prefix = `cha_${k}`;
      else if (this.textures.exists(`mob_${k}_idle_1`)) prefix = `mob_${k}`;
    }
    if (!prefix) return;  // kein animations-fähiger Sprite — Texture unverändert
    if (vx === 0 && vy === 0) {
      // Idle
      entry.moving = false;
      entry.walkTimer = 0;
      // Player: idle = walk_<dir>_1 (Stand-Frame); NPC/Monster: idle_1.
      const key = entry.isPlayer
        ? `player_walk_${entry.facing || 'down'}_1`
        : `${prefix}_idle_1`;
      if (this.textures.exists(key)) {
        entry.body.setTexture(key);
        entry.body.setDisplaySize(TILE_SIZE * 0.95, TILE_SIZE * 0.95);
      }
      return;
    }
    // Richtung wählen (größere Achse gewinnt)
    let dir = entry.facing || 'down';
    if (Math.abs(vx) >= Math.abs(vy)) {
      dir = vx > 0 ? 'right' : (vx < 0 ? 'left' : dir);
    } else {
      dir = vy > 0 ? 'down' : 'up';
    }
    entry.facing = dir;
    entry.moving = true;
    // Frame alle 180 ms toggeln
    entry.walkTimer = (entry.walkTimer || 0) + (delta || 16);
    if (entry.walkTimer >= 180) {
      entry.walkTimer = 0;
      entry.walkFrame = entry.walkFrame === 1 ? 2 : 1;
    }
    const frame = entry.walkFrame || 1;
    const key = `${prefix}_walk_${dir}_${frame}`;
    if (this.textures.exists(key)) {
      entry.body.setTexture(key);
      entry.body.setDisplaySize(TILE_SIZE * 0.95, TILE_SIZE * 0.95);
    }
  }

  movePlayerSmooth(p, tileX, tileY, dx = 0) {
    // Linearer Tween für andere Entitäten — interpoliert zwischen Server-Updates
    const px = tileX * TILE_SIZE + TILE_SIZE / 2;
    const py = tileY * TILE_SIZE + TILE_SIZE / 2;
    // Welle 40: Walk-Frame-Update basierend auf Bewegungsrichtung
    const dx2 = px - p.container.x;
    const dy2 = py - p.container.y;
    this._updateWalkFrame(p, dx2, dy2, 200);
    // Nach ein paar Frames auf idle zurück
    if (p._walkResetTimer) clearTimeout(p._walkResetTimer);
    p._walkResetTimer = setTimeout(() => {
      this._updateWalkFrame(p, 0, 0, 0);
    }, 240);
    if (p.tween) p.tween.stop();
    p.tween = this.tweens.add({
      targets:  p.container,
      x:        px,
      y:        py,
      duration: 220,
      ease:     'Linear',
    });
  }

  // Server-getriggerter Position-Snap (z.B. Knockback, Teleport, Korrektur)
  setLocalPositionFromTile(tileX, tileY) {
    this.myTileX = tileX;
    this.myTileY = tileY;
    this.myPx = tileX * TILE_SIZE + TILE_SIZE / 2;
    this.myPy = tileY * TILE_SIZE + TILE_SIZE / 2;
    if (this.mySprite) {
      if (this.mySprite.tween) this.mySprite.tween.stop();
      this.mySprite.container.x = this.myPx;
      this.mySprite.container.y = this.myPy;
    }
  }

  // Wandkollision per Achse — erlaubt slide-along-wall
  _canMoveTo(px, py) {
    // 4 Ecken der Hitbox prüfen
    const h = this.collisionHalf;
    const corners = [
      [px - h, py - h], [px + h, py - h],
      [px - h, py + h], [px + h, py + h],
    ];
    for (const [cx, cy] of corners) {
      const tx = Math.floor(cx / TILE_SIZE);
      const ty = Math.floor(cy / TILE_SIZE);
      if (!this.isWalkable(tx, ty)) return false;
    }
    return true;
  }

  spawnOther(id, tileX, tileY) {
    if (this.otherPlayers[id]) return;
    const sprite = this.spawnSprite(id, tileX, tileY, false);
    const label = this.add.text(0, -TILE_SIZE * 0.55, id.substr(0, 12), {
      fontSize: '10px', color: '#ddddff', stroke: '#000', strokeThickness: 2,
    }).setOrigin(0.5);
    sprite.container.add(label);
    sprite.label = label;
    this.otherPlayers[id] = { ...sprite, tileX, tileY };
  }

  updatePlayerCount() {
    const n = Object.keys(this.otherPlayers).length + 1;
    document.getElementById('player-count').textContent = `${n} Spieler`;
  }

  showEvent(text) {
    const el = document.createElement('div');
    el.style.cssText = `
      position:fixed; bottom:20px; left:50%; transform:translateX(-50%);
      background:rgba(0,0,0,0.7); color:#c8b88a; padding:6px 16px;
      border:1px solid #555; font-family:monospace; font-size:13px;
      z-index:100; animation:fadeout 3s forwards;
    `;
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  // ─── Welle 24 — Disaster-Effekte (visuell) ──────────────────────────────
  _onDisasterStarted(kind, msg) {
    if (!this._activeDisasters) this._activeDisasters = new Set();
    this._activeDisasters.add(kind);
    // Tint-Overlay anwenden — eigenes div per disaster
    let overlay = document.getElementById(`disaster-${kind}`);
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = `disaster-${kind}`;
      overlay.style.cssText = `
        position: fixed; inset: 0; pointer-events: none; z-index: 6;
        opacity: 0; transition: opacity 4s;
      `;
      document.body.appendChild(overlay);
    }
    if (kind === 'blood_moon') {
      overlay.style.background = 'radial-gradient(circle at center, rgba(120,0,0,0) 30%, rgba(200,30,30,0.45) 100%)';
      overlay.style.mixBlendMode = 'multiply';
    } else if (kind === 'dying_sun') {
      overlay.style.background = 'linear-gradient(180deg, rgba(255,140,40,0.30) 0%, rgba(200,80,20,0.15) 100%)';
      overlay.style.mixBlendMode = 'multiply';
    } else if (kind === 'tainted_well') {
      // Kein full-screen tint; stattdessen Marker am Brunnen via existing event-marker
      if (msg.x != null && msg.y != null) {
        this.showEvent(`☠️ ${msg.label || 'Vergifteter Brunnen'} bei (${msg.x},${msg.y})`);
      }
      return;  // kein Overlay
    }
    // Fade in
    requestAnimationFrame(() => { overlay.style.opacity = '1'; });
  }

  _onDisasterEnded(kind) {
    if (this._activeDisasters) this._activeDisasters.delete(kind);
    const overlay = document.getElementById(`disaster-${kind}`);
    if (overlay) {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.remove(), 4500);
    }
    this.showEvent(`✨ ${kind} ist vorbei`);
  }

  _onEarthquakeShake(durationMs, magnitude) {
    if (!this.cameras || !this.cameras.main) return;
    this.cameras.main.shake(durationMs, magnitude / 1000);
    this.showEvent('🏚 ERDBEBEN!');
  }

  _onLightningStrike(tx, ty) {
    // Visueller Blitz auf der Tile-Position + 200ms weißer Vollbild-Flash
    const px = tx * TILE_SIZE + TILE_SIZE / 2;
    const py = ty * TILE_SIZE + TILE_SIZE / 2;
    // Wenn die Lightning-Animation als Spritesheet vorhanden ist, abspielen
    try {
      if (this.anims && this.anims.exists('lightning_strike')) {
        const s = this.add.sprite(px, py, 'lightning_strike_01')
          .setOrigin(0.5, 1.0).setDepth(20);
        s.play('lightning_strike');
        s.on('animationcomplete', () => s.destroy());
      } else {
        // Fallback: weißer Kreis-Flash auf der Position
        const g = this.add.graphics().setDepth(20);
        g.fillStyle(0xffffff, 0.85);
        g.fillCircle(px, py, TILE_SIZE * 0.7);
        this.tweens.add({
          targets: g, alpha: 0, duration: 250,
          onComplete: () => g.destroy(),
        });
      }
    } catch (e) { /* render-fail egal */ }
    // Kurzer Vollbild-Flash
    const flash = document.createElement('div');
    flash.style.cssText = `
      position: fixed; inset: 0; background: #ffffff; opacity: 0.55;
      pointer-events: none; z-index: 50;
      transition: opacity 0.18s ease-out;
    `;
    document.body.appendChild(flash);
    requestAnimationFrame(() => { flash.style.opacity = '0'; });
    setTimeout(() => flash.remove(), 250);
  }

  update(time, delta) {
    if (!this.mySprite) return;
    if (this.activeDialog || this.inventoryOpen || this.activeChest ||
        this.activeCrafting || this.activeTrade || this.skillsOpen ||
        this.researchOpen || this.questsOpen) return;
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    // Eingabe-Richtung (Keyboard + Touch-Joystick)
    let vx = 0, vy = 0;
    if (this.wasd.left.isDown  || this.cursors.left.isDown)  vx = -1;
    else if (this.wasd.right.isDown || this.cursors.right.isDown) vx = 1;
    if (this.wasd.up.isDown    || this.cursors.up.isDown)    vy = -1;
    else if (this.wasd.down.isDown  || this.cursors.down.isDown)  vy = 1;
    if (window.touchInput && (window.touchInput.x !== 0 || window.touchInput.y !== 0)) {
      vx = window.touchInput.x;
      vy = window.touchInput.y;
    }
    if (vx === 0 && vy === 0) return;

    // Magnitude clampen auf 1 (Keyboard diagonal & Touch-Joystick beides korrekt)
    const _mag = Math.sqrt(vx * vx + vy * vy);
    if (_mag > 1) { vx /= _mag; vy /= _mag; }

    // Delta clampen gegen Lag-Spikes (max 100ms pro Frame)
    const dt = Math.min(0.1, (delta || 16) / 1000);
    const dpx = vx * this.moveSpeed * dt;
    const dpy = vy * this.moveSpeed * dt;

    // Achsen-separate Kollision: erlaubt Sliding an Wänden
    if (dpx !== 0) {
      const newPx = this.myPx + dpx;
      if (this._canMoveTo(newPx, this.myPy)) this.myPx = newPx;
    }
    if (dpy !== 0) {
      const newPy = this.myPy + dpy;
      if (this._canMoveTo(this.myPx, newPy)) this.myPy = newPy;
    }

    // Sprite direkt setzen — keine Tween-Treppe
    this.mySprite.container.x = this.myPx;
    this.mySprite.container.y = this.myPy;
    // Welle 40: Walk-Animation mit 4-Richtungs-Sprites
    this._updateWalkFrame(this.mySprite, vx, vy, delta);

    // Tile-Wechsel → Server informieren + UI/Chunks updaten
    const newTileX = Math.floor(this.myPx / TILE_SIZE);
    const newTileY = Math.floor(this.myPy / TILE_SIZE);
    if (newTileX !== this.myTileX || newTileY !== this.myTileY) {
      const prevTile = this.tileAt(this.myTileX, this.myTileY);
      const prevPxX = this.myTileX * TILE_SIZE + TILE_SIZE / 2;
      const prevPxY = this.myTileY * TILE_SIZE + TILE_SIZE / 2;
      this.myTileX = newTileX;
      this.myTileY = newTileY;
      this.ws.send(JSON.stringify({ type: 'move', x: newTileX, y: newTileY }));
      this.updateUI(newTileX, newTileY);
      this.drawMinimap();
      // Biome geändert → Wetter neu evaluieren (Wüste/Lava blocken Niederschlag)
      const curTile = this.tileAt(newTileX, newTileY);
      if (curTile !== prevTile) this._applyWeather();
      // Welle 50: Footstep-Dust am verlassenen Tile, jeden zweiten Schritt,
      // nur auf trockenen Böden (sand/desert/snow/mountain/lava — kein Wasser
      // oder dichtes Gras). Hält die Anim subtil statt dauerhaft.
      this._footstepCounter = (this._footstepCounter || 0) + 1;
      const DRY_TILES = new Set([1, 5, 8, 4, 7]);  // sand, desert, snow, mountain, lava
      if (this._footstepCounter % 2 === 0 && DRY_TILES.has(prevTile)) {
        this.playOverlayAnim('footstep_dust', prevPxX, prevPxY + TILE_SIZE * 0.2,
                             { scale: 0.45, depth: 2.5, alpha: 0.55, once: true });
      }
    }
  }

  isWalkable(x, y) {
    // Welle 9b: in Dungeons andere Validierung
    if (this.inDungeon) {
      if (x < 0 || y < 0 || x >= this.dungeonSize || y >= this.dungeonSize) return false;
      const dt = this.dungeonTiles[y][x];
      return dt === 1 || dt === 2 || dt === 3;   // floor, corridor, stairs_up
    }
    const t = this.tileAt(x, y);
    if (t === null) return false;  // Chunk noch nicht geladen → blockt vorerst
    if (NON_WALKABLE_TILES.has(t)) return false;
    const s = this.structures[`${x},${y}`];
    if (s && STRUCTURE[s.type] && STRUCTURE[s.type].blocking) return false;
    return true;
  }

  updateUI(x, y) {
    document.getElementById('coords').textContent = `x:${x} y:${y}`;
    const t = this.tileAt(x, y);
    const cfg = (t !== null) ? TILE_BY_ID[t] : null;
    document.getElementById('tile-name').textContent = cfg ? cfg.name : '???';
  }
}

// ─── Phaser Config ────────────────────────────────────────────────────────────
const config = {
  type:            Phaser.AUTO,
  scale: {
    mode:        Phaser.Scale.RESIZE,
    parent:      document.body,
    // Bei RESIZE braucht man weder autoCenter noch fixed width/height — die
    // canvas-Größe folgt dem parent (body = 100vw × 100dvh). Fixed width/height
    // beim Init führte auf Mobile zu Letterboxing nach Orientation-Change.
  },
  backgroundColor: '#0a0a0f',
  scene:           [WorldScene],
};

// Auth-Check vor Game-Start. Bei 401 → Login. Sonst MY_ID setzen und Phaser starten.
(async () => {
  try {
    const r = await fetch('/auth/me');
    if (!r.ok) {
      window.location.href = '/login';
      return;
    }
    const me = await r.json();
    MY_ID = me.username;
    MY_ROLE = me.role;
  } catch (e) {
    window.location.href = '/login';
    return;
  }

  // Auf Mobile: Icon-only, sonst Text. Liest MobileUI das ganz oben gesetzt wird.
  const compactTopRight = !!(window.MobileUI && window.MobileUI.isMobile);
  if (MY_ROLE === 'admin') {
    const adminLink = document.createElement('a');
    adminLink.href = '/admin';
    adminLink.textContent = compactTopRight ? '🛠️' : '🛠️ Admin';
    adminLink.title = 'Admin';
    adminLink.id = 'top-link-admin';
    adminLink.className = 'top-right-link';
    document.body.appendChild(adminLink);
  }

  const logoutLink = document.createElement('a');
  logoutLink.href = '#';
  logoutLink.textContent = compactTopRight ? '🚪' : '🚪 Logout';
  logoutLink.title = 'Logout';
  logoutLink.id = 'top-link-logout';
  logoutLink.className = 'top-right-link';
  logoutLink.addEventListener('click', async (ev) => {
    ev.preventDefault();
    await fetch('/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });
  document.body.appendChild(logoutLink);

  setupChatConsole(MY_ROLE);

  const game = new Phaser.Game(config);
  window._gameInstance = game;
  const refreshCanvas = () => {
    // Phaser auf aktuellen Viewport zwingen — wichtig nach Orientation-Change
    // damit kein Letterbox-Rand bleibt.
    game.scale.resize(window.innerWidth, window.innerHeight);
    game.scale.refresh();
  };
  window.addEventListener('resize', refreshCanvas);
  window.addEventListener('orientationchange', () => setTimeout(refreshCanvas, 200));
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', refreshCanvas);
  }
  setupTouchControls();
})();

// ─── Floating Chat Console ────────────────────────────────────────────────────
// Verschiebbares Chat-Fenster mit Player-Chat (broadcast über game-WS) und
// Dev-Mode (admin-only, Bridge zu Claude CLI auf dem Host).
function setupChatConsole(myRole) {
  const isAdmin = myRole === 'admin';

  const css = `
    #chat-console {
      position: fixed; top: 100px; right: 20px;
      width: 380px; height: 480px;
      background: rgba(15,15,22,0.95);
      border: 1px solid #444;
      box-shadow: 0 8px 32px rgba(0,0,0,0.7);
      z-index: 200; display: flex; flex-direction: column;
      font-family: monospace; color: #c8b88a; font-size: 12px;
    }
    #chat-header {
      padding: 8px 10px; background: #1a1a25;
      border-bottom: 1px solid #444; cursor: move;
      display: flex; align-items: center; gap: 8px; user-select: none;
    }
    #chat-header .title { flex: 1; font-weight: bold; }
    #chat-header button {
      background: transparent; color: #c8b88a; border: 1px solid #444;
      padding: 2px 8px; cursor: pointer; font-family: monospace; font-size: 11px;
    }
    #chat-tabs { display: flex; border-bottom: 1px solid #2a2a35; }
    #chat-tabs button {
      flex: 1; padding: 8px; background: transparent;
      color: #888; border: none; border-bottom: 2px solid transparent;
      cursor: pointer; font-family: monospace; font-size: 12px;
    }
    #chat-tabs button.active { color: #c8b88a; border-bottom-color: #c8b88a; }
    #chat-messages { flex: 1; overflow-y: auto; padding: 10px; }
    .chat-msg { margin-bottom: 8px; line-height: 1.4; white-space: pre-wrap; word-wrap: break-word; }
    .chat-msg .from { color: #7aad6a; font-weight: bold; margin-right: 4px; }
    .chat-msg.system .from { color: #888; }
    .chat-msg.system { color: #888; font-style: italic; }
    .chat-msg.error { color: #e85040; }
    .chat-msg.claude .from { color: #c8a8e8; }
    .chat-msg.claude .body { display: block; margin-top: 2px; }
    #chat-input-row {
      border-top: 1px solid #2a2a35;
      display: flex; padding: 6px; gap: 4px;
    }
    #chat-input {
      flex: 1; background: #0a0a0f; border: 1px solid #2a2a35;
      color: #c8b88a; padding: 6px 8px; font-family: monospace; font-size: 12px;
    }
    #chat-input:focus { outline: none; border-color: #c8b88a; }
    #chat-send {
      padding: 6px 14px; background: #c8b88a; color: #0a0a0f;
      border: none; cursor: pointer; font-family: monospace; font-weight: bold;
    }
    #chat-send:disabled { opacity: 0.4; cursor: not-allowed; }
    .chat-mini {
      position: fixed; top: 12px; right: 230px; z-index: 200;
      background: rgba(15,15,22,0.95); border: 1px solid #444;
      color: #c8b88a; padding: 6px 12px;
      font-family: monospace; font-size: 12px; cursor: pointer;
    }
    @media (max-width: 720px), (max-height: 500px) {
      #chat-console {
        top: auto !important; right: 0 !important; left: 0 !important;
        bottom: 0 !important;
        width: 100vw !important;
        height: 60dvh !important;
        max-height: 60dvh !important;
        border-left: none; border-right: none; border-bottom: none;
      }
      #chat-header { cursor: default; padding: 10px; }
      #chat-tabs button { padding: 12px; font-size: 13px; }
      .chat-mini {
        right: 12px !important; top: auto !important; bottom: 80px;
        padding: 10px 16px;
      }
      #chat-input-row { padding: 8px; }
      #chat-input { font-size: 16px; padding: 10px; }  /* font-size:16px verhindert iOS-Autozoom */
      #chat-send { padding: 10px 18px; }
    }
    /* Landscape-Phone: schmal hoch — chat als rechte Spalte statt Bottom-Sheet */
    @media (orientation: landscape) and (max-height: 500px) {
      #chat-console {
        top: 0 !important; bottom: 0 !important; left: auto !important;
        right: 0 !important;
        width: 55vw !important;
        height: 100dvh !important;
        max-height: 100dvh !important;
      }
    }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  let activeMode = 'player';
  let devWs = null;
  let devBusy = false;

  const root = document.createElement('div');
  root.id = 'chat-console';
  root.innerHTML = `
    <div id="chat-header">
      <span class="title">💬 Chat</span>
      <button id="chat-min">_</button>
    </div>
    <div id="chat-tabs">
      <button data-mode="player" class="active">🎮 Player</button>
      ${isAdmin ? '<button data-mode="dev">🛠️ Dev (Claude)</button>' : ''}
    </div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="An alle Spieler…" maxlength="500" />
      <button id="chat-send">↩</button>
    </div>
  `;
  document.body.appendChild(root);

  const miniBtn = document.createElement('div');
  miniBtn.className = 'chat-mini';
  // Mobile: nur Icon, sonst voller Text
  const _mobChat = !!(window.MobileUI && window.MobileUI.isMobile);
  miniBtn.textContent = _mobChat ? '💬' : '💬 Chat öffnen';
  miniBtn.title = 'Chat öffnen';
  miniBtn.style.display = 'none';
  document.body.appendChild(miniBtn);

  // === Drag ===
  const header = root.querySelector('#chat-header');
  let dragStart = null;
  header.addEventListener('mousedown', (ev) => {
    if (ev.target.tagName === 'BUTTON') return;
    const rect = root.getBoundingClientRect();
    dragStart = { dx: ev.clientX - rect.left, dy: ev.clientY - rect.top };
  });
  document.addEventListener('mousemove', (ev) => {
    if (!dragStart) return;
    root.style.left = Math.max(0, Math.min(window.innerWidth - 100, ev.clientX - dragStart.dx)) + 'px';
    root.style.top  = Math.max(0, Math.min(window.innerHeight - 50, ev.clientY - dragStart.dy)) + 'px';
    root.style.right = 'auto';
  });
  document.addEventListener('mouseup', () => { dragStart = null; });

  // === Minimize ===
  root.querySelector('#chat-min').addEventListener('click', () => {
    root.style.display = 'none';
    miniBtn.style.display = 'block';
  });
  miniBtn.addEventListener('click', () => {
    root.style.display = 'flex';
    miniBtn.style.display = 'none';
  });

  // === Tabs ===
  const inputEl = root.querySelector('#chat-input');
  const sendBtn = root.querySelector('#chat-send');
  root.querySelectorAll('#chat-tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      activeMode = mode;
      root.querySelectorAll('#chat-tabs button').forEach(b => b.classList.toggle('active', b === btn));
      inputEl.placeholder = (mode === 'dev') ? 'Frag Claude (Repo: liege)…' : 'An alle Spieler…';
      if (mode === 'dev' && (!devWs || devWs.readyState > 1)) connectDevWs();
      updateSendDisabled();
    });
  });

  // === Messages ===
  const msgsEl = root.querySelector('#chat-messages');
  function addMessage(kind, from, text) {
    const div = document.createElement('div');
    div.className = 'chat-msg ' + (kind || '');
    if (from) {
      const f = document.createElement('span');
      f.className = 'from';
      f.textContent = from + ':';
      div.appendChild(f);
    }
    const body = document.createElement('span');
    body.className = 'body';
    body.textContent = text;
    div.appendChild(body);
    msgsEl.appendChild(div);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  // === Send ===
  function updateSendDisabled() {
    sendBtn.disabled = (activeMode === 'dev' && devBusy);
  }
  function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    if (activeMode === 'player') {
      if (window.GAME_WS && window.GAME_WS.readyState === WebSocket.OPEN) {
        window.GAME_WS.send(JSON.stringify({ type: 'chat', text }));
      } else {
        addMessage('error', null, '⚠️ Game-Verbindung nicht offen');
      }
    } else if (activeMode === 'dev') {
      if (devBusy) return;
      if (devWs && devWs.readyState === WebSocket.OPEN) {
        addMessage('', MY_ID, text);
        devWs.send(JSON.stringify({ type: 'message', message: text }));
        devBusy = true;
        updateSendDisabled();
      } else {
        addMessage('error', null, '⚠️ Dev-Verbindung nicht offen — Tab wechseln und zurück');
      }
    }
    inputEl.value = '';
  }
  sendBtn.addEventListener('click', send);
  inputEl.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      send();
    }
  });

  // === Dev WS ===
  function connectDevWs() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    devWs = new WebSocket(`${proto}//${window.location.host}/ws/dev-chat`);
    devWs.onopen = () => addMessage('system', null, '✓ Dev-Chat verbunden');
    devWs.onclose = (ev) => {
      addMessage('system', null, '✗ Dev-Chat getrennt (' + ev.code + ')');
      devWs = null;
      devBusy = false;
      updateSendDisabled();
    };
    devWs.onerror = () => addMessage('error', null, 'Dev-WS Fehler');
    devWs.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.type === 'ready') {
        // ok
      } else if (data.type === 'thinking') {
        addMessage('system', null, '… Claude arbeitet (kann 30+ Sek dauern)');
      } else if (data.type === 'reply') {
        devBusy = false;
        updateSendDisabled();
        if (data.ok) {
          addMessage('claude', 'Claude', data.response || '(leere Antwort)');
        } else {
          addMessage('error', 'Claude', 'Fehler: ' + (data.stderr || 'unbekannt'));
        }
      } else if (data.type === 'error') {
        addMessage('error', null, data.error || 'Fehler');
      }
    };
  }

  // Hook für Game-Scene (eingehende Player-Chats über die Game-WS)
  window.chatConsole = { addMessage };

  addMessage('system', null, isAdmin
    ? 'Bereit. Tab wechseln zu Dev für Claude-Bridge.'
    : 'Bereit. Schreib was an die anderen Spieler.');

  // VisualViewport-API: Chat über die Soft-Keyboard hochschieben damit Input sichtbar bleibt.
  // Ohne das versteckt iOS Safari (und teils Chrome Android) die fixed-bottom-Elements
  // hinter der Tastatur. Die Mobile-CSS-Regeln nutzen !important — wir müssen daher
  // auch mit !important über setProperty arbeiten, sonst werden unsere Inline-Werte
  // ignoriert.
  if (window.visualViewport) {
    const adjustForKeyboard = () => {
      const vv = window.visualViewport;
      const keyboardHeight = window.innerHeight - vv.height - vv.offsetTop;
      if (keyboardHeight > 80) {
        root.style.setProperty('bottom', keyboardHeight + 'px', 'important');
        root.style.setProperty('max-height', (vv.height - 20) + 'px', 'important');
        root.style.setProperty('height', Math.min(vv.height - 20, 480) + 'px', 'important');
        // Scroll der Messages ans Ende, damit der gerade getippte Bereich sichtbar bleibt
        const msgs = document.getElementById('chat-messages');
        if (msgs) msgs.scrollTop = msgs.scrollHeight;
      } else {
        root.style.removeProperty('bottom');
        root.style.removeProperty('max-height');
        root.style.removeProperty('height');
      }
    };
    window.visualViewport.addEventListener('resize', adjustForKeyboard);
    window.visualViewport.addEventListener('scroll', adjustForKeyboard);
    // Auch beim Fokus auf das Input: Verzögert nochmal trigger, weil iOS die
    // viewport-resize manchmal erst NACH dem Tastatur-Öffnen feuert.
    const inp = document.getElementById('chat-input');
    if (inp) {
      inp.addEventListener('focus', () => {
        setTimeout(adjustForKeyboard, 100);
        setTimeout(adjustForKeyboard, 400);
      });
      inp.addEventListener('blur', () => setTimeout(adjustForKeyboard, 100));
    }
  }
}

// ─── Touch Controls ──────────────────────────────────────────────────────────
// Virtual Joystick links unten (Movement) + Action-Buttons rechts unten (Menüs).
// Wird nur initialisiert wenn Touch-Device. Schreibt window.touchInput = {x,y}
// das die Game-update-Loop liest.
function setupTouchControls() {
  const isTouch =
    ('ontouchstart' in window) ||
    (navigator.maxTouchPoints > 0) ||
    window.matchMedia('(pointer: coarse)').matches;
  if (!isTouch) return;

  const css = `
    /* Floating-Joystick: erscheint dort wo der Daumen in der linken Hälfte landet.
       Anfangs versteckt, opacity-Transition für sanften Auftritt. */
    #touch-joystick {
      position: fixed; left: 0; top: 0;
      width: 140px; height: 140px;
      background: rgba(15,15,22,0.45);
      border: 2px solid rgba(200,184,138,0.55);
      border-radius: 50%;
      z-index: 150;
      opacity: 0;
      pointer-events: none;        /* gefangen wird über zone */
      transform: translate(-9999px, -9999px);
      transition: opacity 0.12s linear;
    }
    #touch-joystick.active { opacity: 1; }
    #touch-joystick-thumb {
      position: absolute; left: 50%; top: 50%;
      width: 60px; height: 60px; margin: -30px 0 0 -30px;
      background: rgba(200,184,138,0.7);
      border: 2px solid #c8b88a;
      border-radius: 50%;
      pointer-events: none;
      will-change: transform;
    }
    /* Joystick-Zone (unsichtbar): unteres Drittel des Screens, volle Breite.
       Oberes 2/3 bleibt frei für Tile-Clicks/Angriffe — vorher fing der
       Joystick fast die ganze linke Hälfte ab und blockierte Combat-Touches. */
    #touch-joystick-zone {
      position: fixed; left: 0; bottom: 0;
      width: 100vw; height: 33vh;
      z-index: 140;
      touch-action: none;
      -webkit-user-select: none; user-select: none;
      /* Kein pointer-events: none — wir wollen touchstart abfangen */
    }
    #touch-actions {
      position: fixed; right: 12px; bottom: calc(12px + env(safe-area-inset-bottom));
      display: grid; grid-template-columns: 56px 56px; gap: 8px;
      z-index: 220;     /* über Minimap (10) und über inventory-overlay (150) */
    }
    .touch-btn {
      width: 56px; height: 56px;
      background: rgba(15,15,22,0.7);
      border: 2px solid rgba(200,184,138,0.6);
      color: #c8b88a; font-size: 22px;
      display: flex; align-items: center; justify-content: center;
      border-radius: 50%;
      touch-action: manipulation;
      -webkit-user-select: none; user-select: none;
      cursor: pointer;
    }
    .touch-btn:active { background: rgba(200,184,138,0.3); }
    .touch-btn.toggled { background: rgba(200,184,138,0.3); border-color: #c8b88a; }
    /* Portrait-Mobile: Buttons als horizontale Bottom-Bar quer über den Screen,
       damit sie weder mit der Minimap noch mit dem Joystick kollidieren. */
    @media (orientation: portrait) and (max-width: 720px) {
      #touch-actions {
        right: auto; left: 50%; transform: translateX(-50%);
        bottom: calc(8px + env(safe-area-inset-bottom));
        grid-template-columns: repeat(6, 52px);
        gap: 6px;
      }
      .touch-btn { width: 52px; height: 52px; font-size: 20px; }
      /* Portrait-Mobile: Minimap oben rechts, kompakt */
      #minimap {
        bottom: auto !important; right: 8px !important; top: 80px !important;
        width: 120px !important; height: 90px !important;
      }
      /* Portrait übernimmt jetzt das Default 100vw × 33vh — kein Override nötig */
    }
    @media (orientation: landscape) and (max-height: 500px) {
      /* In Landscape mit wenig Höhe: Action-Buttons als 1 Spalte */
      #touch-actions { grid-template-columns: 56px; right: 8px; bottom: 8px; }
      /* Landscape niedrige Höhe: Joystick-Zone bleibt bei unterem 1/3 */
      #touch-joystick-zone { height: 33vh; width: 100vw; }
    }
    /* Orientation-Warnung deaktiviert — Portrait wird jetzt unterstützt.
       (Wenn Bedarf: alte @media-Regel reaktivieren) */
    #orient-warning { display: none !important; }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  // ── Floating Joystick ──
  // Joystick existiert immer im DOM, ist aber unsichtbar bis ein Touch in der
  // Joystick-Zone (linke untere Bildschirmhälfte) landet. Spawnt dort, folgt dem
  // Finger im MAX_R-Radius, verschwindet bei touchend.
  const joystick = document.createElement('div');
  joystick.id = 'touch-joystick';
  joystick.innerHTML = '<div id="touch-joystick-thumb"></div>';
  document.body.appendChild(joystick);
  const thumb = joystick.querySelector('#touch-joystick-thumb');

  const zone = document.createElement('div');
  zone.id = 'touch-joystick-zone';
  document.body.appendChild(zone);

  window.touchInput = { x: 0, y: 0 };
  let activeId = null;
  let originX = 0, originY = 0;
  const MAX_R = 55;             // Max Thumb-Displacement (px)
  const DEAD_ZONE = MAX_R * 0.15;  // 15% des Radius (Cassino-Recommendation)

  function placeJoystickAt(x, y) {
    // Joystick zentriert auf (x,y) positionieren
    const halfSize = 70; // halbe Joystick-Breite (140/2)
    joystick.style.transform = `translate(${x - halfSize}px, ${y - halfSize}px)`;
    joystick.classList.add('active');
    originX = x;
    originY = y;
    setThumb(0, 0);
  }
  function hideJoystick() {
    joystick.classList.remove('active');
    joystick.style.transform = 'translate(-9999px, -9999px)';
  }
  function setThumb(dx, dy) {
    thumb.style.transform = `translate(${dx}px, ${dy}px)`;
  }
  function resetJoy() {
    setThumb(0, 0);
    window.touchInput.x = 0;
    window.touchInput.y = 0;
    activeId = null;
    hideJoystick();
  }

  zone.addEventListener('touchstart', (ev) => {
    ev.preventDefault();
    if (activeId !== null) return;
    const t = ev.changedTouches[0];
    activeId = t.identifier;
    placeJoystickAt(t.clientX, t.clientY);
  }, { passive: false });

  // touchmove auf document, damit Finger über die Zone hinaus gleiten darf
  document.addEventListener('touchmove', (ev) => {
    if (activeId === null) return;
    let touch = null;
    for (let i = 0; i < ev.touches.length; i++) {
      if (ev.touches[i].identifier === activeId) { touch = ev.touches[i]; break; }
    }
    if (!touch) return;
    ev.preventDefault();
    let dx = touch.clientX - originX;
    let dy = touch.clientY - originY;
    const dist = Math.hypot(dx, dy);
    if (dist < DEAD_ZONE) {
      setThumb(0, 0);
      window.touchInput.x = 0;
      window.touchInput.y = 0;
      return;
    }
    if (dist > MAX_R) {
      dx = dx / dist * MAX_R;
      dy = dy / dist * MAX_R;
    }
    setThumb(dx, dy);
    window.touchInput.x = dx / MAX_R;
    window.touchInput.y = dy / MAX_R;
  }, { passive: false });

  function handleEnd(ev) {
    if (activeId === null) return;
    for (let i = 0; i < ev.changedTouches.length; i++) {
      if (ev.changedTouches[i].identifier === activeId) { resetJoy(); break; }
    }
  }
  document.addEventListener('touchend', handleEnd, { passive: true });
  document.addEventListener('touchcancel', handleEnd, { passive: true });

  // ── Action Buttons ──
  // Greift direkt auf die WorldScene zu. Falls Scene noch nicht da: kurzer Retry.
  function getScene() {
    if (!window._gameInstance) return null;
    return window._gameInstance.scene.getScene('WorldScene') || null;
  }
  function callScene(method) {
    const sc = getScene();
    if (sc && typeof sc[method] === 'function') sc[method]();
  }

  const actions = document.createElement('div');
  actions.id = 'touch-actions';
  // primary=immer sichtbar (auch im Build-Mode). secondary=im Build-Mode versteckt (CSS).
  // Reihenfolge so dass im Portrait-4×2-Grid die wichtigsten 4 in der oberen Reihe sind.
  const BUTTONS = [
    { label: '🎒', method: 'toggleInventory', title: 'Inventar',    primary: true  },
    { label: '⚒️', method: 'toggleBuildMode', title: 'Bauen',       primary: true  },
    { label: '📜', method: 'toggleQuests',    title: 'Quests',      primary: true  },
    { label: '🗺',  method: 'toggleMinimap',  title: 'Karte',       primary: true  },
    { label: '🌱', method: 'toggleSkills',    title: 'Skills',      primary: false },
    { label: '🔬', method: 'toggleResearch',  title: 'Forschung',   primary: false },
    { label: '⭐', method: 'toggleTalents',   title: 'Talente',     primary: false },
    { label: '⚖️', method: 'toggleFactions',  title: 'Faktionen',   primary: false },
    { label: '📋', method: 'toggleAttributes',title: 'Attribute',   primary: false },
  ];
  BUTTONS.forEach((b) => {
    const btn = document.createElement('div');
    btn.className = 'touch-btn';
    btn.textContent = b.label;
    btn.title = b.title;
    if (!b.primary) btn.setAttribute('data-secondary', '1');
    const fire = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      // toggleMinimap: lokaler DOM-Toggle, keine Scene-Methode
      if (b.method === 'toggleMinimap') {
        const map = document.getElementById('minimap');
        const tog = document.getElementById('minimap-toggle');
        if (map) {
          map.classList.toggle('collapsed');
          if (tog) tog.textContent = map.classList.contains('collapsed') ? '🗺' : '×';
        }
        return;
      }
      callScene(b.method);
    };
    btn.addEventListener('touchstart', fire, { passive: false });
    btn.addEventListener('click', fire);
    actions.appendChild(btn);
  });
  document.body.appendChild(actions);

  // Orientation-Warnung — wird per CSS-Media-Query angezeigt wenn Portrait + schmal
  const orient = document.createElement('div');
  orient.id = 'orient-warning';
  orient.innerHTML = `
    <div class="icon">📱</div>
    <div>Bitte dreh dein Gerät quer</div>
    <div style="font-size:11px;color:#888;">Liege spielt sich am besten im Landscape-Modus.</div>
  `;
  document.body.appendChild(orient);

  // Bei aktivem Dialog/Overlay: Joystick zurücksetzen damit Player nicht weiterläuft
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) resetJoy();
  });

  // Wenn der Browser ins Background geht → Joystick reset + Phaser-Pause
  window.addEventListener('blur', () => resetJoy());
}

// Fade-Animation für Events
const style = document.createElement('style');
style.textContent = `@keyframes fadeout { 0%{opacity:1} 70%{opacity:1} 100%{opacity:0} }`;
document.head.appendChild(style);
