"""NPC-Chatter (Welle 20, Session 3) — Sprechblasen zwischen NPCs.

Wenn zwei friendly NPCs adjacent (4-Nachbarn) sind, gibt es eine kleine Chance
dass sie ein kurzes Dialog-Paar austauschen. Backend broadcastet `npc_speech`
Events, Frontend rendert Sprechblasen über den NPCs für ~6 Sekunden.

MVP-Variante: canned Dialog-Pools per Tageszeit + NPC-Kind. Kein LLM-Call,
damit das System günstig läuft. LLM-Integration kann später nachgezogen werden.

Tuning:
    SPEECH_CHANCE_PER_TICK = 0.04 — bei 2-Sekunden-Wander-Tick = pro
                                    Minute 1.2 Speech-Versuche pro NPC.
    SPEECH_COOLDOWN_PER_NPC = 90s — gleicher NPC redet nicht öfter als alle 1.5min.
"""
import logging
import random
import time

import combat
import time_system

log = logging.getLogger("liege.npc_chatter")

SPEECH_CHANCE_PER_TICK = 0.04
SPEECH_COOLDOWN_PER_NPC = 90.0     # Sekunden

# Letzter Speech-Timestamp pro NPC-ID
_last_speech: dict[int, float] = {}

# Canned Dialoge: phase → kind → liste von (initiator_line, responder_line)
DIALOG_POOLS = {
    "morning": {
        "_any": [
            ("Guten Morgen!", "Und dir auch."),
            ("Hast du gut geschlafen?", "Wie ein Stein."),
            ("Schöner Tag heute, oder?", "Solange es nicht regnet."),
            ("Brauchst du noch Brot?", "Vielleicht später."),
        ],
        "blacksmith": [
            ("Heute schmiede ich neue Klingen.", "Brauche eine für meinen Sohn."),
            ("Hast du Eisen für mich?", "Schau im Lager nach."),
        ],
        "farmer": [
            ("Die Felder brauchen Wasser.", "Holst du die Eimer?"),
            ("Karotten sind reif.", "Dann erntet bevor die Hasen kommen."),
        ],
    },
    "day": {
        "_any": [
            ("Hast du die Reisenden gesehen?", "Sie sind nach Osten gezogen."),
            ("Die Kreaturen werden wieder mehr.", "Wir sollten Wachen aufstellen."),
            ("Kennst du die alten Geschichten?", "Nur Gerüchte."),
            ("Wo ist eigentlich der Hund?", "Wahrscheinlich am Brunnen."),
            ("Hier ist es heute lebhaft.", "Liegt am Marktag."),
        ],
        "merchant": [
            ("Heute habe ich Salz dabei.", "Wie viel kostet eine Handvoll?"),
            ("Die Preise steigen.", "Schuld ist die Dürre."),
        ],
        "blacksmith": [
            ("Der Amboss klingt heute hell.", "Gutes Eisen."),
            ("Wer hat den Hammer verlegt?", "Lag bei der Schmiede."),
        ],
        "farmer": [
            ("Sind die Felder bewässert?", "Bis zum Mittag."),
            ("Die Krähen sind zurück.", "Stell die Vogelscheuche neu auf."),
        ],
        "scholar": [
            ("Ein altes Buch liegt in der Ruine.", "Hat jemand es schon angefasst?"),
            ("Die Sterne stehen seltsam.", "Bedeutet das was?"),
        ],
        "guard": [
            ("Ruhe an der Wegkreuzung.", "Solange das so bleibt."),
            ("Hast du was Verdächtiges gesehen?", "Nur den üblichen Pöbel."),
        ],
        "bard": [
            ("Hört ihr das Lied vom verlorenen König?", "Singst du es uns?"),
            ("Mein Hals ist trocken.", "Ich hole Wasser."),
        ],
    },
    "evening": {
        "_any": [
            ("Die Sonne sinkt.", "Bald wird es kühl."),
            ("Hast du heute genug geschafft?", "Mehr als ich wollte."),
            ("Ich brauche etwas zu trinken.", "Komm zur Schenke."),
            ("Erzähl mir was vom Krieg.", "Ein anderes Mal."),
            ("Morgen ist Markttag.", "Ich muss noch packen."),
        ],
        "bard": [
            ("Soll ich heute Abend singen?", "Aber bitte nichts Trauriges."),
            ("Das Feuer brennt schon.", "Ich hole meine Laute."),
        ],
    },
    "night": {
        "_any": [
            ("Ich gehe schlafen.", "Schlaf gut."),
            ("Komisches Geräusch da hinten...", "Bleib drinnen."),
            ("Wer hat die Tür offengelassen?", "Ich war es nicht."),
        ],
        "guard": [
            ("Augen auf. Es ist dunkel.", "Ich höre nichts."),
            ("Hab ich da was gesehen?", "Vermutlich nur ein Tier."),
        ],
        "watchman": [
            ("Alle Lampen brennen.", "Gut. Erste Wache übernehme ich."),
            ("Ungewöhnlich ruhig heute.", "Verdächtig ruhig."),
        ],
    },
}


