"""Research-Tree MVP — Tech-Progression.

Spieler investiert Zeit (Klick = 1 Punkt) in Forschungs-Knoten.
Wenn ein Knoten komplett ist, ist er 'unlocked' — Effekt: andere Knoten freischalten
oder Rezepte aktivieren (Game-Code muss `is_research_done` prüfen)."""

import logging

import db

log = logging.getLogger("liege.research")


# ─── Welle 30c — Research-Tree v2 ─────────────────────────────────────────
# 5 Tech-Ages × 8 Branches × 1-3 Nodes/Branch/Age = ~75 Nodes.
#
# Felder pro Node:
#   name        — UI-Anzeige
#   desc        — Tooltip-Text
#   points      — Forschungspunkt-Kosten
#   prereq      — Liste von node-IDs die alle vorher 'done' sein müssen.
#                 Empty list [] = kein Prereq (Start-Knoten).
#                 Single id als String wird in Liste konvertiert (backwards-compat).
#   unlocks     — Liste von Recipe-IDs / Spell-Items / Strukturen die freigeschaltet werden
#   icon        — Emoji für UI
#   branch      — Tree-Branch: smithing | alchemy | magic | agriculture |
#                 architecture | medicine | economy | mysticism
#   age         — Tech-Age: tribal | iron | high_medieval | magic | legendary
#   tech_print  — Optional: Item-Kind das im Inventar sein muss (wird beim
#                 Unlock consumed). Macht Late-Game-Nodes von Quests/Boss-Drops
#                 abhängig statt nur Punkte-Sammeln.
RESEARCH_NODES = {

    # ════════════════ ⚒️  SCHMIEDEKUNST  (12 Nodes) ════════════════════════
    # Stammeszeit
    "smithing_bone_tools": {
        "name": "Knochen-Werkzeuge", "icon": "🦴",
        "desc": "Primitive Waffen aus Knochen + Stein",
        "branch": "smithing", "age": "tribal",
        "points": 4, "prereq": [],
        "unlocks": ["wooden_sword", "wooden_spear", "stone_sword", "stone_dagger", "stone_spear"],
    },
    "smithing_quarry": {
        "name": "Steinbruch", "icon": "⛏️",
        "desc": "Erz aus Felsen brechen + Steinwerkzeuge",
        "branch": "smithing", "age": "tribal",
        "points": 6, "prereq": [],
        "unlocks": ["make_pickaxe", "stone_dagger"],
    },
    # Eisen-Zeit
    "smithing_iron_smelting": {
        "name": "Eisenschmelze", "icon": "🔥",
        "desc": "Eisen aus Erz schmelzen, Eisenwaffen + Rüstung",
        "branch": "smithing", "age": "iron",
        "points": 18, "prereq": ["smithing_bone_tools"],
        "unlocks": ["smelt_iron", "iron_sword", "iron_axe", "iron_helm",
                    "iron_chest", "iron_shield", "iron_boots", "iron_katana",
                    "iron_halberd", "iron_trident", "iron_lance",
                    "iron_twinblade", "iron_sickle"],
    },
    "smithing_archery": {
        "name": "Bogenbau", "icon": "🏹",
        "desc": "Ranged-Waffen für Jäger",
        "branch": "smithing", "age": "iron",
        "points": 15, "prereq": ["smithing_bone_tools"],
        "unlocks": ["make_bow", "make_crossbow", "make_throwing_knife"],
    },
    "smithing_leatherworking": {
        "name": "Lederverarbeitung", "icon": "🛡️",
        "desc": "Leder gerben, Lederrüstung",
        "branch": "smithing", "age": "iron",
        "points": 12, "prereq": ["smithing_bone_tools"],
        "unlocks": ["tan_leather", "leather_gloves"],
    },
    # Hochmittelalter
    "smithing_steel": {
        "name": "Stahlverarbeitung", "icon": "🗡️",
        "desc": "Stahl-Legierung — bessere Waffen + Rüstung",
        "branch": "smithing", "age": "high_medieval",
        "points": 45, "prereq": ["smithing_iron_smelting"],
        "unlocks": ["smelt_steel", "steel_sword", "steel_chest",
                    "steel_katana", "steel_halberd"],
    },
    "smithing_plate_armor": {
        "name": "Plattenpanzer", "icon": "🛡️",
        "desc": "Vollplattenrüstung — schwer + hohe DR",
        "branch": "smithing", "age": "high_medieval",
        "points": 55, "prereq": ["smithing_steel", "smithing_leatherworking"],
        "unlocks": ["plate_helm", "plate_chest", "plate_boots"],
    },
    "smithing_silver": {
        "name": "Silberschmiede", "icon": "🥈",
        "desc": "Silber für magieresistente Waffen",
        "branch": "smithing", "age": "high_medieval",
        "points": 40, "prereq": ["smithing_steel"],
        "unlocks": ["smelt_silver", "silver_sword", "silver_helm"],
    },
    # Magisches Zeitalter
    "smithing_mithril": {
        "name": "Mithril-Schmiede", "icon": "💎",
        "desc": "Leichtes Mithril — sehr hohe DR bei niedriger Last",
        "branch": "smithing", "age": "magic",
        "points": 110, "prereq": ["smithing_silver", "magic_runes"],
        "tech_print": "mithril_plans",
        "unlocks": ["smelt_mithril", "mithril_sword", "mithril_chest",
                    "mithril_runeblade"],
    },
    "smithing_runic_weapons": {
        "name": "Runenwaffen", "icon": "🔣",
        "desc": "Magisch verstärkte Waffen mit Affixen",
        "branch": "smithing", "age": "magic",
        "points": 95, "prereq": ["smithing_steel", "magic_runes"],
        "unlocks": ["forge_rune_weapon"],
    },
    "smithing_dragon_steel": {
        "name": "Drachenstahl", "icon": "🐲",
        "desc": "Stahl in Drachenfeuer gehärtet — feuerresistent",
        "branch": "smithing", "age": "magic",
        "points": 130, "prereq": ["smithing_mithril"],
        "tech_print": "dragon_skull",
        "unlocks": ["forge_dragon_steel"],
    },
    # Legendäres Zeitalter
    "smithing_adamant": {
        "name": "Adamant-Schmiede", "icon": "⭐",
        "desc": "Unzerstörbares Adamant — Götterklingen",
        "branch": "smithing", "age": "legendary",
        "points": 280, "prereq": ["smithing_dragon_steel"],
        "tech_print": "gods_tablet",
        "unlocks": ["smelt_adamant", "adamant_sword", "adamant_chest"],
    },

    # ════════════════ ⚗️  ALCHEMIE  (10 Nodes) ════════════════════════════
    # Stammeszeit
    "alchemy_herbs": {
        "name": "Kräuterkunde", "icon": "🌿",
        "desc": "Heilkräuter sammeln + zubereiten",
        "branch": "alchemy", "age": "tribal",
        "points": 5, "prereq": [],
        "unlocks": ["brew_herb_tea"],
    },
    # Eisen-Zeit
    "alchemy_basic_potions": {
        "name": "Trankbrauerei", "icon": "🧪",
        "desc": "Heil- und Manatränke brauen",
        "branch": "alchemy", "age": "iron",
        "points": 18, "prereq": ["alchemy_herbs"],
        "unlocks": ["brew_health", "brew_mana"],
    },
    "alchemy_antidotes": {
        "name": "Gegengifte", "icon": "💊",
        "desc": "Antidote gegen Gift- und Krankheitszustände",
        "branch": "alchemy", "age": "iron",
        "points": 22, "prereq": ["alchemy_basic_potions"],
        "unlocks": ["brew_antidote"],
    },
    # Hochmittelalter
    "alchemy_resistance": {
        "name": "Resistenz-Tränke", "icon": "🔥",
        "desc": "Feuer-/Frostwiderstandstränke",
        "branch": "alchemy", "age": "high_medieval",
        "points": 50, "prereq": ["alchemy_basic_potions"],
        "unlocks": ["brew_fire_resist", "brew_frost_resist"],
    },
    "alchemy_combat_potions": {
        "name": "Kampftränke", "icon": "💪",
        "desc": "Stärke + Geschwindigkeit + Ausdauer",
        "branch": "alchemy", "age": "high_medieval",
        "points": 55, "prereq": ["alchemy_antidotes"],
        "unlocks": ["brew_strength", "brew_speed", "brew_stamina"],
    },
    "alchemy_bombs": {
        "name": "Alchemistische Bomben", "icon": "💣",
        "desc": "Wurfbomben — AOE-Schaden",
        "branch": "alchemy", "age": "high_medieval",
        "points": 45, "prereq": ["alchemy_combat_potions"],
        "unlocks": ["craft_fire_bomb", "craft_poison_bomb"],
    },
    # Magisches Zeitalter
    "alchemy_invisibility": {
        "name": "Unsichtbarkeit", "icon": "👻",
        "desc": "Unsichtbarkeits-Trank — kurzfristig untracebar",
        "branch": "alchemy", "age": "magic",
        "points": 90, "prereq": ["alchemy_resistance"],
        "tech_print": "alchemy_codex",
        "unlocks": ["brew_invisibility"],
    },
    "alchemy_transmutation": {
        "name": "Transmutation", "icon": "✨",
        "desc": "Materialien in andere umwandeln (iron→steel etc.)",
        "branch": "alchemy", "age": "magic",
        "points": 105, "prereq": ["alchemy_invisibility"],
        "tech_print": "alchemy_codex",
        "unlocks": ["transmute_iron_to_steel"],
    },
    # Legendär
    "alchemy_immortality_elixir": {
        "name": "Lebenselixier", "icon": "🌟",
        "desc": "Mythisches Elixier — voll-Heal + Buff-Boost",
        "branch": "alchemy", "age": "legendary",
        "points": 240, "prereq": ["alchemy_transmutation"],
        "tech_print": "gods_tablet",
        "unlocks": ["brew_immortality"],
    },
    "alchemy_philosopher_stone": {
        "name": "Stein der Weisen", "icon": "💎",
        "desc": "Endgame — Gold aus jedem Metall",
        "branch": "alchemy", "age": "legendary",
        "points": 350, "prereq": ["alchemy_immortality_elixir", "smithing_adamant"],
        "tech_print": "gods_tablet",
        "unlocks": ["philosopher_stone"],
    },

    # ════════════════ ✨  MAGIE  (12 Nodes) ═══════════════════════════════
    # Stammeszeit
    "magic_animism": {
        "name": "Animismus", "icon": "🔥",
        "desc": "Schamanenkunst — Naturgeister rufen",
        "branch": "magic", "age": "tribal",
        "points": 6, "prereq": [],
        "unlocks": ["rune_stone"],   # Heilrune existing
    },
    # Eisen-Zeit
    "magic_fundamentals": {
        "name": "Magische Grundlagen", "icon": "✨",
        "desc": "Schriftrollen lesen + Mana fokussieren",
        "branch": "magic", "age": "iron",
        "points": 20, "prereq": ["magic_animism"],
        "unlocks": ["scroll"],   # Magisches Geschoss
    },
    "magic_fire": {
        "name": "Feuermagie", "icon": "🔥",
        "desc": "Feuerball + Brandzauber",
        "branch": "magic", "age": "iron",
        "points": 25, "prereq": ["magic_fundamentals"],
        "unlocks": ["spell_book"],   # Feuerball
    },
    "magic_light": {
        "name": "Lichtmagie", "icon": "💡",
        "desc": "Heilung + Lichtkegel",
        "branch": "magic", "age": "iron",
        "points": 25, "prereq": ["magic_animism"],
        "unlocks": ["holy_shield_scroll"],
    },
    # Hochmittelalter
    "magic_ice": {
        "name": "Eismagie", "icon": "❄️",
        "desc": "Eis-Sturm + Frost-Effekte",
        "branch": "magic", "age": "high_medieval",
        "points": 55, "prereq": ["magic_fire"],
        "unlocks": ["ice_scroll"],
    },
    "magic_air": {
        "name": "Windmagie", "icon": "🌪",
        "desc": "Wind-Klinge + Levitation",
        "branch": "magic", "age": "high_medieval",
        "points": 50, "prereq": ["magic_fundamentals"],
        "unlocks": ["wind_slash_scroll"],
    },
    "magic_summoning": {
        "name": "Beschwörung", "icon": "👹",
        "desc": "Geist-Diener auf Zeit beschwören",
        "branch": "magic", "age": "high_medieval",
        "points": 70, "prereq": ["magic_fire", "magic_light"],
        "unlocks": ["summon_familiar"],
    },
    # Magisches Zeitalter
    "magic_runes": {
        "name": "Runenmagie", "icon": "🔣",
        "desc": "Permanente Effekte in Stein/Waffe gebrannt",
        "branch": "magic", "age": "magic",
        "points": 95, "prereq": ["magic_ice", "magic_air"],
        "tech_print": "runic_tablet",
        "unlocks": ["inscribe_rune"],
    },
    "magic_necromancy": {
        "name": "Nekromantie", "icon": "💀",
        "desc": "Untote erwecken — kontroverse Schule",
        "branch": "magic", "age": "magic",
        "points": 110, "prereq": ["magic_summoning"],
        "tech_print": "ancient_scroll",
        "unlocks": ["raise_skeleton"],
    },
    "magic_dragonspeak": {
        "name": "Drachensprache", "icon": "🐲",
        "desc": "Drachen verstehen und befrieden",
        "branch": "magic", "age": "magic",
        "points": 120, "prereq": ["magic_runes"],
        "tech_print": "dragon_skull",
        "unlocks": ["tame_dragon_whelp"],
    },
    # Legendär
    "magic_chronomancy": {
        "name": "Zeitmagie", "icon": "⏳",
        "desc": "Zeit lokal verlangsamen/anhalten",
        "branch": "magic", "age": "legendary",
        "points": 250, "prereq": ["magic_runes", "magic_necromancy"],
        "tech_print": "gods_tablet",
        "unlocks": ["chronos_spell"],
    },
    "magic_portal": {
        "name": "Portalmagie", "icon": "🌀",
        "desc": "Fern-Teleport zwischen Portal-Steinen",
        "branch": "magic", "age": "legendary",
        "points": 300, "prereq": ["magic_chronomancy", "architecture_portal_stone"],
        "tech_print": "gods_tablet",
        "unlocks": ["create_portal"],
    },

    # ════════════════ 🌾  LANDWIRTSCHAFT  (8 Nodes) ═══════════════════════
    "agriculture_foraging": {
        "name": "Sammeln", "icon": "🍓",
        "desc": "Wildbeeren + Wildkräuter erkennen",
        "branch": "agriculture", "age": "tribal",
        "points": 4, "prereq": [],
        "unlocks": ["forage_plus"],
    },
    "agriculture_basic_farming": {
        "name": "Ackerbau", "icon": "🌾",
        "desc": "Brot backen, gekochte Mahlzeiten, Acker pflanzen",
        "branch": "agriculture", "age": "iron",
        "points": 15, "prereq": ["agriculture_foraging"],
        "unlocks": ["bake_bread", "cook_meat", "cook_fish"],
    },
    "agriculture_animal_husbandry": {
        "name": "Tierhaltung", "icon": "🐄",
        "desc": "Nutztiere zähmen + halten",
        "branch": "agriculture", "age": "iron",
        "points": 20, "prereq": ["agriculture_basic_farming"],
        "unlocks": ["tame_livestock"],
    },
    "agriculture_advanced_crops": {
        "name": "Erweiterte Feldfrüchte", "icon": "🌻",
        "desc": "Höherer Ertrag + neue Pflanzen (Trauben, Knoblauch)",
        "branch": "agriculture", "age": "high_medieval",
        "points": 45, "prereq": ["agriculture_basic_farming"],
        "unlocks": ["plant_grapes", "plant_garlic"],
    },
    "agriculture_dairy": {
        "name": "Milchwirtschaft", "icon": "🥛",
        "desc": "Käse + Butter herstellen",
        "branch": "agriculture", "age": "high_medieval",
        "points": 40, "prereq": ["agriculture_animal_husbandry"],
        "unlocks": ["make_cheese", "make_butter"],
    },
    "agriculture_beekeeping": {
        "name": "Imkerei", "icon": "🐝",
        "desc": "Bienenstöcke + Honigertrag",
        "branch": "agriculture", "age": "high_medieval",
        "points": 50, "prereq": ["agriculture_advanced_crops"],
        "unlocks": ["beehive", "harvest_honey"],
    },
    "agriculture_brewery": {
        "name": "Brauerei", "icon": "🍺",
        "desc": "Bier + Met brauen",
        "branch": "agriculture", "age": "magic",
        "points": 75, "prereq": ["agriculture_advanced_crops", "agriculture_beekeeping"],
        "unlocks": ["brew_beer", "brew_mead"],
    },
    "agriculture_dragon_taming": {
        "name": "Drachenzucht", "icon": "🐉",
        "desc": "Drachen als Reittier + Wachen",
        "branch": "agriculture", "age": "legendary",
        "points": 280, "prereq": ["agriculture_animal_husbandry", "magic_dragonspeak"],
        "tech_print": "dragon_skull",
        "unlocks": ["dragon_stable"],
    },

    # ════════════════ 🏛️  ARCHITEKTUR  (10 Nodes) ════════════════════════
    "architecture_huts": {
        "name": "Primitive Hütten", "icon": "⛺",
        "desc": "Stroh-/Lehm-Wände, einfache Türen",
        "branch": "architecture", "age": "tribal",
        "points": 5, "prereq": [],
        "unlocks": ["build_straw_wall", "build_camp_tent"],
    },
    "architecture_stone_walls": {
        "name": "Steinmauern", "icon": "🧱",
        "desc": "Stein als Bau-Material, robuste Wände",
        "branch": "architecture", "age": "iron",
        "points": 18, "prereq": ["architecture_huts"],
        "unlocks": ["build_stone_wall", "build_well"],
    },
    "architecture_doors_locks": {
        "name": "Türen + Schlösser", "icon": "🚪",
        "desc": "Holztür + Eisentür-Crafting",
        "branch": "architecture", "age": "iron",
        "points": 15, "prereq": ["architecture_stone_walls"],
        "unlocks": ["build_door_iron"],
    },
    "architecture_fortress": {
        "name": "Festungsbau", "icon": "🏰",
        "desc": "Verstärkte Mauern + Tore + Schießscharten",
        "branch": "architecture", "age": "high_medieval",
        "points": 60, "prereq": ["architecture_stone_walls"],
        "unlocks": ["build_door_reinforced", "build_arrow_slit"],
    },
    "architecture_towers": {
        "name": "Wehrtürme", "icon": "🗼",
        "desc": "Hohe Wachtürme mit Höhen-Vorteil",
        "branch": "architecture", "age": "high_medieval",
        "points": 55, "prereq": ["architecture_fortress"],
        "unlocks": ["build_watch_tower"],
    },
    "architecture_bridges": {
        "name": "Brückenbau", "icon": "🌉",
        "desc": "Stein- und Holzbrücken über Wasser",
        "branch": "architecture", "age": "high_medieval",
        "points": 50, "prereq": ["architecture_doors_locks"],
        "unlocks": ["build_stone_bridge"],
    },
    "architecture_temple": {
        "name": "Tempelbau", "icon": "🛐",
        "desc": "Heilige Bauten — Schrein/Tempel",
        "branch": "architecture", "age": "magic",
        "points": 95, "prereq": ["architecture_towers", "mysticism_priesthood"],
        "unlocks": ["build_temple"],
    },
    "architecture_portal_stone": {
        "name": "Portalsteine", "icon": "🌀",
        "desc": "Bauwerk-Foundation für Magie-Portale",
        "branch": "architecture", "age": "magic",
        "points": 110, "prereq": ["architecture_temple", "magic_runes"],
        "tech_print": "runic_tablet",
        "unlocks": ["build_portal_stone"],
    },
    "architecture_floating_citadel": {
        "name": "Schwebende Zitadelle", "icon": "🏯",
        "desc": "Festung in der Luft — uneinnehmbar",
        "branch": "architecture", "age": "legendary",
        "points": 320, "prereq": ["architecture_portal_stone"],
        "tech_print": "gods_tablet",
        "unlocks": ["build_floating_citadel"],
    },
    "architecture_world_wonders": {
        "name": "Weltwunder", "icon": "⭐",
        "desc": "Welt-prägende Monumente",
        "branch": "architecture", "age": "legendary",
        "points": 400, "prereq": ["architecture_floating_citadel"],
        "tech_print": "gods_tablet",
        "unlocks": ["build_world_wonder"],
    },

    # ════════════════ ❤️‍🩹  MEDIZIN  (6 Nodes) ════════════════════════════
    "medicine_first_aid": {
        "name": "Erste Hilfe", "icon": "🩹",
        "desc": "Verbände + grundlegende Wundbehandlung",
        "branch": "medicine", "age": "tribal",
        "points": 5, "prereq": [],
        "unlocks": ["craft_bandage"],
    },
    "medicine_herbal_healing": {
        "name": "Pflanzenheilkunde", "icon": "🌿",
        "desc": "Heil-Salben aus Kräutern",
        "branch": "medicine", "age": "iron",
        "points": 18, "prereq": ["medicine_first_aid", "alchemy_herbs"],
        "unlocks": ["craft_healing_salve"],
    },
    "medicine_surgery": {
        "name": "Chirurgie", "icon": "⚕️",
        "desc": "Verletzte Gliedmaßen behandeln",
        "branch": "medicine", "age": "high_medieval",
        "points": 65, "prereq": ["medicine_herbal_healing"],
        "tech_print": "healing_codex",
        "unlocks": ["surgery_table", "treat_body_part"],
    },
    "medicine_magical_healing": {
        "name": "Magische Heilung", "icon": "✨",
        "desc": "Magie-gestützte Heilung anderer Spieler",
        "branch": "medicine", "age": "magic",
        "points": 100, "prereq": ["medicine_surgery", "magic_light"],
        "unlocks": ["heal_other_spell"],
    },
    "medicine_resurrection": {
        "name": "Wiederbelebung", "icon": "💖",
        "desc": "Tote Verbündete in den letzten 60s reanimieren",
        "branch": "medicine", "age": "legendary",
        "points": 220, "prereq": ["medicine_magical_healing"],
        "tech_print": "gods_tablet",
        "unlocks": ["resurrect_spell"],
    },
    "medicine_phoenix_ashes": {
        "name": "Phönix-Asche", "icon": "🔥",
        "desc": "Selbst-Wiederbelebung bei Tod (Solo-Cooldown 1×/Tag)",
        "branch": "medicine", "age": "legendary",
        "points": 320, "prereq": ["medicine_resurrection"],
        "tech_print": "gods_tablet",
        "unlocks": ["phoenix_ash_item"],
    },

    # ════════════════ 🪙  WIRTSCHAFT  (6 Nodes) ═══════════════════════════
    "economy_barter": {
        "name": "Tauschhandel", "icon": "🤝",
        "desc": "Mit NPCs Tauschen ohne Münzen",
        "branch": "economy", "age": "tribal",
        "points": 5, "prereq": [],
        "unlocks": ["barter_trade"],
    },
    "economy_coinage": {
        "name": "Münzprägung", "icon": "🪙",
        "desc": "Kupfer/Silber/Gold-Münzen schmieden + handeln",
        "branch": "economy", "age": "iron",
        "points": 22, "prereq": ["economy_barter", "smithing_iron_smelting"],
        "unlocks": ["mint_coins"],
    },
    "economy_market": {
        "name": "Markt + Karawanen", "icon": "🏪",
        "desc": "Marktstand bauen, Karawanen anlocken",
        "branch": "economy", "age": "high_medieval",
        "points": 55, "prereq": ["economy_coinage"],
        "unlocks": ["build_market_stall", "summon_caravan"],
    },
    "economy_banking": {
        "name": "Bankwesen", "icon": "🏦",
        "desc": "Münzen sicher lagern + Zinsen",
        "branch": "economy", "age": "magic",
        "points": 90, "prereq": ["economy_market"],
        "tech_print": "trade_ledger",
        "unlocks": ["build_bank"],
    },
    "economy_guild_charter": {
        "name": "Händlergilde", "icon": "📜",
        "desc": "Handelsmonopole + Preis-Boni",
        "branch": "economy", "age": "magic",
        "points": 120, "prereq": ["economy_banking"],
        "tech_print": "trade_ledger",
        "unlocks": ["merchants_guild_charter"],
    },
    "economy_imperial_trade": {
        "name": "Imperiums-Handel", "icon": "👑",
        "desc": "Ferne Königreiche freischalten — Exotic-Waren",
        "branch": "economy", "age": "legendary",
        "points": 280, "prereq": ["economy_guild_charter"],
        "tech_print": "gods_tablet",
        "unlocks": ["imperial_caravan"],
    },

    # ════════════════ ⛪  MYSTIK  (6 Nodes) ════════════════════════════════
    "mysticism_animism_rites": {
        "name": "Animistische Riten", "icon": "🪶",
        "desc": "Geister-Anrufung + Natur-Pakte",
        "branch": "mysticism", "age": "tribal",
        "points": 6, "prereq": [],
        "unlocks": ["nature_ritual"],
    },
    "mysticism_priesthood": {
        "name": "Priesterschaft", "icon": "🙏",
        "desc": "Priester-Klasse + Gebet-Boni",
        "branch": "mysticism", "age": "iron",
        "points": 22, "prereq": ["mysticism_animism_rites"],
        "unlocks": ["pray_at_shrine"],
    },
    "mysticism_monastic_orders": {
        "name": "Klosterorden", "icon": "📖",
        "desc": "Klöster mit Schriftrollen-Bibliothek",
        "branch": "mysticism", "age": "high_medieval",
        "points": 60, "prereq": ["mysticism_priesthood", "architecture_temple"],
        "unlocks": ["build_monastery"],
    },
    "mysticism_divine_pacts": {
        "name": "Götterpakte", "icon": "⚡",
        "desc": "Permanente Buffs durch Götter-Eide",
        "branch": "mysticism", "age": "magic",
        "points": 105, "prereq": ["mysticism_monastic_orders"],
        "tech_print": "gods_tablet",
        "unlocks": ["divine_pact"],
    },
    "mysticism_godhood": {
        "name": "Götter-Anrufung", "icon": "🌟",
        "desc": "Götter direkt rufen für World-Events",
        "branch": "mysticism", "age": "legendary",
        "points": 270, "prereq": ["mysticism_divine_pacts"],
        "tech_print": "gods_tablet",
        "unlocks": ["call_god"],
    },
    "mysticism_ascension": {
        "name": "Aufstieg", "icon": "🕊",
        "desc": "Endgame — Spieler wird selbst zur Halbgottheit",
        "branch": "mysticism", "age": "legendary",
        "points": 500, "prereq": ["mysticism_godhood", "alchemy_immortality_elixir"],
        "tech_print": "gods_tablet",
        "unlocks": ["ascension_ritual"],
    },
}


