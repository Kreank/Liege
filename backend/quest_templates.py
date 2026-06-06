"""Welle 23 — Quest-Template-Library.

Skyrim-Radiant-Pattern: jedes Template hat Aliases (`<giver>`, `<target>`,
`<location>`, `<reward_item>`), die beim Quest-Spawn mit konkreten Welt-
Referenzen gefüllt werden. Resultat: ein Template erzeugt unzählige Varianten.

Quest-Typen:
    kill     — töte N×<creature_kind>
    fetch    — bringe N×<item_kind>
    deliver  — bringe Item zu <target_npc>
    talk     — sprich mit <target_npc>
    visit    — besuche <location>
    bounty   — töte named-mob (single, hochwertig)
    escort   — begleite NPC nach <location>
    defend   — halte <location> N Sekunden gegen Welle

Template-Felder:
    id              — eindeutig
    type            — quest-type oben
    title_template  — String mit {placeholders}
    desc_template   — Story-Beschreibung
    giver_kinds     — welche NPC-Kinds bieten diese Quest an (z.B. ['guard','quest_giver'])
    receiver_kinds  — welche NPC-Kinds nehmen sie zurück (None = giver = receiver)
    objective       — {type-specific, kann Aliases enthalten}
    reward          — {item: count, gold: int, xp: int, faction: {name: delta}}
    min_level       — Combat-Level-Floor (default 0)
    max_level       — Combat-Level-Ceiling (default 999)
    tier            — Difficulty 1-4
    faction_req     — {faction: min_rep} optional
"""

