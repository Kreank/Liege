# RimWorld → Liege: Mechanik-Mapping

Stand: 2026-05-25

Ziel: RimWorld-Mechaniken übernehmen, an Online-Multiplayer mit einzeln-gespielten Charakteren anpassen, dabei nicht über-engineering.

## Direkt übernehmbar (Tier 1 — fokus)

### 1. Skill-System
RimWorld hat ~13 Skills pro Pawn (Construction, Mining, Cooking, Crafting, Melee, Shooting, ...).
- Wir: ähnliches Set pro Spieler. Vorschlag:
  - **Mining** (Felsen/Erze)
  - **Woodcutting** (Bäume)
  - **Construction** (Bauen)
  - **Crafting** (Werkbank/Schmelze/Amboss)
  - **Combat** (Melee + Range, evtl. split)
  - **Magic** (Spells)
  - **Cooking** (später wenn Food-System)
  - **Medicine** (später wenn Heal-System komplexer)
- Skill-Level 0–20 (RimWorld-Standard)
- XP-Gain bei jeder Aktion (Holz hacken = Woodcutting-XP)
- Höheres Level = schneller, mehr Output, höhere Qualität

### 2. Item-Quality (5 Stufen statt RimWorld-7)
RimWorld: awful/poor/normal/good/excellent/masterwork/legendary.
Wir vereinfacht: **roh / normal / fein / meisterhaft / legendär**.
- Hängt vom Skill des Crafters ab (Random-Roll mit Skill als Bias)
- Stats-Boost: Schwert-fein = +20% Damage, masterwork = +50%
- UI: Item-Name mit Qualitäts-Präfix (z.B. "✨ Meisterhaftes Eisenschwert")

### 3. Hunger / Energy
RimWorld: Food, Rest, Mood als Need-Bars.
- Wir: **Hunger** + **Stamina** pro Spieler
- Hunger sinkt langsam; bei 0 nimmt HP ab
- Stamina sinkt bei Aktionen, regeneriert beim Stehen
- Essen restored Hunger (food-items aus crafting/loot/farming)
- Schlafen (Bett-Interaktion) restored Stamina

### 4. KI-Storyteller-Modi
RimWorld: Cassandra (escalating), Phoebe (chill), Randy (chaos).
- Wir: Slow Brain bekommt einen Modus-Hint im Prompt
- 3 Modi: "balanced", "chill", "chaos"
- Modus beeinflusst Event-Frequenz, Creature-Spawn-Härte, etc.
- Globale Setting in env oder ein Admin-Befehl

## Anpassbar mit Aufwand (Tier 2)

### 5. Body-Parts-Health (komplexer Combat)
RimWorld: jeder Pawn hat Körperteile mit eigenen HP. Bein verletzt → langsam, Arm verletzt → schlechtere Accuracy.
- Wir: vereinfacht 3 Slots: **Beine** (Move-Speed), **Arme** (Combat-Damage), **Rumpf** (Max-HP-Reduktion)
- Schaden zu Beinen reduziert Bewegungs-Cooldown nicht (kompliziert), aber Damage zu armen verringert eigenen Damage
- Heilung durch Heiltrank repariert alle Wunden

### 6. Crafting-Bills (Queue statt Single-Click)
RimWorld: Werkbank hat Liste von Bills ("mach 5 Schwerter dann stop").
- Wir: aktuell pro Klick ein Recipe. Erweitert: Queue (z.B. 10× Schwert → Server craftet parallel je nach Material).
- Implement: queue-Tabelle, Worker checkt + reduziert Materials sequenziell

### 7. Mood + Mental Breaks
RimWorld: low mood → mental break.
- Wir: nicht direkt für Spieler (kein Soft-Lock-Risiko), aber für **NPCs**:
  - NPC-Mood basierend auf "wie viele Spieler-Tötungen erlebt", "wurde getroffen?", "isst gut?"
  - Mental break: NPCs flüchten, weinen, randomieren ziellos

## Groß (Tier 3 — eigene Wellen)

### 8. Research-Tree / Tech-Progression
Mehrstufige Forschung schaltet bessere Recipes frei.
- Welt-Wide oder Pro-Player? Beides denkbar.
- UI: Tree-View, XP-Stunden in Research zu investieren.

### 9. World-Map / Travel
RimWorld: Hex-Welt mit Settlements und Caravans.
- Bei uns: aktuell ist die Welt selbst die Map. Würde "Welt-Welt-Map" bedeuten — Multi-World wie Dungeon-Layer.
- Erstmal weglassen.

### 10. Raids (Eskalierend)
RimWorld: periodische Raid-Attacks, Schwere steigt mit Colony-Wealth.
- Wir: ähnlich, aber **Spieler-spezifisch**. Wenn ein Spieler viel gebaut hat, kommen Raids zu seiner Base.
- Slow Brain triggert das.

## Was wir NICHT übernehmen (out-of-scope)

- **Pawn-Recruitment** (wir haben einen Charakter pro Spieler, keine Crew)
- **Beziehungen zwischen mehreren eigenen Pawns** (n/a)
- **Power-Grid** (Strom-Verteilung — zu komplex für MVP)
- **Temperature-System** als Game-Mechanik (kalt → Frostbrand etc. — zu fummelig)
- **Animals tame / Schlachten** (späteres Update vielleicht)
- **Drugs** (suchterzeugende Tränke — nicht im Stil)

## Reihenfolge-Vorschlag

1. **Skill-System + XP** (mittel-groß, gibt Spielern Progression)
2. **Item-Quality** (mittel, nutzt Skill als Bias)
3. **Hunger + Stamina** (mittel, gibt Survival-Element)
4. **KI-Storyteller-Modi** (klein, env-config)
5. **Body-Parts** (mittel)
6. **Crafting-Bills** (mittel)
7. **NPC-Mood / Mental-Breaks** (mittel)
8. **Research-Tree** (groß)
9. **Raid-Mechanik** (groß)