def _canned_dialog_pair(initiator_kind: str, responder_kind: str) -> tuple[str, str] | None:
    """Pickt zufällig ein passendes Dialog-Pair für die aktuelle Phase und
    bevorzugt kind-spezifische Zeilen wenn vorhanden."""
    phase = time_system.clock.phase()
    pool = DIALOG_POOLS.get(phase, DIALOG_POOLS["day"])
    # 50/50 zwischen kind-spezifisch und generic, wenn beide vorhanden
    options = list(pool.get("_any", []))
    if initiator_kind in pool:
        # Kind-spezifische überrepräsentiert (3× weight) für mehr Variation
        options.extend(pool[initiator_kind] * 3)
    if responder_kind in pool and responder_kind != initiator_kind:
        options.extend(pool[responder_kind])
    if not options:
        return None
    return random.choice(options)


def is_on_cooldown(npc_id: int) -> bool:
    now = time.monotonic()
    last = _last_speech.get(npc_id, 0.0)
    return (now - last) < SPEECH_COOLDOWN_PER_NPC


def mark_spoke(npc_id: int) -> None:
    _last_speech[npc_id] = time.monotonic()


def find_chatter_partner(npc: dict, npc_manager) -> dict | None:
    """Sucht einen friendly NPC der direkt adjacent ist und nicht auf
    Cooldown. None wenn nichts passt."""
    if is_on_cooldown(npc["id"]):
        return None
    if npc["kind"] in combat.CREATURE_KINDS:
        return None
    nx, ny = npc["x"], npc["y"]
    for other in npc_manager.all():
        if other["id"] == npc["id"]:
            continue
        if other["kind"] in combat.CREATURE_KINDS:
            continue
        d = abs(other["x"] - nx) + abs(other["y"] - ny)
        if d == 1 and not is_on_cooldown(other["id"]):
            return other
    return None


async def maybe_chat(npc: dict, npc_manager, connection_manager) -> bool:
    """Pro NPC-Tick: chance auf Sprechblase. Returns True wenn ein Dialog
    abgefeuert wurde."""
    if random.random() >= SPEECH_CHANCE_PER_TICK:
        return False
    partner = find_chatter_partner(npc, npc_manager)
    if partner is None:
        return False
    pair = _canned_dialog_pair(npc["kind"], partner["kind"])
    if pair is None:
        return False
    initiator_text, responder_text = pair
    mark_spoke(npc["id"])
    mark_spoke(partner["id"])
    await connection_manager.broadcast({
        "type":   "npc_speech",
        "npc_id": npc["id"],
        "text":   initiator_text,
    })
    # Antwort kurz verzögert für Lese-Rhythmus (Frontend kümmert sich um Ablauf)
    await connection_manager.broadcast({
        "type":     "npc_speech",
        "npc_id":   partner["id"],
        "text":     responder_text,
        "delay_ms": 1800,
    })
    log.debug("NPC-chat: %s → %s : %r / %r",
              npc["kind"], partner["kind"], initiator_text, responder_text)
    return True
