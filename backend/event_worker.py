"""Event-Worker v2 (Welle 20) — Tiered World-Brain.

Statt einem globalen Event-Loop: separate Timer pro Tier. Jeder Tick (1 Minute)
prüft alle Tiers ob fällig. Pro Tick wird höchstens EIN Event abgefeuert
(Cataclysm > Boss > Catastrophe > Encounter > Atmosphere), damit nicht alles
gleichzeitig knallt — außer im chaos-Modus, da darf ein zweites Tier folgen.
"""
import asyncio
import json
import logging
import os
import random

import combat
import currency
import llm
import npc_worker
import player_profile
import skills as _skills
import storyteller

log = logging.getLogger("liege.event_worker")

# Wie oft der Dispatcher prüft ob Tiers fällig sind
TICK_SECONDS = int(os.environ.get("EVENT_TICK_SECONDS", "60"))

# System-Prompts pro Tier (LLM-Färbung)
TIER_SYSTEM_PROMPTS = {
    "atmosphere": (
        "Du bist der atmosphärische Erzähler einer Fantasy-Welt 'Liege'. "
        "Beschreibe stimmungsvolle, harmlose Welt-Momente: Wetter, Geräusche, "
        "kleine Funde. Halte den Ton ruhig und poetisch."
    ),
    "encounter": (
        "Du bist der Erzähler einer Fantasy-Welt 'Liege'. Beschreibe eine "
        "Begegnung oder Entdeckung — kleine Mob-Gruppe, alte Ruine, wandernder "
        "NPC. Konkret und visuell."
    ),
    "catastrophe": (
        "Du bist der Erzähler einer Fantasy-Welt 'Liege'. Erzähle von einer "
        "bedrohlichen Welt-Entwicklung — Schwarm, Brand, Erdbeben, Seuche. "
        "Dramatisch, mit Konsequenzen-Andeutung."
    ),
    "boss": (
        "Du bist der Erzähler einer Fantasy-Welt 'Liege'. Verkünde das Erwachen "
        "eines Welt-Bosses — episch, mit Furcht und Lockruf. Spieler werden "
        "herausgefordert ihn zu finden und zu besiegen."
    ),
    "cataclysm": (
        "Du bist der Erzähler einer Fantasy-Welt 'Liege'. Verkünde ein welt-"
        "veränderndes Ereignis. Apokalyptisch, mythisch, lange Nachwirkung."
    ),
}

EVENT_RESPONSE_SCHEMA = (
    'Antworte AUSSCHLIESSLICH als gültiges JSON ohne Markdown:\n'
    '{"title": "kurzer Titel max 80 Zeichen, Deutsch",\n'
    ' "body":  "1-2 Sätze Beschreibung, Deutsch, atmosphärisch"}'
)


def _build_prompt(tier: str, tag: str, state_summary: str, audiences: set[str]) -> str:
    audience_hint = ""
    if audiences:
        labels = ", ".join(sorted(audiences))
        audience_hint = (
            f"Aktive Spieler-Profile: {labels}. Das Event soll für sie "
            "interessant sein.\n"
        )
    return (
        f"Tier: {tier}\nThema: {tag}\n{audience_hint}"
        f"Aktueller Welt-Zustand:\n{state_summary}\n\n"
        f"Erfinde EIN Welt-Event zum Thema '{tag}'. {EVENT_RESPONSE_SCHEMA}"
    )


def world_state_summary(npc_manager, structure_manager, connection_manager) -> str:
    players = connection_manager.get_players()
    npcs_all = npc_manager.all()
    creatures = [n for n in npcs_all if n["kind"] in combat.CREATURE_KINDS]
    friendlies = [n for n in npcs_all if n["kind"] not in combat.CREATURE_KINDS]
    structs = structure_manager.all()
    built = sum(1 for s in structs if s.get("owner") not in (None, "system"))
    natural = sum(1 for s in structs if s.get("owner") == "system")
    lines = [
        f"- Aktive Spieler: {len(players)}",
        f"- Wilde Kreaturen: {len(creatures)}",
        f"- Bewohner (NPCs): {len(friendlies)}",
        f"- Spieler-Bauten: {built}",
        f"- Natürliche Strukturen: {natural}",
    ]
    return "\n".join(lines)


