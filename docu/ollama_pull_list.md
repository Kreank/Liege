# Ollama-Modelle für Liege (Setup E — Fast/Slow-Split)

Auf Dev-PC und Server identisch:

```bash
ollama pull qwen3.5:0.8b         # Fast Brain — NPC-Dialoge, Item-Flavor (1.0 GB)
ollama pull qwen3.5:9b           # Slow Brain — Welt-Events, Quests (6.6 GB), läuft auf CPU
ollama pull nomic-embed-text     # Embeddings — Semantic Search (~0.3 GB)
```

## Hardware-Verteilung auf dem Server (RTX 3070 8 GB / 3900X / 32 GB RAM)

**GPU (~1.3 GB belegt, ~6.7 GB frei für SD in Phase 4):**

| Modell | Größe | Rolle |
|--------|-------|-------|
| qwen3.5:0.8b | 1.0 GB | Fast Brain (interaktiv, <1s) |
| nomic-embed-text | ~0.3 GB | Embeddings |

**CPU + RAM (~7 GB belegt, viel Puffer):**

| Modell | Größe | Rolle |
|--------|-------|-------|
| qwen3.5:9b | 6.6 GB | Slow Brain (Hintergrund-DM, 15–40s) |

## Routing-Logik

| Anfrage | Modell | Wo | Latenz |
|---------|--------|-----|--------|
| NPC-Dialog, Kampftext, Item-Flavor | qwen3.5:0.8b | GPU | <1s |
| Welt-Event, Quest, Fraktionsentscheidung | qwen3.5:9b | CPU | 15–40s |
| Semantic Search (Lore, ähnliche Events) | nomic-embed-text | GPU | <100ms |

## API-Beispiel — Slow Brain auf CPU forcen

```python
import httpx

# Fast Brain (GPU, default)
httpx.post("http://localhost:11434/api/generate", json={
    "model": "qwen3.5:0.8b",
    "prompt": "Der Dorfwächter sagt..."
})

# Slow Brain (CPU only — num_gpu=0 erzwingt CPU-Offload)
httpx.post("http://localhost:11434/api/generate", json={
    "model": "qwen3.5:9b",
    "options": {"num_gpu": 0},
    "prompt": "Generiere ein Welt-Event..."
})
```

## Upgrade-Pfad

Wenn 9b-on-CPU problemlos läuft, evaluieren wir ein 14B-Modell als Slow Brain (Sweet-Spot moderner LLMs).
Optionen z.B. `hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL` (9.2 GB) — auf CPU mit 3900X erwartete ~4–6 tok/s.
