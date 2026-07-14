import snapshotJson from '../data/eia_snapshot.json';

export type Ba = 'CAISO' | 'ERCOT' | 'PJM' | 'MISO';

export interface BaSnapshot {
  eia_code: string;
  name: string;
  snapshot_hour_utc: string;
  carbon_intensity_g_per_kwh: number;
  fuel_mix_mwh: Record<string, number>;
  net_imports_or_storage_mwh: Record<string, number>;
}

export interface EiaSnapshot {
  fetched_at: string;
  source: string;
  route: string;
  carbon_factors_source: string;
  carbon_factors_g_per_kwh: Record<string, number>;
  peaker_g_per_kwh: number;
  ccgt_g_per_kwh: number;
  bas: Record<string, BaSnapshot | { error: string }>;
}

export const eiaSnapshot = snapshotJson as unknown as EiaSnapshot;

function isBaSnapshot(x: unknown): x is BaSnapshot {
  return !!x && typeof x === 'object' && 'carbon_intensity_g_per_kwh' in x;
}

/**
 * Real BA grid carbon intensity (g CO₂/kWh) from latest EIA-930 snapshot.
 * Falls back to the published BA fleet average if the snapshot is missing.
 */
export function getCarbonIntensity(ba: Ba): number {
  const fallbacks: Record<Ba, number> = {
    CAISO: 230,
    ERCOT: 380,
    PJM: 450,
    MISO: 500,
  };
  const entry = eiaSnapshot.bas[ba];
  return isBaSnapshot(entry) ? entry.carbon_intensity_g_per_kwh : fallbacks[ba];
}

export function getSnapshotHourUtc(ba: Ba): string | null {
  const entry = eiaSnapshot.bas[ba];
  return isBaSnapshot(entry) ? entry.snapshot_hour_utc : null;
}

/**
 * Tons CO₂ avoided when `mw` of load is shifted away from a peaker
 * (firing at peakerCarbon) and absorbed by the BA grid (at baCarbon)
 * for `durationMin` minutes.
 *
 * Formula: avoided_g = (peakerCarbon − baCarbon) g/kWh × MWh
 *          tons      = avoided_g / 1_000_000_000
 */
export function tonsCo2Avoided(mw: number, durationMin: number, ba: Ba): number {
  const baCarbon = getCarbonIntensity(ba);
  const peakerCarbon = eiaSnapshot.peaker_g_per_kwh;
  const avoidedGPerKwh = Math.max(0, peakerCarbon - baCarbon);
  const mwh = mw * (durationMin / 60);
  return (mwh * 1000 * avoidedGPerKwh) / 1_000_000_000;
}

/**
 * Settlement payout from a dispatch.
 *   $ = MW × hours × $/MWh
 */
export function settlementUsd(
  mw: number,
  durationMin: number,
  pricePerMwh: number,
): number {
  return mw * (durationMin / 60) * pricePerMwh;
}

/**
 * Energy delivered, MWh.
 */
export function energyMwh(mw: number, durationMin: number): number {
  return mw * (durationMin / 60);
}

export const PEAKER_CARBON_G_PER_KWH = eiaSnapshot.peaker_g_per_kwh;
export const CCGT_CARBON_G_PER_KWH = eiaSnapshot.ccgt_g_per_kwh;