async def _generate_event_text(tier: str, tag: str, state_summary: str,
                                audiences: set[str]) -> dict | None:
    """LLM-Call für Titel+Body. Returns {title, body} oder None bei Fehler."""
    try:
        raw = await llm.slow_brain(
            _build_prompt(tier, tag, state_summary, audiences),
            system=TIER_SYSTEM_PROMPTS.get(tier, TIER_SYSTEM_PROMPTS["atmosphere"]),
            json_mode=True,
        )
        data = json.loads(raw)
        return {
            "title": str(data["title"])[:120],
            "body":  str(data["body"])[:1000],
        }
    except (json.JSONDecodeError, KeyError, Exception) as e:
        log.warning("LLM-Event-Text fehlgeschlagen (%s/%s): %s", tier, tag, e)
        # Fallback-Text (kein LLM-Crash)
        return {
            "title": f"[{tier}] {tag}",
            "body":  f"Etwas geschieht in der Welt ({tag}).",
        }


async def _apply_event_effect(tmpl: dict, ev_meta: dict, world, npc_manager,
                              structure_manager, connection_manager) -> dict | None:
    """Mechanische Effekte je nach Template. Returns optional einen Marker-Dict
    {x, y, label, color, ttl_s} der dem Event-Broadcast hinzugefügt wird, damit
    Frontend einen Map-Marker zeigen kann. Best-effort — Fehler werden geloggt."""
    effect = tmpl.get("effect")
    if not effect:
        return None
    marker = None
    try:
        # ── Boss-Spawn — Format "boss_spawn:<kind>" ─────────────────────────
        if effect.startswith("boss_spawn:"):
            kind = effect.split(":", 1)[1]
            # Boss spawnt etwas weiter weg damit der Player ihn JAGEN muss
            biomes = (npc_worker.CREATURE_SPAWN_PROFILE.get(kind) or {}).get("biomes")
            center = await npc_worker.find_event_cluster_center(
                world, connection_manager, biomes=biomes, min_dist=28, max_dist=50,
            )
            if center is None:
                spawned = await npc_worker.spawn_one(world, npc_manager,
                                                      connection_manager, kind=kind)
                if spawned:
                    center = (spawned["x"], spawned["y"])
            else:
                await npc_worker.spawn_one(world, npc_manager, connection_manager,
                                            kind=kind, at=center)
            if center:
                marker = _marker(center, label=f"💀 {tmpl.get('tag','Boss')}",
                                 color="#ff4060", ttl_s=1800)

        # ── Invasion — Format "spawn_invasion:<kind>:<count>" ──────────────
        elif effect.startswith("spawn_invasion:"):
            parts = effect.split(":")
            kind = parts[1]
            n = int(parts[2]) if len(parts) > 2 else 30
            center = await npc_worker.spawn_cluster(world, npc_manager,
                                                     connection_manager,
                                                     kind=kind, count=n, jitter=5)
            if center:
                marker = _marker(center, label=f"🌑 Invasion ({n}×{kind})",
                                 color="#d060ff", ttl_s=3600)

        # ── Cluster-Mob-Spawns ─────────────────────────────────────────────
        elif effect == "spawn_bandits":
            n = random.randint(3, 5)
            center = await npc_worker.spawn_cluster(world, npc_manager, connection_manager,
                                                     kind="bandit", count=n, jitter=3)
            if center:
                marker = _marker(center, label=f"🗡 Banditen ({n})",
                                 color="#e85040", ttl_s=900)

        elif effect == "spawn_spiders":
            n = random.randint(2, 4)
            center = await npc_worker.spawn_cluster(world, npc_manager, connection_manager,
                                                     kind="spider", count=n, jitter=2)
            if center:
                marker = _marker(center, label=f"🕷 Spinnennest ({n})",
                                 color="#a060c0", ttl_s=900)

        elif effect == "spawn_undead":
            n = random.randint(2, 4)
            kind = random.choice(["skeleton", "zombie"])
            center = await npc_worker.spawn_cluster(world, npc_manager, connection_manager,
                                                     kind=kind, count=n, jitter=3)
            if center:
                marker = _marker(center, label=f"☠️ Untote ({n})",
                                 color="#c060c0", ttl_s=900)

        elif effect == "spawn_elites":
            elite_pool = ["mantis_chimera", "iron_spider", "mossback_warden",
                          "serpent_oracle", "urtikus_eye_fiend"]
            kind = random.choice(elite_pool)
            n = random.randint(2, 3)
            center = await npc_worker.spawn_cluster(world, npc_manager, connection_manager,
                                                     kind=kind, count=n, jitter=4)
            if center:
                marker = _marker(center, label=f"🔥 Elite-Rudel ({n})",
                                 color="#ff8040", ttl_s=1200)

        elif effect == "spawn_raid":
            kind = random.choice(["bandit", "goblin"])
            n = random.randint(6, 10)
            center = await npc_worker.spawn_cluster(world, npc_manager, connection_manager,
                                                     kind=kind, count=n, jitter=4)
            if center:
                marker = _marker(center, label=f"⚔️ Raid ({n}×{kind})",
                                 color="#ff6020", ttl_s=1500)

        elif effect == "spawn_merchant":
            # Merchant ist friendly — spawnt direkt nahe Spieler (8-15 Tiles)
            spawned = await npc_worker.spawn_one(world, npc_manager,
                                                  connection_manager, kind="merchant")
            if spawned:
                marker = _marker((spawned["x"], spawned["y"]),
                                 label="🪙 Wandernder Händler",
                                 color="#80c060", ttl_s=1800)

        elif effect == "spawn_caravan":
            # Welle 23-C: Wandernde Händler-Karawane — Merchant + 1-2 Guards
            # + 1 Wagen, alle als Cluster (jitter 2). Sie bewegen sich danach
            # selbständig durch den Wander-Loop, bleiben aber visuell nahe
            # beieinander weil ihr Spawn-Punkt geclustered ist.
            cart_kind = random.choice([
                "farm_cart_hay", "handcart_empty",
                "horse_cart_single", "market_wagon_covered",
            ])
            # Erst Merchant (center) spawnen
            merchant = await npc_worker.spawn_one(world, npc_manager,
                                                   connection_manager, kind="merchant")
            if merchant:
                cx, cy = merchant["x"], merchant["y"]
                # Cart direkt daneben
                cart_pos = await npc_worker._find_nearby_walkable(world, cx, cy, radius=2)
                if cart_pos:
                    await npc_worker.spawn_one(world, npc_manager, connection_manager,
                                                kind=cart_kind, at=cart_pos)
                # 1-2 Guards rundherum
                guard_count = random.randint(1, 2)
                for _ in range(guard_count):
                    gpos = await npc_worker._find_nearby_walkable(world, cx, cy, radius=3)
                    if gpos:
                        await npc_worker.spawn_one(world, npc_manager, connection_manager,
                                                    kind="guard", at=gpos)
                marker = _marker((cx, cy),
                                 label=f"🛒 Händler-Karawane",
                                 color="#c8a050", ttl_s=2400)

        # ── Strukturen / Items am Boden ─────────────────────────────────────
        elif effect == "ruin_spawn":
            struct_type = random.choice(["ruin_pillar", "rubble", "statue_broken", "gravestone"])
            placed = await _spawn_structure_near_player(world, structure_manager,
                                                        connection_manager, struct_type)
            if placed:
                marker = _marker((placed["x"], placed["y"]),
                                 label=f"🏛 {struct_type}",
                                 color="#a0a0a0", ttl_s=1200)

        elif effect == "spawn_ore":
            kind = random.choice(["iron_ore", "silver_ore", "gold_ore", "crystal"])
            pos = await _spawn_ground_item_near_player(world, connection_manager, kind)
            if pos:
                marker = _marker(pos, label=f"⛏ {kind}", color="#d0c060", ttl_s=900)

        elif effect == "spawn_herb":
            pos = await _spawn_ground_item_near_player(world, connection_manager, "herb")
            if pos:
                marker = _marker(pos, label="🌿 Heilkraut", color="#60d060", ttl_s=900)

        elif effect == "drop_coin":
            # Welle 33: Münzfund fließt direkt in den Geldbeutel eines zufälligen
            # Online-Spielers (Währung ist kein Boden-Item mehr).
            _pids = list(connection_manager.get_players().keys())
            if _pids:
                _pid = random.choice(_pids)
                _amount = random.randint(40, 200)  # Kupfer
                await currency.add(_pid, _amount)
                _p = connection_manager.get_players().get(_pid)
                _ws = connection_manager.connections.get(_pid)
                if _ws is not None:
                    try:
                        await _ws.send_json({"type": "wallet_update",
                                             "copper": await currency.balance(_pid)})
                        await _ws.send_json({"type": "toast",
                                             "text": f"🪙 Münzfund: +{currency.format(_amount)}"})
                    except Exception:
                        pass
                if _p:
                    marker = _marker((_p["x"], _p["y"]), label="🪙 Münzfund",
                                     color="#e8c860", ttl_s=600)

        elif effect == "drop_items":
            first_pos = None
            for k in random.sample(["cloth", "bone", "leather", "wood", "stone"], k=2):
                pos = await _spawn_ground_item_near_player(world, connection_manager, k)
                if pos and first_pos is None:
                    first_pos = pos
            if first_pos:
                marker = _marker(first_pos, label="📦 Verlorene Karawane",
                                 color="#c08060", ttl_s=900)

        # ── Welt-Effekte (Welle 24: echte Mechanik statt nur Toast) ─────────
        elif effect == "blood_moon":
            # Welle 24: Echte Mechanik — Mob-Damage × 1.3, Mob-Aggression hoch.
            import disaster_state
            await disaster_state.activate("blood_moon")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "blood_moon",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["blood_moon"],
                "label": "🌑 BLUTMOND",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "🌑 BLUTMOND erhebt sich — Monster wittern Blut!",
            })

        elif effect == "dying_sun":
            # Welle 24: Hunger/Thirst-Drain × 2 für 30 min.
            import disaster_state
            await disaster_state.activate("dying_sun")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "dying_sun",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["dying_sun"],
                "label": "🌒 Sterbende Sonne",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "🌒 Die Sonne stirbt — Hunger und Durst sind brutal.",
            })

        elif effect == "damage_structures":
            # Welle 24: Erdbeben — 8-15 zufällige Strukturen verlieren Durability,
            # Screen-Shake-Event ans Frontend.
            await _trigger_earthquake(structure_manager, connection_manager)

        elif effect == "taint_water":
            # Welle 24: Vergifteter Brunnen — 1 random well wird tainted für 30min.
            await _trigger_tainted_well(structure_manager, connection_manager)

        elif effect == "plague_npcs":
            # Welle 24: Pest — 2-5 NPCs werden krank.
            await _trigger_plague(npc_manager, connection_manager)

        elif effect == "destroy_farms":
            # Welle 24: Heuschrecken setzen plantings.last_watered_at = NULL.
            await _trigger_locust_swarm(connection_manager)
            # Welle 29e: Plus echten wandernden Schwarm-Mob spawnen
            await _spawn_locust_swarm_mob(world, npc_manager, connection_manager)

        elif effect == "burn_area":
            # Welle 29e: Waldbrand — 2-3 fire_tile Strukturen + Spread-Logik
            await _trigger_wildfire(world, structure_manager, connection_manager)

        # ── Welle 2026-05-29: 5 neue Disaster-Packs ─────────────────────────
        elif effect == "thunderstorm":
            import disaster_state
            await disaster_state.activate("thunderstorm")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "thunderstorm",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["thunderstorm"],
                "label": "⛈️ Gewitter",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "⛈️ Ein Unwetter zieht auf — Vorsicht vor Blitzen!"})

        elif effect == "toxic_fog":
            import disaster_state
            await disaster_state.activate("toxic_fog")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "toxic_fog",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["toxic_fog"],
                "label": "☣️ Giftnebel",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "☣️ Giftiger Nebel breitet sich aus — er zersetzt die Lunge."})

        elif effect == "ash_rain":
            import disaster_state
            await disaster_state.activate("ash_rain")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "ash_rain",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["ash_rain"],
                "label": "🌋 Aschenregen",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "🌋 Asche regnet vom Himmel — Atmen und Laufen fallen schwer."})

        elif effect == "scorching_heat":
            import disaster_state
            await disaster_state.activate("scorching_heat")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "scorching_heat",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["scorching_heat"],
                "label": "☀️ Sengende Hitze",
            })
            await connection_manager.broadcast({
                "type": "toast", "text": "☀️ Sengende Hitze — der Durst frisst dich, jede Bewegung zehrt."})

        elif effect == "frog_plague":
            import disaster_state
            await disaster_state.activate("frog_plague")
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "frog_plague",
                "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["frog_plague"],
                "label": "🐸 Froschplage",
            })
            try:
                await npc_worker.spawn_cluster(
                    world, npc_manager, connection_manager,
                    kind="frog_swarm", count=random.randint(6, 10))
            except Exception:
                log.exception("Frog-Plague-Spawn fehlgeschlagen")
            await connection_manager.broadcast({
                "type": "toast", "text": "🐸 Eine Froschplage bricht herein — sie kriechen überall!"})

    except Exception:
        log.exception("Event-Effekt fehlgeschlagen: %s", effect)
    return marker


