# RimWorld → Liege: Mechanik-Mapping

Stand: 2026-05-30

Ziel: RimWorld-Mechaniken übernehmen, an Online-Multiplayer mit einzeln-gespielten Charakteren anpassen, dabei nicht über-engineeren.

Hinweis: Dieses Dokument war lange ungepflegt. Vieles, was hier früher als "Vorschlag/geplant" stand, ist längst implementiert. Status jetzt sauber getrennt in **✅ Erledigt**, **🔶 Teilweise/Backlog** und **⏭️ Bewusst übersprungen**.

---

## ✅ Erledigt

### 1. Skill-System (RimWorld: ~13 Skills, Level 0–20)
Umgesetzt mit **11 Skills**: mining, woodcutting, gathering, construction, crafting, combat, magic, cooking, medical, farming, social.
- Level 0–20 (RimWorld-Standard), **non-lineare XP-Kurve** (höhere Level kosten überproportional mehr).
- XP bei jeder passenden Aktion (Holz hacken = woodcutting-XP usw.).
- Höheres Level = schneller, mehr Output, höhere Qualität.
- Combat/Magic als eigene Skills statt RimWorlds Melee/Shooting-Split.
- Backend: `skills.py`

### 2. Attribute (RimWorld-Stats, neu strukturiert)
**12 Attribute** (deutsch): Stärke, Ausdauer, Energie, Intelligenz, Weisheit, Ausweichen, Geschick, Verteidigung, Charisma, Krit-Rate, Krit-Schaden, Schleichen.
- Geht über RimWorlds reine Stat-Modifier hinaus, RPG-typisches Attributmodell.
- Backend: `attributes.py`

### 3. Talent-System (über RimWorld hinaus)
**46 Talent-Nodes**, Baumstruktur mit **3 Tiers pro Skill**. Freischaltung über Skill-Progression.
- RimWorld kennt keine Talentbäume — bewusste RPG-Erweiterung.
- Backend: `talents.py`

### 4. Item-Quality (5 Stufen statt RimWorld-7)
RimWorld: awful/poor/normal/good/excellent/masterwork/legendary.
Wir: **roh / normal / fein / meisterhaft / legendär**.
- Hängt vom Skill des Crafters ab (Random-Roll mit Skill als Bias).
- Stats-Boost je Stufe (z.B. Schwert fein +20% Damage, meisterhaft +50%).
- UI: Item-Name mit Qualitäts-Präfix (z.B. "✨ Meisterhaftes Eisenschwert").

### 5. Bedürfnisse (RimWorld: Food/Rest als Need-Bars)
Umgesetzt: **Hunger + Durst + Stamina/Schlaf**.
- Hunger & Durst sinken langsam; bei 0 nimmt HP ab.
- **Stamina-System**: Sprint kostet 8 Stamina/s (via Shift), Bau-Aktion kostet 6 Stamina.
- **Bett-Schlaf**: +8 Stamina/s und +4 HP/s.
- Essen/Trinken restoren Hunger/Durst (Food-Items aus Crafting/Loot/Farming).
- Backend: `needs.py`

### 6. KI-Storyteller-Modi (Cassandra/Phoebe/Randy)
Storyteller-Modi + KI-getriebene Events sind live.
- Modus beeinflusst Event-Frequenz, Spawn-Härte etc.
- Slow Brain / LLM erzeugt Narrative; Mechanik bleibt server-deterministisch.
- Backend: `storyteller.py`, `event_worker.py`

### 7. Crafting-Bills (Queue statt Single-Click)
RimWorld: Werkbank mit Bill-Liste ("mach 5 Schwerter dann stop").
Umgesetzt: **4 Stationen** (hand / workbench / furnace / anvil) mit **Bills/Queue**.
- Worker checkt Material und arbeitet die Queue sequenziell ab.
- Backend: `recipes.py`, `bill_queue.py`

### 8. Body-Parts-Health
RimWorld: Körperteile mit eigenen HP.
Umgesetzt: **3 Slots — Beine / Arme / Torso** (Move-Speed, Combat-Damage, Max-HP).
- Heilung repariert Wunden.

### 9. Factions / Reputation
Fraktionen mit Reputationssystem umgesetzt (RimWorld: Faction-Goodwill).

### 10. Research-Tree / Tech-Progression
RimWorld: mehrstufige Forschung schaltet Recipes frei.
Umgesetzt: **70 Research-Nodes**, **5 Tech-Ages × 8 Branches**.
- Forschungspunkte kommen aus **Skill-Levelups**.
- Backend: `research.py`

### 11. Raids / Gruppenspiel (eskalierende Raids)
RimWorld: periodische Raids, Schwere skaliert mit Colony-Wealth.
Umgesetzt als Multiplayer-Gruppensystem:
- **Party (5) / Raid20 / Raid40**.
- **Loot-Regeln**: ffa und need_greed; **XP-Share** in der Gruppe.
- Raids server-getrieben über Director.
- Backend: `groups.py`, `raid_director.py`

---

## Neu seit Projektstart (kein direktes RimWorld-Äquivalent, ✅ erledigt)

### 12. Währung / Geldbeutel
**Kupfer / Silber / Gold** (100 Kupfer = 1 Silber, 100 Silber = 1 Gold), `wallet_copper` am Spieler.
- Backend: `currency.py`

### 13. Multi-Floor-Dungeons
**5-Tier-System** mit mehreren Floors, **Reaper**, **Auto-Spawn** und **tier-skaliertem Loot**.
- Eigene instanzierte Layer (vgl. RimWorld Ancient Danger / Quest-Sites, aber als echte Dungeons).
- Backend: `dungeon_director.py`, `dungeon_instance.py`, `dungeon_tiers.py`, `dungeon_themes.py`, `dungeon_world.py`, `dungeons.py`

### 14. Monster-Longlist
**133-Monster-Longlist** on-map, daten-getrieben aus Manifest, plus **Bestiarium-UI**.
- Backend: `monster_longlist.py`

### 15. Quests
**KI-generiert**: Narrative via LLM, Mechanik server-deterministisch.

---

## 🔶 Teilweise / Backlog

### Mood + Mental Breaks (RimWorld: low mood → mental break)
- Für Spieler bewusst **nicht** (kein Soft-Lock-Risiko).
- Für **NPCs** angedacht: Mood aus erlebten Tötungen / Treffern / Versorgung, Mental Break = Flucht/ziellos.
- Noch offen / Backlog.

### Tod-Strafe (Death Penalty)
- Geplant, Form noch offen. Ohne Penalty ist die hohe Mob-Skalierung Theater.
- Backlog.

### Persistentes Quest-Board
- Über die KI-Quests hinaus: persistente Struktur, Spieler reichen Quests ein + nehmen an.
- Kommt nach dem Capital-Feature.

---

## ⏭️ Bewusst übersprungen (out-of-scope)

- **Pawn-Recruitment** — ein Charakter pro Spieler, keine Crew.
- **Beziehungen zwischen mehreren eigenen Pawns** — n/a beim Single-Char-Modell.
- **Power-Grid** (Strom-Verteilung) — zu komplex.
- **Temperature-System** als Game-Mechanik (Frostbrand etc.) — zu fummelig.
- **World-Map / Caravans** — die Welt selbst ist die Map; Multi-World nur als Dungeon-Layer realisiert.
- **Animals tame / Schlachten** — evtl. späteres Update.
- **Drugs** (suchterzeugende Tränke) — passt nicht zum Stil.