QUEST_TEMPLATES = [
    # ────────────────────────────── KILL ─────────────────────────────────
    {
        "id": "kill_wolves_basic",
        "type": "kill",
        "title_template": "Wölfe vertreiben",
        "desc_template": ("Die Wölfe machen unser Vieh nervös. Erleg {count} "
                          "von ihnen, dann hast du Ruhe vor mir."),
        "giver_kinds": ["farmer", "peasant", "villager", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "wolf", "count": 3},
        "reward": {"items": {"leather": 3}, "gold": 8,
                   "faction": {"village": 2}},
        "min_level": 0, "max_level": 6, "tier": 1,
    },
    {
        "id": "kill_goblins",
        "type": "kill",
        "title_template": "Goblin-Plage",
        "desc_template": "Erleg {count} Goblins. Sie werden zu zahlreich.",
        "giver_kinds": ["guard", "quest_giver", "village_elder"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "goblin", "count": 4},
        "reward": {"items": {"cloth": 4}, "gold": 12,
                   "faction": {"village": 3}},
        "min_level": 1, "max_level": 8, "tier": 1,
    },
    {
        "id": "kill_bandits",
        "type": "kill",
        "title_template": "Räuber im Wald",
        "desc_template": "Vertreibe {count} Banditen aus unseren Wäldern.",
        "giver_kinds": ["guard", "merchant", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "bandit", "count": 2},
        "reward": {"items": {"sword": 1}, "gold": 20, "research": 3,
                   "faction": {"village": 5, "bandits": -3}},
        "min_level": 2, "max_level": 10, "tier": 2,
    },
    {
        "id": "kill_thieves",
        "type": "kill",
        "title_template": "Diebe im Königreich",
        "desc_template": "Die Stadtwache fasst die Diebe nicht. Erleg {count}.",
        "giver_kinds": ["merchant", "guard"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "thief", "count": 3},
        "reward": {"items": {"silver_coin": 8}, "gold": 25, "research": 3,
                   "faction": {"village": 4, "bandits": -4}},
        "min_level": 2, "max_level": 10, "tier": 2,
    },
    {
        "id": "kill_skeletons",
        "type": "kill",
        "title_template": "Untote im Friedhof",
        "desc_template": "Reinige den alten Friedhof — {count} Skelette müssen fallen.",
        "giver_kinds": ["priest", "scholar", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "skeleton", "count": 5},
        "reward": {"items": {"bone": 5, "scroll": 1}, "gold": 18, "research": 3,
                   "faction": {"undead_cult": -5}},
        "min_level": 3, "max_level": 12, "tier": 2,
    },
    {
        "id": "kill_spiders",
        "type": "kill",
        "title_template": "Riesenspinnen-Plage",
        "desc_template": "Die Spinnen im Wald werden zur Gefahr. Töte {count}.",
        "giver_kinds": ["hunter", "woodcutter", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "giant_spider", "count": 3},
        "reward": {"items": {"cloth": 8}, "gold": 22, "research": 4,
                   "faction": {"village": 3, "wild_beasts": -2}},
        "min_level": 4, "max_level": 14, "tier": 2,
    },
    {
        "id": "kill_dire_wolves",
        "type": "kill",
        "title_template": "Schreckenswölfe",
        "desc_template": "Ein Rudel Schreckenswölfe hat unsere Karawane überfallen. {count} müssen sterben.",
        "giver_kinds": ["merchant", "guard", "hunter"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "dire_wolf", "count": 2},
        "reward": {"items": {"leather": 6, "raw_meat": 5}, "gold": 30, "research": 8,
                   "faction": {"wild_beasts": -3}},
        "min_level": 6, "max_level": 16, "tier": 3,
    },
    {
        "id": "kill_treants",
        "type": "kill",
        "title_template": "Wütender Wald",
        "desc_template": "Die Treants sind erwacht und bedrohen die Holzfäller. Erleg {count}.",
        "giver_kinds": ["woodcutter", "guard"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "treant", "count": 1},
        "reward": {"items": {"wood": 25, "crystal": 2}, "gold": 40, "research": 10,
                   "faction": {"village": 4}},
        "min_level": 7, "max_level": 18, "tier": 3,
    },
    # ────────────────────────────── FETCH ────────────────────────────────
    {
        "id": "fetch_wood",
        "type": "fetch",
        "title_template": "Holz für die Schmiede",
        "desc_template": "Bring mir {count} Stück Holz. Meine Vorräte sind erschöpft.",
        "giver_kinds": ["blacksmith", "carpenter", "smithy"],
        "receiver_kinds": None,
        "objective": {"item_kind": "wood", "count": 10},
        "reward": {"items": {"copper_coin": 8}, "gold": 5,
                   "faction": {"village": 1}},
        "min_level": 0, "max_level": 6, "tier": 1,
    },
    {
        "id": "fetch_iron",
        "type": "fetch",
        "title_template": "Eisen aus den Bergen",
        "desc_template": "Ich brauche {count} Eisenerz. Die Bergwerke sind gefährlich, sei vorsichtig.",
        "giver_kinds": ["blacksmith", "smithy"],
        "receiver_kinds": None,
        "objective": {"item_kind": "iron_ore", "count": 5},
        "reward": {"items": {"silver_coin": 3}, "gold": 12,
                   "faction": {"village": 2}},
        "min_level": 1, "max_level": 8, "tier": 1,
    },
    {
        "id": "fetch_herbs",
        "type": "fetch",
        "title_template": "Heilkräuter sammeln",
        "desc_template": "Ich brauche {count} Heilkräuter für meine Tinkturen.",
        "giver_kinds": ["healer", "priest", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "herb", "count": 8},
        "reward": {"items": {"health_potion": 2}, "gold": 8,
                   "faction": {"village": 1}},
        "min_level": 0, "max_level": 6, "tier": 1,
    },
    {
        "id": "fetch_bones",
        "type": "fetch",
        "title_template": "Knochen für das Ritual",
        "desc_template": "Bring mir {count} Knochen. Frag nicht warum.",
        "giver_kinds": ["scholar", "hermit", "mage"],
        "receiver_kinds": None,
        "objective": {"item_kind": "bone", "count": 6},
        "reward": {"items": {"scroll": 1}, "gold": 10},
        "min_level": 0, "max_level": 8, "tier": 1,
    },
    {
        "id": "fetch_leather",
        "type": "fetch",
        "title_template": "Leder für die Sattlerei",
        "desc_template": "Mein Vorrat ist aus. {count} Lederstücke, bitte.",
        "giver_kinds": ["tailor", "merchant"],
        "receiver_kinds": None,
        "objective": {"item_kind": "leather", "count": 7},
        "reward": {"items": {"cloth": 4}, "gold": 12,
                   "faction": {"village": 1}},
        "min_level": 0, "max_level": 8, "tier": 1,
    },
    {
        "id": "fetch_crystals",
        "type": "fetch",
        "title_template": "Kristalle für den Zauber",
        "desc_template": "Sammle {count} Kristalle. Sie sind selten, ich weiß.",
        "giver_kinds": ["mage", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "crystal", "count": 4},
        "reward": {"items": {"mana_potion": 3, "scroll": 1}, "gold": 25, "research": 4,
                   "faction": {"village": 2}},
        "min_level": 3, "max_level": 14, "tier": 2,
    },
    {
        "id": "fetch_gold_ore",
        "type": "fetch",
        "title_template": "Goldräusch",
        "desc_template": "Ich bezahle gut für {count} Stücke Golderz.",
        "giver_kinds": ["merchant", "blacksmith"],
        "receiver_kinds": None,
        "objective": {"item_kind": "gold_ore", "count": 3},
        "reward": {"items": {"gold_coin": 2}, "gold": 35, "research": 5,
                   "faction": {"village": 2}},
        "min_level": 4, "max_level": 15, "tier": 2,
    },
    {
        "id": "fetch_mythril",
        "type": "fetch",
        "title_template": "Mythril für den Meister",
        "desc_template": "Bring mir {count} Mythril. Nur die Berge geben es her.",
        "giver_kinds": ["blacksmith"],
        "receiver_kinds": None,
        "objective": {"item_kind": "mythril_ore", "count": 2},
        "reward": {"items": {"steel_ingot": 3, "gold_coin": 3}, "gold": 60, "research": 12,
                   "faction": {"village": 4}},
        "min_level": 7, "max_level": 20, "tier": 3,
    },
    {
        "id": "fetch_meat",
        "type": "fetch",
        "title_template": "Fleisch für die Taverne",
        "desc_template": "Die Gäste haben Hunger. {count} rohes Fleisch, bitte.",
        "giver_kinds": ["innkeeper", "baker"],
        "receiver_kinds": None,
        "objective": {"item_kind": "raw_meat", "count": 6},
        "reward": {"items": {"bread": 4, "cooked_meat": 2}, "gold": 14,
                   "faction": {"village": 2}},
        "min_level": 0, "max_level": 8, "tier": 1,
    },
    # ────────────────────────────── BOUNTY ────────────────────────────────
    # Bounties = einzelne harte Kills, hochwertige Rewards
    {
        "id": "bounty_ogre",
        "type": "kill",
        "title_template": "Kopfgeld: Oger",
        "desc_template": "Ein Oger terrorisiert die Berge. Kopfgeld für seine Erledigung.",
        "giver_kinds": ["guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "ogre", "count": 1},
        "reward": {"items": {"gold_coin": 8, "chestplate": 1}, "gold": 100, "research": 18,
                   "faction": {"village": 8}},
        "min_level": 8, "max_level": 99, "tier": 3,
    },
    {
        "id": "bounty_necromancer",
        "type": "kill",
        "title_template": "Kopfgeld: Nekromant",
        "desc_template": "Ein Nekromant beschwört die Toten. Beende ihn.",
        "giver_kinds": ["priest", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "necromancer", "count": 1},
        "reward": {"items": {"spell_book": 1, "gold_coin": 10}, "gold": 150, "research": 25,
                   "faction": {"village": 10, "undead_cult": -10}},
        "min_level": 10, "max_level": 99, "tier": 4,
    },
    {
        "id": "bounty_dragon_whelp",
        "type": "kill",
        "title_template": "Kopfgeld: Drachenwelpe",
        "desc_template": "Ein junger Drache plündert Karawanen. Wer ihn fällt, wird reich.",
        "giver_kinds": ["merchant", "guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "dragon_whelp", "count": 1},
        "reward": {"items": {"gold_coin": 15, "mythril_ore": 3, "scroll": 2}, "gold": 200, "research": 35,
                   "faction": {"village": 12}},
        "min_level": 12, "max_level": 99, "tier": 4,
    },
    # ────────────────────────────── OVERWORLD-BOUNTIES (Welle 34c) ──────
    # Kopfgelder auf benannte Overworld-Bosse + Rare-Mobs aus
    # `overworld_monster_pool`. creature_kind ist exakt der overworld_*-Slug,
    # weil `quests.on_creature_killed` per String-Equality matched.
    {
        "id": "bounty_orgrim_basher",
        "type": "kill",
        "title_template": "Kopfgeld: Orgrim-Schläger",
        "desc_template": ("Ein Orgrim-Schläger walzt durch unsere Vorposten. "
                          "Bring ihn zur Strecke, dann ist die Belohnung dein."),
        "giver_kinds": ["guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "overworld_orgrim_basher", "count": 1},
        "reward": {"items": {"gold_coin": 6, "crude_steel_ingot": 2}, "gold": 80, "research": 15,
                   "faction": {"village": 7}},
        "min_level": 6, "max_level": 99, "tier": 3,
    },
    {
        "id": "bounty_brigand_captain",
        "type": "kill",
        "title_template": "Kopfgeld: Räuber-Hauptmann",
        "desc_template": ("Der Räuber-Hauptmann hält die Handelsstraße in Schach. "
                          "Fäll ihn — die Stadtwache zahlt gut."),
        "giver_kinds": ["guard", "merchant", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "overworld_brigand_captain", "count": 1},
        "reward": {"items": {"gold_coin": 5, "leather_armor_piece": 1}, "gold": 90, "research": 14,
                   "faction": {"village": 8, "bandits": -8}},
        "min_level": 5, "max_level": 99, "tier": 3,
    },
    {
        "id": "bounty_ridge_drake",
        "type": "kill",
        "title_template": "Kopfgeld: Felsdrache",
        "desc_template": ("Ein Felsdrache hat sich über dem Pass eingenistet. "
                          "Wer ihn fällt, erhält ein Vermögen."),
        "giver_kinds": ["merchant", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "overworld_apex_ridge_drake", "count": 1},
        "reward": {"items": {"gold_coin": 18, "drake_scale": 4, "mythril_ore": 2}, "gold": 220, "research": 38,
                   "faction": {"village": 12}},
        "min_level": 12, "max_level": 99, "tier": 4,
    },
    {
        "id": "bounty_cliff_kraken_arm",
        "type": "kill",
        "title_template": "Kopfgeld: Klippen-Kraken",
        "desc_template": ("Aus der See greift ein Kraken-Arm nach den Fischern. "
                          "Hack ihn ab, dann sind unsere Boote sicher."),
        "giver_kinds": ["merchant", "guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "overworld_apex_cliff_kraken_arm", "count": 1},
        "reward": {"items": {"gold_coin": 16, "pearl_great": 1, "kraken_ink": 3}, "gold": 200, "research": 32,
                   "faction": {"village": 10}},
        "min_level": 11, "max_level": 99, "tier": 4,
    },
    {
        "id": "bounty_eyeless_pilgrim",
        "type": "kill",
        "title_template": "Kopfgeld: Augenloser Pilger",
        "desc_template": ("Der augenlose Pilger zieht über das Land — wo er hinkommt, "
                          "verschwinden Reisende spurlos. Beende ihn, leise."),
        "giver_kinds": ["priest", "scholar", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"creature_kind": "overworld_aberrant_eyeless_pilgrim", "count": 1},
        "reward": {"items": {"gold_coin": 10, "forehead_eye": 1, "scroll": 2}, "gold": 140, "research": 28,
                   "faction": {"village": 9, "undead_cult": -6}},
        "min_level": 8, "max_level": 99, "tier": 3,
    },
    # ────────────────────────────── SAMMEL-QUESTS (Welle 34c) ───────────
    # Bring-N-Trophy-Items von Monster-Drops. Counts so gewählt, dass
    # 2-4 Mobs reichen (Drops rollen mit 8-100% Weights).
    {
        "id": "collect_goblin_ears",
        "type": "fetch",
        "title_template": "Goblin-Ohren sammeln",
        "desc_template": ("Bring mir {count} Goblin-Ohren — der Sold der Wache wird "
                          "pro Stück ausgezahlt."),
        "giver_kinds": ["guard", "hunter", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"item_kind": "goblin_ear", "count": 5},
        "reward": {"items": {"silver_coin": 6}, "gold": 22, "research": 4,
                   "faction": {"village": 4}},
        "min_level": 1, "max_level": 10, "tier": 1,
    },
    {
        "id": "collect_drake_scales",
        "type": "fetch",
        "title_template": "Drachen-Schuppen für die Schmiede",
        "desc_template": ("Ich rüste eine besondere Klinge — bring mir {count} "
                          "Drachen-Schuppen aus den Bergen."),
        "giver_kinds": ["blacksmith"],
        "receiver_kinds": None,
        "objective": {"item_kind": "drake_scale", "count": 10},
        "reward": {"items": {"crystal": 3, "gold_coin": 1, "steel_ingot": 2}, "gold": 70, "research": 14,
                   "faction": {"village": 5}},
        "min_level": 8, "max_level": 99, "tier": 3,
    },
    {
        "id": "collect_wolf_pelts",
        "type": "fetch",
        "title_template": "Wolfsfelle für den Pelzhändler",
        "desc_template": ("Die Wintermäntel verkaufen sich wie nie — bring mir "
                          "{count} Wolfsfelle, dann zahlen wir."),
        "giver_kinds": ["hunter", "merchant", "tailor"],
        "receiver_kinds": None,
        "objective": {"item_kind": "wolf_pelt", "count": 4},
        "reward": {"items": {"leather": 2, "silver_coin": 4}, "gold": 16, "research": 3,
                   "faction": {"village": 2}},
        "min_level": 2, "max_level": 12, "tier": 1,
    },
    {
        "id": "collect_arctic_pelts",
        "type": "fetch",
        "title_template": "Arktis-Felle für den Hof",
        "desc_template": ("Die Adligen verlangen warme Mäntel. {count} Arktis-Felle, "
                          "von Gletscher-Luchsen, nichts anderes."),
        "giver_kinds": ["hunter", "merchant", "tailor"],
        "receiver_kinds": None,
        "objective": {"item_kind": "arctic_pelt", "count": 3},
        "reward": {"items": {"leather": 3, "silver_coin": 8}, "gold": 32, "research": 5,
                   "faction": {"village": 3}},
        "min_level": 4, "max_level": 14, "tier": 2,
    },
    {
        "id": "collect_bones_drops",
        "type": "fetch",
        "title_template": "Knochen für das Ossuar",
        "desc_template": ("Bring mir {count} Knochen — die Heiler brauchen sie für "
                          "Schienen und Sude."),
        "giver_kinds": ["healer", "priest", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "bone", "count": 20},
        "reward": {"items": {"silver_coin": 5, "health_potion": 1}, "gold": 18, "research": 3,
                   "faction": {"village": 2}},
        "min_level": 1, "max_level": 10, "tier": 1,
    },
    {
        "id": "collect_rotten_flesh",
        "type": "fetch",
        "title_template": "Faules Fleisch für den Alchimisten",
        "desc_template": ("So eklig es klingt — bring mir {count} Stücke faules Fleisch. "
                          "Die Pestphiolen brauen sich nicht selbst."),
        "giver_kinds": ["healer", "mage", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "rotten_flesh", "count": 6},
        "reward": {"items": {"health_potion": 1, "silver_coin": 4}, "gold": 20, "research": 4,
                   "faction": {"village": 2}},
        "min_level": 2, "max_level": 12, "tier": 1,
    },
    {
        "id": "collect_kraken_ink",
        "type": "fetch",
        "title_template": "Kraken-Tinte für Schriftrollen",
        "desc_template": ("{count} Phiolen Kraken-Tinte, dann kann ich endlich wieder "
                          "schreiben — die See lässt sich nicht bitten."),
        "giver_kinds": ["mage", "scholar", "scribe"],
        "receiver_kinds": None,
        "objective": {"item_kind": "kraken_ink", "count": 3},
        "reward": {"items": {"scroll": 2, "silver_coin": 6}, "gold": 30, "research": 6,
                   "faction": {"village": 3}},
        "min_level": 6, "max_level": 16, "tier": 2,
    },
    {
        "id": "collect_essence_fire",
        "type": "fetch",
        "title_template": "Feuer-Essenz für den Magier",
        "desc_template": ("Bring mir {count} Phiolen Feuer-Essenz. Mein Studium der "
                          "Flamme stockt ohne sie."),
        "giver_kinds": ["mage", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "essence_fire", "count": 2},
        "reward": {"items": {"mana_potion": 2, "scroll": 1}, "gold": 35, "research": 7,
                   "faction": {"village": 3}},
        "min_level": 5, "max_level": 16, "tier": 2,
    },
    {
        "id": "collect_essence_frost",
        "type": "fetch",
        "title_template": "Frost-Essenz für den Magier",
        "desc_template": ("{count} Phiolen Frost-Essenz, dann kann ich die Kühl-Runen "
                          "endlich abschließen."),
        "giver_kinds": ["mage", "scholar"],
        "receiver_kinds": None,
        "objective": {"item_kind": "essence_frost", "count": 2},
        "reward": {"items": {"mana_potion": 2, "scroll": 1}, "gold": 35, "research": 7,
                   "faction": {"village": 3}},
        "min_level": 5, "max_level": 16, "tier": 2,
    },
    # ────────────────────────────── BOSS-TURN-IN (Welle 34c) ────────────
    # Einmalige Boss-Trophäen — als fetch mit count=1 modelliert
    # (echtes turn_in passiert via `quests.turn_in` beim Quest-Geber).
    {
        "id": "turnin_warchief_crown",
        "type": "fetch",
        "title_template": "Krone des Goblin-Kriegshäuptlings",
        "desc_template": ("Bring mir die Krone des Goblin-Kriegshäuptlings — der "
                          "Stamm braucht ein Zeichen, dass sein Anführer fiel."),
        "giver_kinds": ["village_elder", "quest_giver", "guard"],
        "receiver_kinds": None,
        "objective": {"item_kind": "warchief_crown", "count": 1},
        "reward": {"items": {"gold_coin": 50, "steel_ingot": 3}, "gold": 250, "research": 35,
                   "faction": {"village": 15}},
        "min_level": 10, "max_level": 99, "tier": 4,
    },
    {
        "id": "turnin_witchking_crown",
        "type": "fetch",
        "title_template": "Krone des Sumpf-Hexenkönigs",
        "desc_template": ("Tief im Moor herrscht der Hexenkönig. Bring mir seine "
                          "Krone — der Hof zahlt königlich dafür."),
        "giver_kinds": ["village_elder", "quest_giver", "priest"],
        "receiver_kinds": None,
        "objective": {"item_kind": "witchking_crown", "count": 1},
        "reward": {"items": {"gold_coin": 80, "mythril_ore": 1, "rune_stone": 2}, "gold": 380, "research": 50,
                   "faction": {"village": 18, "undead_cult": -10}},
        "min_level": 13, "max_level": 99, "tier": 4,
    },
    {
        "id": "turnin_undying_crown",
        "type": "fetch",
        "title_template": "Krone des Untoten Königs",
        "desc_template": ("Aus der Krypta soll die Krone des Untoten Königs geborgen "
                          "werden — dann ist sein Bann gebrochen."),
        "giver_kinds": ["priest", "scholar", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"item_kind": "undying_crown", "count": 1},
        "reward": {"items": {"rune_stone": 3, "gold_coin": 70, "scroll": 3}, "gold": 340, "research": 48,
                   "faction": {"village": 16, "undead_cult": -15}},
        "min_level": 13, "max_level": 99, "tier": 4,
    },
    {
        "id": "turnin_pharaoh_mask",
        "type": "fetch",
        "title_template": "Maske des Wüsten-Pharao",
        "desc_template": ("Im Sand schläft der Pharao-Revenant. Bring seine Maske, "
                          "dann beweist du dem Hof, dass die Wüste ruht."),
        "giver_kinds": ["scholar", "village_elder", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"item_kind": "pharaoh_mask", "count": 1},
        "reward": {"items": {"gold_coin": 100, "scarab_amulet": 1, "rune_stone": 2}, "gold": 450, "research": 55,
                   "faction": {"village": 20}},
        "min_level": 14, "max_level": 99, "tier": 4,
    },
    {
        "id": "turnin_captain_banner",
        "type": "fetch",
        "title_template": "Banner des Räuber-Hauptmanns",
        "desc_template": ("Bring mir das Banner des Räuber-Hauptmanns — die Wache "
                          "soll wissen, dass die Straße wieder unser ist."),
        "giver_kinds": ["guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"item_kind": "captain_banner", "count": 1},
        "reward": {"items": {"silver_coin": 50, "leather_armor_piece": 1}, "gold": 120, "research": 18,
                   "faction": {"village": 10, "bandits": -10}},
        "min_level": 6, "max_level": 99, "tier": 3,
    },
    {
        "id": "turnin_orgrim_skull",
        "type": "fetch",
        "title_template": "Schädel des Orgrim",
        "desc_template": ("Häng den Orgrim-Schädel an unser Tor — der Stamm soll "
                          "sehen, dass wir keine Angst haben."),
        "giver_kinds": ["guard", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"item_kind": "orgrim_skull", "count": 1},
        "reward": {"items": {"gold_coin": 30, "iron_sword": 1}, "gold": 140, "research": 20,
                   "faction": {"village": 12}},
        "min_level": 7, "max_level": 99, "tier": 3,
    },
    {
        "id": "turnin_boss_trophy",
        "type": "fetch",
        "title_template": "Bossjäger-Aufgabe",
        "desc_template": ("Bring mir {count} Boss-Trophäen — ich sammle sie, wie "
                          "andere Münzen sammeln. Bezahlt wird fürstlich."),
        "giver_kinds": ["quest_giver", "bard"],
        "receiver_kinds": None,
        "objective": {"item_kind": "boss_trophy", "count": 3},
        "reward": {"items": {"mythril_ore": 2, "gold_coin": 100, "rune_stone": 1}, "gold": 500, "research": 60,
                   "faction": {"village": 22}},
        "min_level": 15, "max_level": 99, "tier": 4,
    },
    # ────────────────────────────── DELIVER ──────────────────────────────
    # Bring Item zu ANDEREM NPC
    {
        "id": "deliver_letter",
        "type": "deliver",
        "title_template": "Brief an die Nachbarstadt",
        "desc_template": "Bring diesen versiegelten Brief zum Wirt der nächsten Taverne.",
        "giver_kinds": ["scribe", "village_elder", "quest_giver"],
        "receiver_kinds": ["innkeeper", "tavern"],
        "objective": {"item_kind": "scroll", "count": 1, "to_kind": "innkeeper"},
        "reward": {"items": {"silver_coin": 4}, "gold": 18,
                   "faction": {"village": 3}},
        "min_level": 0, "max_level": 10, "tier": 1,
    },
    {
        "id": "deliver_potion",
        "type": "deliver",
        "title_template": "Trank für die Schmiede",
        "desc_template": "Der Schmied hat sich verletzt. Bring diesen Heiltrank zu ihm.",
        "giver_kinds": ["healer", "priest"],
        "receiver_kinds": ["blacksmith"],
        "objective": {"item_kind": "health_potion", "count": 1, "to_kind": "blacksmith"},
        "reward": {"items": {"iron_ingot": 2}, "gold": 12,
                   "faction": {"village": 2}},
        "min_level": 0, "max_level": 8, "tier": 1,
    },
    # ────────────────────────────── TALK ─────────────────────────────────
    {
        "id": "talk_elder",
        "type": "talk",
        "title_template": "Worte des Ältesten",
        "desc_template": "Geh und sprich mit dem Dorfältesten. Er hat Neuigkeiten.",
        "giver_kinds": ["villager", "peasant"],
        "receiver_kinds": ["village_elder"],
        "objective": {"to_kind": "village_elder"},
        "reward": {"gold": 5,
                   "faction": {"village": 1}},
        "min_level": 0, "max_level": 4, "tier": 1,
    },
    {
        "id": "talk_priest",
        "type": "talk",
        "title_template": "Beichte beim Priester",
        "desc_template": "Such den Priester auf und sprich mit ihm — er kennt die Antwort.",
        "giver_kinds": ["villager", "scholar"],
        "receiver_kinds": ["priest"],
        "objective": {"to_kind": "priest"},
        "reward": {"gold": 8,
                   "faction": {"village": 2}},
        "min_level": 0, "max_level": 6, "tier": 1,
    },
    # ────────────────────────────── DEFEND ───────────────────────────────
    # NEU Welle 23: halte Position für N Sekunden gegen Welle
    {
        "id": "defend_caravan",
        "type": "defend",
        "title_template": "Karawane verteidigen",
        "desc_template": "Eine Karawane wird angegriffen. Halt die Stellung 60 Sekunden!",
        "giver_kinds": ["merchant", "guard"],
        "receiver_kinds": None,
        "objective": {"duration_s": 60, "radius": 5},
        "reward": {"items": {"silver_coin": 10, "leather": 4}, "gold": 50, "research": 10,
                   "faction": {"village": 5}},
        "min_level": 5, "max_level": 16, "tier": 2,
    },
    # ────────────────────────────── ESCORT ───────────────────────────────
    # NEU Welle 23: begleite NPC nach Location
    {
        "id": "escort_merchant",
        "type": "escort",
        "title_template": "Händler eskortieren",
        "desc_template": "Eine Händlerin will zum nächsten Dorf — und braucht Schutz.",
        "giver_kinds": ["merchant", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"npc_kind": "merchant", "distance_min": 20},
        "reward": {"items": {"gold_coin": 4, "silver_coin": 6}, "gold": 60, "research": 12,
                   "faction": {"village": 6}},
        "min_level": 4, "max_level": 14, "tier": 2,
    },
    # ────────────────────────────── VISIT ────────────────────────────────
    # Besuche Location — radiant kann <location> als ruin_pillar etc. fillen
    {
        "id": "visit_ruin",
        "type": "visit",
        "title_template": "Alte Ruinen erkunden",
        "desc_template": "Geh zu den alten Ruinen und sieh nach, was sich dort regt.",
        "giver_kinds": ["scholar", "quest_giver"],
        "receiver_kinds": None,
        "objective": {"location_struct": "ruin_pillar", "radius": 5},
        "reward": {"items": {"scroll": 1}, "gold": 25, "research": 5,
                   "faction": {"village": 3}},
        "min_level": 2, "max_level": 12, "tier": 2,
    },
]

# Quest-Typen ohne funktionierenden Completion-Hook werden aus allen Angebots-
# Pools gefiltert (sonst blieben sie als 'active' für immer hängen).
# Welle 53: defend (Positions-Timer) + escort (folgender NPC) sind jetzt im
# quest_worker verdrahtet → Set ist wieder leer, beide werden angeboten.
UNSUPPORTED_QUEST_TYPES: set[str] = set()


def templates_for_npc_kind(npc_kind: str, player_level: int = 0) -> list[dict]:
    """Welche Templates kann dieser NPC anbieten, passend zum Player-Level?"""
    return [
        t for t in QUEST_TEMPLATES
        if npc_kind in t["giver_kinds"]
        and t["min_level"] <= player_level <= t["max_level"]
    ]


def receiver_kinds_for_template(template_id: str) -> list[str] | None:
    """Wo wird die Quest abgegeben? None = bei giver, sonst kind-Liste."""
    for t in QUEST_TEMPLATES:
        if t["id"] == template_id:
            return t.get("receiver_kinds")
    return None


def template_by_id(template_id: str) -> dict | None:
    for t in QUEST_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None