def _marker(pos: tuple[int, int], label: str, color: str, ttl_s: int) -> dict:
    """Standardisiert ein Map-Marker-Dict für Event-Broadcasts."""
    return {
        "x": int(pos[0]), "y": int(pos[1]),
        "label": label, "color": color, "ttl_s": ttl_s,
    }


async def _spawn_structure_near_player(world, structure_manager, connection_manager,
                                        struct_type: str) -> dict | None:
    """Spawnt eine Struktur auf einem walkable Tile in 8-15 Tiles Entfernung
    von einem zufälligen aktiven Spieler. Returns placed-dict oder None."""
    players = list(connection_manager.get_players().values())
    if not players:
        return None
    p = random.choice(players)
    for _ in range(20):
        dx = random.randint(-15, 15)
        dy = random.randint(-15, 15)
        if abs(dx) < 8 and abs(dy) < 8:
            continue
        x, y = p["x"] + dx, p["y"] + dy
        if not await world.is_walkable(x, y):
            continue
        if structure_manager.object_at(x, y) is not None:
            continue
        placed = await structure_manager.place(x, y, struct_type, owner="system")
        if placed is not None:
            await connection_manager.broadcast({
                "type": "structure_placed", "structure": placed,
            })
            log.info("Event-Struktur %s @ (%d,%d)", struct_type, x, y)
            return placed
    return None


