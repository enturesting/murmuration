#!/usr/bin/env python3
"""Pull real EIA-930 fuel-mix snapshots for CAISO, ERCOT, PJM, MISO.
Compute carbon intensity per BA. Write to JSON for the demo cache.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

KEY = os.environ['EIA_KEY']
BAS = [
    ('CISO', 'CAISO', 'California ISO'),
    ('ERCO', 'ERCOT', 'Electric Reliability Council of Texas'),
    ('PJM',  'PJM',   'PJM Interconnection'),
    ('MISO', 'MISO',  'Midcontinent ISO'),
]

# EPA eGRID 2022 + IPCC AR6 lifecycle factors (g CO2 / kWh net generation)
# Sources: EPA eGRID 2022 Data Explorer; IPCC AR6 WG3 Annex III Table A.III.2
CARBON_G_PER_KWH = {
    'COL': 1001,   # Coal — EPA eGRID 2022 US average
    'NG':  430,    # Natural gas combined cycle (most US gas fleet)
    'OIL': 893,    # Petroleum
    'NUC': 12,     # Nuclear (lifecycle, IPCC AR6 median)
    'WAT': 24,     # Hydro (lifecycle, IPCC AR6 median)
    'SUN': 48,     # Solar PV (lifecycle, IPCC AR6 median utility-scale)
    'WND': 11,     # Wind (lifecycle, IPCC AR6 median onshore)
    'GEO': 38,     # Geothermal (lifecycle, IPCC AR6 median)
    'OTH': 500,    # Other / unknown — assume gas-like
    'BAT': 0,      # Battery (treat as zero direct; embodied accounted at gen)
    'PS':  0,      # Pumped storage
    'SNB': 48,     # Solar with battery
    'WNB': 11,     # Wind with battery
    'OES': 0,      # Other energy storage
    'UNK': 500,    # Unknown — assume gas
    'UES': 500,    # Unknown energy storage
}

# Peaker-specific factor (worst-case gas peaker, used for counterfactual "displaced peakers")
PEAKER_G_PER_KWH = 720   # ~720 g/kWh for older simple-cycle gas turbines
CCGT_G_PER_KWH = 360     # Best-in-class combined cycle gas

def fetch(ba_code: str, start: str, end: str, length: int = 200):
    qs = urllib.parse.urlencode({
        'api_key': KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': ba_code,
        'start': start,
        'end': end,
        'length': str(length),
    }, doseq=False)
    url = f'https://api.eia.gov/v2/electricity/rto/fuel-type-data/data?{qs}'
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def latest_hour(rows):
    """Group by hour, return the most recent fully-populated hour."""
    by_hour = {}
    for r in rows:
        h = r['period']
        by_hour.setdefault(h, []).append(r)
    # most recent hour with at least 4 fuel types
    for h in sorted(by_hour, reverse=True):
        if len(by_hour[h]) >= 4:
            return h, by_hour[h]
    return None, []

def carbon_intensity(rows):
    """Compute g CO2 / kWh from a list of fuel rows (one hour, one BA)."""
    total_mwh = 0.0
    weighted_g = 0.0
    breakdown = {}
    for r in rows:
        ft = r['fueltype']
        v = float(r['value'])
        # Skip negative (imports/exports/storage discharge)
        if v <= 0:
            breakdown[ft] = v
            continue
        factor = CARBON_G_PER_KWH.get(ft, 500)
        total_mwh += v
        weighted_g += v * factor
        breakdown[ft] = v
    if total_mwh == 0:
        return None, breakdown
    # weighted_g is in (MWh × g/kWh) = (1000 kWh × g/kWh) = 1000 g; divide by total_mwh*1000 to get g/kWh
    intensity = weighted_g / total_mwh
    return intensity, breakdown

def main():
    # Use a recent date with full data — yesterday in UTC
    snapshot = {
        'fetched_at': datetime.utcnow().isoformat() + 'Z',
        'source': 'EIA Open Data v2 — EIA-930 fuel-type-data',
        'route': 'https://api.eia.gov/v2/electricity/rto/fuel-type-data/',
        'carbon_factors_source': 'EPA eGRID 2022 (combustion); IPCC AR6 WG3 Annex III (low-carbon lifecycle)',
        'carbon_factors_g_per_kwh': CARBON_G_PER_KWH,
        'peaker_g_per_kwh': PEAKER_G_PER_KWH,
        'ccgt_g_per_kwh': CCGT_G_PER_KWH,
        'bas': {},
    }

    for code, alias, name in BAS:
        print(f'--- {alias} ({code}) ---', file=sys.stderr)
        try:
            data = fetch(code, '2026-04-22', '2026-04-23', length=200)
            rows = data['response']['data']
            hour, hour_rows = latest_hour(rows)
            if not hour:
                print(f'  no data', file=sys.stderr)
                continue
            ci, breakdown = carbon_intensity(hour_rows)
            print(f'  hour={hour} carbon_intensity={ci:.0f} g/kWh', file=sys.stderr)
            print(f'  breakdown: ' + ', '.join(f'{k}={int(v)}' for k,v in sorted(breakdown.items()) if abs(v) > 0), file=sys.stderr)
            snapshot['bas'][alias] = {
                'eia_code': code,
                'name': name,
                'snapshot_hour_utc': hour,
                'carbon_intensity_g_per_kwh': round(ci, 1),
                'fuel_mix_mwh': {k: int(v) for k, v in breakdown.items() if v > 0},
                'net_imports_or_storage_mwh': {k: int(v) for k, v in breakdown.items() if v < 0},
            }
        except Exception as e:
            print(f'  FAILED: {e}', file=sys.stderr)
            snapshot['bas'][alias] = {'error': str(e)}

    out_path = '/Users/nic/dev/murmuration/public/cache/eia_snapshot.json'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f'\nWrote {out_path}', file=sys.stderr)
    # Print summary to stdout
    print(json.dumps({k: v.get('carbon_intensity_g_per_kwh') for k, v in snapshot['bas'].items()}, indent=2))

if __name__ == '__main__':
    main()