# ─── Welle 30c — Tree-Meta für UI ───────────────────────────────────────
# Welche Branches gibt es, wie sind sie benannt, welche Farbe für Tree-View.
RESEARCH_BRANCHES = [
    {"id": "smithing",     "label": "Schmiedekunst",    "icon": "⚒️", "color": "#c89060"},
    {"id": "alchemy",      "label": "Alchemie",         "icon": "⚗️", "color": "#80c060"},
    {"id": "magic",        "label": "Magie",            "icon": "✨", "color": "#8060c0"},
    {"id": "agriculture",  "label": "Landwirtschaft",   "icon": "🌾", "color": "#c0c060"},
    {"id": "architecture", "label": "Architektur",      "icon": "🏛️", "color": "#a0a0a0"},
    {"id": "medicine",     "label": "Medizin",          "icon": "❤️‍🩹", "color": "#e85070"},
    {"id": "economy",      "label": "Wirtschaft",       "icon": "🪙", "color": "#e8c050"},
    {"id": "mysticism",    "label": "Mystik",           "icon": "⛪", "color": "#a060c0"},
]
RESEARCH_AGES = [
    {"id": "tribal",        "label": "Stammeszeit",       "icon": "🪵", "tier": 1},
    {"id": "iron",          "label": "Eisen-Zeit",        "icon": "⚔️", "tier": 2},
    {"id": "high_medieval", "label": "Hochmittelalter",   "icon": "🏰", "tier": 3},
    {"id": "magic",         "label": "Magisches Zeitalter","icon": "🔮", "tier": 4},
    {"id": "legendary",     "label": "Legendär",          "icon": "⭐", "tier": 5},
]