async def _spawn_ground_item_near_player(world, connection_manager, item_kind: str) -> tuple[int, int] | None:
    players = list(connection_manager.get_players().values())
    if not players:
        return None
    p = random.choice(players)
    try:
        for _ in range(15):
            dx = random.randint(-10, 10)
            dy = random.randint(-10, 10)
            x, y = p["x"] + dx, p["y"] + dy
            if not await world.is_walkable(x, y):
                continue
            from main import items as _glob_items
            spawned = await _glob_items.spawn_on_ground(item_kind, x, y)
            if spawned:
                await connection_manager.broadcast({
                    "type": "item_spawned", "item": spawned,
                })
                return (x, y)
    except Exception:
        log.debug("ground-item-spawn fehlgeschlagen", exc_info=True)
    return None


async def run(event_manager, connection_manager, world=None,
              npc_manager=None, structure_manager=None) -> None:
    """Multi-Tier-Dispatcher (Welle 20).

    Pro Tick (default 60s): prüft alle Tiers in Prioritätsreihenfolge
    (cataclysm > boss > catastrophe > encounter > atmosphere). Höchstens 1
    Event pro Tick — außer chaos-Modus, da kann ein zweites Tier folgen.
    """
    log.info("Event-Worker v2 startet, Tick=%ds, Tiers=%s",
             TICK_SECONDS, ", ".join(storyteller.TIERS))
    # Initialer Sleep — Welt soll erst hochfahren
    await asyncio.sleep(15)

    # Priority — Cataclysm zuerst (dominantes Event), atmosphere zuletzt
    priority_order = ("cataclysm", "boss", "catastrophe", "encounter", "atmosphere")

    while True:
        try:
            ws_state = {}
            state_text = ""
            audiences: set[str] = set()
            if npc_manager and structure_manager:
                state_text = world_state_summary(npc_manager, structure_manager, connection_manager)
                npcs_all = npc_manager.all()
                creatures = [n for n in npcs_all if n["kind"] in combat.CREATURE_KINDS]
                structs = structure_manager.all()
                audiences = await player_profile.active_audiences(connection_manager, _skills)
                ws_state = {
                    "active_players":   len(connection_manager.get_players()),
                    "active_audiences": audiences,
                    "wealth_score":     sum(1 for s in structs if s.get("owner") not in (None, "system")),
                    "creature_count":   len(creatures),
                    "structure_count":  len(structs),
                }

            fired_this_tick = 0
            for tier in priority_order:
                if not storyteller.tier_due(tier):
                    continue
                tmpl = storyteller.select_event(tier, ws_state)
                if tmpl is None:
                    continue
                ev = await _generate_event_text(tier, tmpl["tag"], state_text, audiences)
                if ev is None:
                    continue
                # Effekt zuerst — Marker hängen wir dann ans Event
                marker = None
                if world is not None and npc_manager is not None and structure_manager is not None:
                    marker = await _apply_event_effect(
                        tmpl, ev, world, npc_manager, structure_manager, connection_manager
                    )
                saved = await event_manager.save(
                    tier, ev["title"], ev["body"]
                )
                event_payload = {**saved, "tier": tier, "tag": tmpl["tag"]}
                if marker is not None:
                    event_payload["marker"] = marker
                await connection_manager.broadcast({
                    "type":  "event",
                    "event": event_payload,
                })
                storyteller.mark_event_fired(tier, danger=tmpl.get("danger", 0))
                log.info("[%s] %s — %s%s",
                         tier, ev["title"], tmpl["tag"],
                         f" @ ({marker['x']},{marker['y']})" if marker else "")
                fired_this_tick += 1
                # Im chaos-Modus erlauben wir bis zu 2 Events pro Tick
                if storyteller.get_mode() != "chaos" or fired_this_tick >= 2:
                    break

        except asyncio.CancelledError:
            log.info("Event-Worker gestoppt")
            raise
        except Exception:
            log.exception("Event-Worker iteration fehlgeschlagen")
        await asyncio.sleep(TICK_SECONDS)


