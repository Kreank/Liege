// Bill-Modell (Workshop-Auftrag — Welle 36ff.).
//
// Backend sendet Bills im `bills_update`-Frame mit der vollen Liste
// (Server-Filter: alle Bills für den anfragenden Spieler, alle Stationen).
// UI-Pannels filtern client-seitig nach `station_type`.
//
// Spiegel des Legacy-`this.bills[]`-Arrays (frontend/legacy/app.js Z. 6029-
// 6056, 6336-6543).

export type BillStatus = 'active' | 'blocked' | 'pending';

export interface Bill {
  readonly id: number;
  readonly station_type: string;
  readonly recipe_id: string;
  readonly target_count: number;
  readonly completed: number;
  readonly status?: BillStatus | string;
}