async def is_node_done(player_name: str, node_id: str) -> bool:
    """Welle 22: prüft ob ein bestimmter Forschungs-Knoten abgeschlossen ist."""
    row = await db.pool().fetchrow(
        "SELECT done FROM research_progress "
        "WHERE player_name = $1 AND node_id = $2",
        player_name, node_id,
    )
    return bool(row and row["done"])


SCHEMA = """
CREATE TABLE IF NOT EXISTS research_progress (
    player_name TEXT NOT NULL,
    node_id     TEXT NOT NULL,
    points      INTEGER NOT NULL DEFAULT 0,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (player_name, node_id)
);
"""


async def get_pool(player_name: str) -> int:
    row = await db.pool().fetchrow(
        "SELECT research_pool FROM players WHERE name = $1", player_name,
    )
    return int(row["research_pool"]) if row else 0


async def award_points(player_name: str, n: int, reason: str = "") -> int:
    """Welle 22: addiert n Forschungspunkte in den Pool des Spielers.
    Returns neuer Pool-Stand. Reason ist nur fürs Logging."""
    if n <= 0:
        return await get_pool(player_name)
    row = await db.pool().fetchrow(
        "UPDATE players SET research_pool = research_pool + $1 "
        "WHERE name = $2 RETURNING research_pool",
        n, player_name,
    )
    if row is None:
        return 0
    log.debug("research_pool %s += %d (%s) → %d", player_name, n, reason, row["research_pool"])
    return int(row["research_pool"])