# ═══════════════════════════════════════════════════════════════════════════
# Welle 24 — Disaster-Trigger-Helpers (echte Mechanik statt nur Toast)
# ═══════════════════════════════════════════════════════════════════════════

async def _trigger_earthquake(structure_manager, connection_manager) -> None:
    """Erdbeben: 8-15 zufällige Strukturen verlieren -2 Durability + Frontend
    screen-shake-Event. Wenn durability ≤ 0 → kollabiert zu rubble."""
    players = list(connection_manager.get_players().values())
    if not players:
        return
    p = random.choice(players)
    # Sammele Strukturen im Radius 30 Tiles
    all_structs = []
    for s in structure_manager.all():
        if abs(s["x"] - p["x"]) <= 30 and abs(s["y"] - p["y"]) <= 30:
            all_structs.append(s)
    if not all_structs:
        return
    # 8-15 random pick
    n = min(len(all_structs), random.randint(8, 15))
    victims = random.sample(all_structs, n)
    collapsed = 0
    for s in victims:
        try:
            result = await structure_manager.damage_structure(s["x"], s["y"], amount=2)
            if result is None:
                # Strukur eingestürzt → rubble platzieren wo es war
                await connection_manager.broadcast({
                    "type": "structure_removed", "x": s["x"], "y": s["y"],
                })
                rubble = await structure_manager.place(
                    s["x"], s["y"], "rubble", "system",
                    material="stone", durability=2,
                )
                if rubble:
                    await connection_manager.broadcast({
                        "type": "structure_placed", "structure": rubble,
                    })
                    collapsed += 1
        except Exception:
            log.exception("Earthquake-Schaden fehlgeschlagen für %s", s)
    # Screen-Shake + Toast
    await connection_manager.broadcast({
        "type": "earthquake_shake",
        "x": p["x"], "y": p["y"], "duration_ms": 6000, "magnitude": 6,
    })
    await connection_manager.broadcast({
        "type": "toast",
        "text": f"🏚 ERDBEBEN! {len(victims)} Strukturen beschädigt, {collapsed} eingestürzt.",
    })
    log.info("Earthquake near (%d,%d): %d struct dmg, %d collapsed",
             p["x"], p["y"], len(victims), collapsed)


