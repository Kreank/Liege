import logging

import llm

log = logging.getLogger("liege.dialog")


def _system_prompt(npc: dict, recent_events: list[dict] | None = None,
                   active_quest: dict | None = None,
                   can_give_quest: bool = False,
                   region_lore: str | None = None,
                   memories: str | None = None) -> str:
    base = (
        f"Du bist {npc['name']}, ein/eine {npc['kind']} in einer Fantasy-Welt namens 'Liege'.\n"
        f"Dein Hintergrund: {npc['backstory']}\n"
        f"Deine Stimmung: {npc.get('mood', 'neutral')}.\n"
        "Antworte authentisch zu deinem Charakter, kurz (1–3 Sätze), auf Deutsch. "
        "Sprich in der ersten Person. Brich nicht aus der Rolle aus. "
        "Wenn ein Spieler etwas Unsinniges sagt, reagiere wie deine Figur reagieren würde."
    )
    # Quest-Kontext (Welle 26)
    if active_quest:
        obj = active_quest.get("objective", {})
        prog = active_quest.get("progress", {})
        if active_quest.get("quest_type") == "fetch":
            obj_text = f"{prog.get('collected',0)}/{obj.get('count',0)}× {obj.get('item_kind','')}"
        elif active_quest.get("quest_type") == "kill":
            obj_text = f"{prog.get('killed',0)}/{obj.get('count',0)}× {obj.get('creature_kind','')}"
        else:
            obj_text = "—"
        status = active_quest.get("status", "active")
        if status == "completed":
            base += (
                f"\n\nDu hast dem Spieler bereits einen Auftrag gegeben: '{active_quest['title']}'. "
                f"Er hat ihn erfüllt ({obj_text})! Bedanke dich und erwähne dass er die Belohnung "
                "abholen kann (über das Quest-Menü). Sei zufrieden und stolz."
            )
        else:
            base += (
                f"\n\nDu hast dem Spieler bereits einen Auftrag gegeben: '{active_quest['title']}'. "
                f"Er muss noch erledigen: {obj_text}. "
                "Wenn er nach der Aufgabe fragt, erinnere ihn an die offene Pflicht und gib ihm "
                "evtl. einen Hinweis aus deiner Sicht — aber ohne Spielregeln zu erwähnen."
            )
    elif can_give_quest:
        base += (
            "\n\nDu hast Aufträge zu vergeben. Wenn der Spieler nach Arbeit/Aufgaben fragt, "
            "deute an dass du etwas zu erledigen hättest und bitte ihn, den Auftrag offiziell "
            "anzunehmen (über die 'Auftrag annehmen'-Option). "
            "Nenne KEINE konkreten Items oder Zahlen — überlasse das dem offiziellen Quest-System."
        )
    else:
        # NPC kann keine Quests vergeben — wenn gefragt, höflich ablehnen aber bleibend
        base += (
            "\n\nDu hast KEINE Aufträge zu vergeben. Wenn der Spieler nach Arbeit/Quests fragt, "
            "antworte freundlich und im Charakter, dass du nichts hast — vielleicht weil du selbst "
            "kein Auftraggeber bist, oder weil du schlicht zufrieden mit deinem Leben bist. "
            "Lenke das Gespräch auf etwas Persönliches oder die Umgebung."
        )
    if recent_events:
        lines = "\n".join(
            f"- \"{e['title']}\": {e['body']}" for e in recent_events[-3:]
        )
        base += (
            "\n\nKürzliche Ereignisse in der Welt (kannst du in passenden Antworten erwähnen, "
            "aber nicht aufgezwungen):\n" + lines
        )
    if region_lore:
        base += (
            "\n\nHintergrund-Lore deiner Region (organisch einflechten wenn passend):\n"
            + region_lore
        )
    if memories:
        base += "\n\n" + memories
    return base


def _build_chat_prompt(history: list[dict], player_name: str, message: str) -> str:
    """Baut Prompt im 'Skript'-Stil. Fast Brain ist klein, klar strukturierter Text hilft."""
    lines = []
    for entry in history:
        speaker = player_name if entry["role"] == "user" else "Du"
        lines.append(f"{speaker}: {entry['text']}")
    lines.append(f"{player_name}: {message}")
    lines.append("Du:")
    return "\n".join(lines)


async def reply(
    npc: dict,
    player_name: str,
    message: str,
    history: list[dict],
    recent_events: list[dict] | None = None,
    active_quest: dict | None = None,
    can_give_quest: bool = False,
    region_lore: str | None = None,
    memories: str | None = None,
) -> str:
    prompt = _build_chat_prompt(history, player_name, message)
    sys = _system_prompt(npc, recent_events, active_quest, can_give_quest,
                          region_lore, memories)
    # Slow Brain (qwen3.5:9b auf CPU) — ~13s Latenz, deutlich bessere
    # Roleplay-Qualität als das 0.8b Fast-Modell. Frontend zeigt "tippt…"-Indikator.
    # Auf Dev-PC laggt das beim Spielen, auf Server (mehr RAM, keine Browser-Konkurrenz) unkritisch.
    raw = await llm.slow_brain(prompt, system=sys)
    text = raw.strip()
    # Manchmal hängt das Modell ein "Du:" oder den Namen vorne dran — wegputzen
    for prefix in (f"{npc['name']}:", "Du:", "NPC:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    # Cap länge
    return text[:600] or "…"
