// Research-Modelle (Welle 30 — Forschungs-Pool + Tech-Tree).
//
// Backend liefert das `research`-Objekt entweder im `init`-Snapshot (im
// Player-Init-Frame) oder via `research_update`/`research_pool_update`. Die
// Struktur spiegelt 1:1 das Legacy-`this.myResearch{,Pool,Branches,Ages}`-
// State (frontend/legacy/app.js Z. 5079-5090).

/** Ein Forschungs-Knoten. */
export interface ResearchNode {
  readonly name: string;
  readonly desc?: string;
  readonly icon?: string;
  readonly age: string;
  readonly branch: string;
  readonly points: number;
  readonly points_max: number;
  readonly done: boolean;
  readonly available: boolean;
  /** Prereq-Knoten-IDs (Backend liefert mal Array, mal Single-String — wir
   *  normalisieren auf Array). */
  readonly prereq?: readonly string[];
  /** Optionaler Tech-Print-Gate (Welle 30b). */
  readonly tech_print?: string;
  readonly has_tech_print?: boolean;
}

/** Branch-Definition (Smithing/Alchemy/…). */
export interface ResearchBranch {
  readonly id: string;
  readonly label: string;
  readonly icon: string;
  readonly color: string;
}

/** Age-Definition (Stammeszeit → Legendär). */
export interface ResearchAge {
  readonly id: string;
  readonly label: string;
  readonly icon: string;
  readonly tier: number;
}