async def _trigger_tainted_well(structure_manager, connection_manager) -> None:
    """Sucht 1 random Brunnen + markiert ihn als tainted via disaster_state-Metadata."""
    import disaster_state
    wells = [s for s in structure_manager.all() if s.get("type") == "well"]
    if not wells:
        return
    well = random.choice(wells)
    await disaster_state.activate("tainted_well",
                                    metadata={"x": well["x"], "y": well["y"]})
    await connection_manager.broadcast({
        "type": "disaster_started", "kind": "tainted_well",
        "duration_s": disaster_state.DISASTER_DEFAULT_DURATION["tainted_well"],
        "x": well["x"], "y": well["y"],
        "label": "☠️ Vergifteter Brunnen",
    })
    await connection_manager.broadcast({
        "type": "toast",
        "text": f"☠️ Der Brunnen bei ({well['x']},{well['y']}) ist vergiftet — nicht trinken!",
    })
    log.info("Tainted well at (%d,%d)", well["x"], well["y"])


async def _trigger_plague(npc_manager, connection_manager) -> None:
    """2-5 random Villager-NPCs werden krank — mental_state=sick + HP-drain.
    Status-Effekt "sick" via status_effects (wird vom Worker getickt)."""
    friendly = [n for n in npc_manager.all() if n["kind"] in (
        "villager", "farmer", "child", "peasant", "baker", "tailor", "innkeeper",
    )]
    if not friendly:
        return
    n = min(len(friendly), random.randint(2, 5))
    victims = random.sample(friendly, n)
    try:
        import status_effects, db
        for v in victims:
            await db.pool().execute(
                "UPDATE npcs SET mental_state = 'sick' WHERE id = $1", v["id"])
            # NPC-spezifischer "sick"-Effekt — wir nutzen einen einfachen Marker
            # in npcs.mental_state, der vom npc_mood-Worker visualisiert wird.
    except Exception:
        log.exception("Plague-Effect fehlgeschlagen")
    await connection_manager.broadcast({
        "type": "toast",
        "text": f"🤒 PEST! {n} Dorfbewohner sind erkrankt.",
    })
    log.info("Plague: %d NPCs sick", n)