def _normalize_prereq(prereq) -> list[str]:
    """Welle 30c: prereq darf Liste, String oder None sein."""
    if prereq is None:
        return []
    if isinstance(prereq, str):
        return [prereq]
    return list(prereq)


async def get_player_research(player_name: str) -> dict:
    """Returns {nodes: {node_id: {...}}, pool: N, branches, ages}.
    Pool wird mit zurückgegeben damit Frontend ihn anzeigen kann.
    Branches+Ages-Meta für Tree-Visualization."""
    rows = await db.pool().fetch(
        "SELECT node_id, points, done FROM research_progress WHERE player_name = $1",
        player_name,
    )
    progress = {r["node_id"]: {"points": r["points"], "done": r["done"]} for r in rows}
    nodes = {}
    for node_id, cfg in RESEARCH_NODES.items():
        p = progress.get(node_id, {"points": 0, "done": False})
        prereqs = _normalize_prereq(cfg.get("prereq"))
        # available = ALLE prereqs done
        available = all(progress.get(pr, {}).get("done", False) for pr in prereqs)
        # Tech-Print-Check: ist das Item im Inventar?
        has_tech_print = True
        tech_print = cfg.get("tech_print")
        if tech_print:
            try:
                row = await db.pool().fetchrow(
                    "SELECT 1 FROM items WHERE owner = $1 AND kind = $2 "
                    "AND equipped_slot IS NULL AND quantity >= 1 LIMIT 1",
                    player_name, tech_print,
                )
                has_tech_print = (row is not None)
            except Exception:
                has_tech_print = False
        nodes[node_id] = {
            "name":       cfg["name"],
            "icon":       cfg["icon"],
            "desc":       cfg.get("desc", ""),
            "points":     p["points"],
            "points_max": cfg["points"],
            "done":       p["done"],
            "available":  available,
            "prereq":     prereqs,
            "unlocks":    cfg.get("unlocks", []),
            # Welle 30c — Tree-Meta
            "branch":     cfg.get("branch"),
            "age":        cfg.get("age"),
            "tech_print":     tech_print,
            "has_tech_print": has_tech_print,
        }
    return {
        "nodes": nodes,
        "pool":  await get_pool(player_name),
        "branches": RESEARCH_BRANCHES,
        "ages":     RESEARCH_AGES,
    }


async def invest(player_name: str, node_id: str, points: int = 1) -> dict | None:
    """Spieler investiert points in einen Knoten — verbraucht Pool-Punkte.
    Welle 30c: Prereq als Liste; tech_print muss im Inventar sein (wird beim
    Node-Complete consumed)."""
    cfg = RESEARCH_NODES.get(node_id)
    if cfg is None:
        return None
    # Check prereqs (alle müssen done sein)
    prereqs = _normalize_prereq(cfg.get("prereq"))
    if prereqs:
        rows = await db.pool().fetch(
            "SELECT node_id, done FROM research_progress "
            "WHERE player_name = $1 AND node_id = ANY($2::text[])",
            player_name, prereqs,
        )
        done_set = {r["node_id"] for r in rows if r["done"]}
        missing = [pr for pr in prereqs if pr not in done_set]
        if missing:
            return {"error": "prereq_missing", "missing": missing}
    # Tech-Print-Check (für Late-Game-Nodes)
    tech_print = cfg.get("tech_print")
    if tech_print:
        tp_row = await db.pool().fetchrow(
            "SELECT 1 FROM items WHERE owner = $1 AND kind = $2 "
            "AND equipped_slot IS NULL AND quantity >= 1 LIMIT 1",
            player_name, tech_print,
        )
        if tp_row is None:
            return {"error": "tech_print_missing", "tech_print": tech_print}
    # Pool-Check + Decrement (atomar)
    pool_row = await db.pool().fetchrow(
        "UPDATE players SET research_pool = research_pool - $1 "
        "WHERE name = $2 AND research_pool >= $1 "
        "RETURNING research_pool",
        points, player_name,
    )
    if pool_row is None:
        return {"error": "not_enough_points", "pool": await get_pool(player_name)}
    new_pool = int(pool_row["research_pool"])
    # Vorherigen done-Status merken um zu wissen ob wir gerade fertig wurden
    prev = await db.pool().fetchrow(
        "SELECT done FROM research_progress WHERE player_name = $1 AND node_id = $2",
        player_name, node_id,
    )
    was_done = bool(prev and prev["done"])
    # Investiere in Node
    row = await db.pool().fetchrow(
        "INSERT INTO research_progress (player_name, node_id, points, done) "
        "VALUES ($1, $2, $3, FALSE) "
        "ON CONFLICT (player_name, node_id) DO UPDATE "
        "SET points = LEAST(research_progress.points + $3, $4), "
        "    done = (research_progress.points + $3 >= $4) "
        "RETURNING points, done",
        player_name, node_id, points, cfg["points"],
    )
    just_completed = (not was_done) and row["done"]
    # Tech-Print consumen wenn Node gerade fertig wurde
    if just_completed and tech_print:
        try:
            import items as _items
            _mgr = _items.ItemManager()
            await _mgr.consume_one(player_name, tech_print)
        except Exception:
            log.exception("Tech-Print consume fehlgeschlagen für %s", tech_print)
    return {
        "node_id":    node_id,
        "points":     row["points"],
        "points_max": cfg["points"],
        "done":       row["done"],
        "unlocks":    cfg.get("unlocks", []) if row["done"] else [],
        "pool":       new_pool,
        "tech_print_consumed": tech_print if just_completed and tech_print else None,
    }