async def _trigger_locust_swarm(connection_manager) -> None:
    """Heuschrecken setzen 30% aller plantings im Player-Radius auf
    last_watered_at = NULL → Felder stagnieren."""
    import db
    players = list(connection_manager.get_players().values())
    if not players:
        return
    p = random.choice(players)
    # Plantings im 30-Tile-Radius — random 30% trifft
    rows = await db.pool().fetch(
        "SELECT structure_id, x, y FROM plantings "
        "WHERE x BETWEEN $1 AND $2 AND y BETWEEN $3 AND $4 "
        "AND last_watered_at IS NOT NULL",
        p["x"] - 30, p["x"] + 30, p["y"] - 30, p["y"] + 30,
    )
    if not rows:
        await connection_manager.broadcast({
            "type": "toast", "text": "🦗 Heuschreckenschwarm zieht durch — keine Felder in der Nähe.",
        })
        return
    victims = [r for r in rows if random.random() < 0.30]
    for r in victims:
        try:
            await db.pool().execute(
                "UPDATE plantings SET last_watered_at = NULL WHERE structure_id = $1",
                r["structure_id"])
        except Exception:
            pass
    await connection_manager.broadcast({
        "type": "toast",
        "text": f"🦗 HEUSCHRECKEN! {len(victims)} Felder ausgetrocknet — neu wässern!",
    })
    log.info("Locust swarm dried %d plantings near (%d,%d)",
             len(victims), p["x"], p["y"])


# ─── Welle 29e: Locust + Wildfire Game-Effekte ──────────────────────────────

async def _spawn_locust_swarm_mob(world, npc_manager, connection_manager) -> None:
    """Spawnt einen wandernden Heuschreckenschwarm-NPC nahe eines Spielers.
    Lebt 5 min (DISASTER_DEFAULT_DURATION für 'locust'), wandert konstant,
    macht 1 dmg/Tick auf Spieler in 3-Tile-Radius — Logik im npc_worker."""
    import disaster_state, npc_worker
    players = list(connection_manager.get_players().values())
    if not players:
        return
    p = random.choice(players)
    # Spawn-Position: 8-15 Tiles vom Spieler (sichtbar aber nicht direkt drauf)
    for _ in range(20):
        dx = random.randint(-15, 15)
        dy = random.randint(-15, 15)
        if abs(dx) < 8 and abs(dy) < 8:
            continue
        sx, sy = p["x"] + dx, p["y"] + dy
        if not await world.is_walkable(sx, sy):
            continue
        try:
            npc = await npc_manager.create(
                name="Heuschreckenschwarm",
                kind="locust_swarm", x=sx, y=sy,
                backstory="Eine wandernde Plage aus Tausenden Insekten.",
                max_hp=500,
            )
            await connection_manager.broadcast({"type": "npc_spawned", "npc": npc})
            # Disaster-Flag aktivieren damit HUD-Icon erscheint
            await disaster_state.activate("locust", duration_s=300,
                                            metadata={"npc_id": npc["id"]})
            await connection_manager.broadcast({
                "type": "disaster_started", "kind": "locust",
                "duration_s": 300, "label": "🦗 Heuschreckenschwarm",
                "x": sx, "y": sy,
            })
            log.info("Locust-swarm-mob spawned @(%d,%d)", sx, sy)
            return
        except Exception:
            log.exception("Locust-swarm-spawn fehlgeschlagen")
            return


async def _trigger_wildfire(world, structure_manager, connection_manager) -> None:
    """Waldbrand-Start: spawnt 2-3 fire_tile-Strukturen auf Tree-Tiles in
    Player-Nähe. Der wildfire_worker (in npc_worker oder eigenem Loop) handelt
    den Spread alle 30s."""
    import disaster_state
    players = list(connection_manager.get_players().values())
    if not players:
        return
    p = random.choice(players)
    # Sammle Tree-Strukturen im 25-Tile-Radius
    candidates = []
    for s in structure_manager.all():
        if s["type"] not in ("tree_oak", "tree_pine", "tree_dead",
                              "apple_tree", "pear_tree", "plum_tree", "cherry_tree"):
            continue
        if abs(s["x"] - p["x"]) > 25 or abs(s["y"] - p["y"]) > 25:
            continue
        candidates.append(s)
    if not candidates:
        await connection_manager.broadcast({
            "type": "toast", "text": "🔥 Waldbrand zieht durch — keine Bäume in der Nähe.",
        })
        return
    # 2-3 zufällige Trees in Brand setzen
    victims = random.sample(candidates, min(len(candidates), random.randint(2, 3)))
    for s in victims:
        try:
            # Original Tree entfernen
            await structure_manager.remove(s["x"], s["y"], layer="object")
            await connection_manager.broadcast({
                "type": "structure_removed", "x": s["x"], "y": s["y"], "layer": "object",
            })
            # fire_tile platzieren
            fire = await structure_manager.place(
                s["x"], s["y"], "fire_tile", "system",
                material="wood", durability=90,   # durability=lebenszeit in ticks
            )
            if fire:
                await connection_manager.broadcast({
                    "type": "structure_placed", "structure": fire,
                })
        except Exception:
            log.exception("Wildfire-Spawn fehlgeschlagen für %s", s)
    # Disaster-Flag
    await disaster_state.activate("wildfire", duration_s=600,
                                    metadata={"origin_x": p["x"], "origin_y": p["y"]})
    await connection_manager.broadcast({
        "type": "disaster_started", "kind": "wildfire",
        "duration_s": 600, "label": "🔥 Waldbrand", "x": p["x"], "y": p["y"],
    })
    await connection_manager.broadcast({
        "type": "toast",
        "text": f"🔥 WALDBRAND! {len(victims)} Bäume in Flammen. Greift sich aus!",
    })
    log.info("Wildfire ignited %d trees near (%d,%d)",
             len(victims), p["x"], p["y"])


async def wildfire_tick_loop(structure_manager, connection_manager) -> None:
    """Background-Loop: alle 30s prüft alle fire_tiles, breitet aus, verwandelt
    abgelaufene zu burned_stump. Damit der Waldbrand lebendig wirkt."""
    import asyncio
    log.info("Wildfire-Tick-Loop startet (tick=30s)")
    while True:
        try:
            await asyncio.sleep(30)
            fire_tiles = [s for s in structure_manager.all() if s.get("type") == "fire_tile"]
            if not fire_tiles:
                continue
            # Spread: jeder fire_tile 40% Chance, einen adjacent Tree anzuzünden
            new_fires = []
            burned_out = []
            for fire in fire_tiles:
                # Durability als Lebenszeit-Counter — wir reduzieren bei jedem Tick
                # Anfangswert 90 → ~45 min Lebenszeit pro Feuer
                new_dur = fire["durability"] - 1
                if new_dur <= 0:
                    burned_out.append(fire)
                    continue
                # Spread
                if random.random() < 0.40:
                    for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                        nx, ny = fire["x"] + dx, fire["y"] + dy
                        neighbor = structure_manager.object_at(nx, ny)
                        if neighbor and neighbor["type"] in (
                            "tree_oak", "tree_pine", "tree_dead",
                            "apple_tree", "pear_tree", "plum_tree", "cherry_tree",
                        ):
                            try:
                                await structure_manager.remove(nx, ny, layer="object")
                                await connection_manager.broadcast({
                                    "type": "structure_removed", "x": nx, "y": ny, "layer": "object",
                                })
                                new_fire = await structure_manager.place(
                                    nx, ny, "fire_tile", "system",
                                    material="wood", durability=90,
                                )
                                if new_fire:
                                    new_fires.append(new_fire)
                                    await connection_manager.broadcast({
                                        "type": "structure_placed", "structure": new_fire,
                                    })
                            except Exception:
                                pass
                            break   # nur 1 spread pro tick pro fire
                # Update durability
                try:
                    await structure_manager.damage_structure(fire["x"], fire["y"], amount=1)
                except Exception:
                    pass
            # Abgebrannte Bäume zu burned_stump
            for fire in burned_out:
                try:
                    await structure_manager.remove(fire["x"], fire["y"], layer="object")
                    await connection_manager.broadcast({
                        "type": "structure_removed", "x": fire["x"], "y": fire["y"], "layer": "object",
                    })
                    stump = await structure_manager.place(
                        fire["x"], fire["y"], "burned_stump", "system",
                        material="wood", durability=5,
                    )
                    if stump:
                        await connection_manager.broadcast({
                            "type": "structure_placed", "structure": stump,
                        })
                except Exception:
                    pass
            if new_fires or burned_out:
                log.info("Wildfire tick: +%d spread, %d burned out, %d active",
                         len(new_fires), len(burned_out), len(fire_tiles) - len(burned_out) + len(new_fires))
        except asyncio.CancelledError:
            log.info("Wildfire-Tick-Loop gestoppt")
            raise
        except Exception:
            log.exception("Wildfire-Tick-Iteration fehlgeschlagen")