# ─── Time-Tick Worker (Welle 22) ────────────────────────────────────────────
async def time_tick_loop(connection_manager) -> None:
    """Alle TICK Sekunden bekommt jeder online-Spieler +TICK_POINTS Pool-Punkte.
    Belohnt aktive Online-Zeit auch bei idle.

    Welle 30: Tick auf 2h erhöht (war 5min). Forschung soll keine "Sand am
    Strand"-Resource sein — der Pool wird primär durch Quest-Rewards und
    Skill-Level-Ups gefüllt, der Tick ist nur eine kleine Idle-Belohnung.
    """
    import asyncio
    import os
    tick_seconds = int(os.environ.get("RESEARCH_TICK_SECONDS", "7200"))   # 2h
    tick_points  = int(os.environ.get("RESEARCH_TICK_POINTS", "1"))
    log.info("Research-Tick-Loop startet (alle %ds +%d Pool)",
             tick_seconds, tick_points)
    while True:
        try:
            await asyncio.sleep(tick_seconds)
            for name in list(connection_manager.get_players().keys()):
                new_pool = await award_points(name, tick_points, "time_tick")
                ws = connection_manager.connections.get(name)
                if ws is not None:
                    try:
                        await ws.send_json({
                            "type": "research_pool_update",
                            "pool": new_pool,
                            "gained": tick_points,
                            "reason": "🕐 Zeit",
                        })
                    except Exception:
                        pass
        except asyncio.CancelledError:
            log.info("Research-Tick-Loop gestoppt")
            raise
        except Exception:
            log.exception("Research-Tick-Loop Iteration fehlgeschlagen")


async def is_unlocked(player_name: str, unlock_key: str) -> bool:
    """Prüft ob ein Spieler einen unlock-key (z.B. Recipe-ID) freigeschaltet hat."""
    rows = await db.pool().fetch(
        "SELECT node_id FROM research_progress "
        "WHERE player_name = $1 AND done = TRUE",
        player_name,
    )
    for r in rows:
        node = RESEARCH_NODES.get(r["node_id"])
        if node and unlock_key in node["unlocks"]:
            return True
    return False
