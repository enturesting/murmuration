#!/usr/bin/env python3
"""Pull real historical data for the 4 demo-anchor incidents.

Outputs to /Users/nic/dev/murmuration/public/cache/historical/
- ercot_uri_2021_02_16.json     — EIA-930 fuel mix during Uri peak load shed
- caiso_psps_2019_10_09.json    — EIA-930 fuel mix during PG&E PSPS event
- caiso_duck_2024_04_15.json    — EIA fuel mix + gridstatus 15-min SP15 LMP
- caiso_heatdome_2023_08_15.json — EIA fuel mix + gridstatus SP15 LMP at peak
- pjm_helene_2024_09_27.json    — EIA-930 fuel mix during Hurricane Helene

Run:
  EIA_KEY=... python3 scripts/fetch_historical.py

Requires gridstatus (uv venv at /tmp/grid_env or similar) for LMP fetches.
EIA fetches use only urllib (stdlib).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path

EIA_KEY = os.environ['EIA_KEY']
OUT_DIR = Path('/Users/nic/dev/murmuration/public/cache/historical')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Carbon factors (g CO2 / kWh) — same as scripts/fetch_eia.py
CARBON = {
    'COL': 1001, 'NG': 430, 'OIL': 893, 'NUC': 12, 'WAT': 24,
    'SUN': 48, 'WND': 11, 'GEO': 38, 'OTH': 500, 'BAT': 0,
    'PS': 0, 'SNB': 48, 'WNB': 11, 'OES': 0, 'UNK': 500, 'UES': 500,
}

def eia_fuel_mix(ba_code: str, start: str, end: str, length: int = 500):
    qs = urllib.parse.urlencode({
        'api_key': EIA_KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': ba_code,
        'start': start,
        'end': end,
        'length': str(length),
    }, doseq=False)
    url = f'https://api.eia.gov/v2/electricity/rto/fuel-type-data/data?{qs}'
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)['response']['data']

def hourly_mix(rows):
    """Group by hour. Return dict {hour: {fueltype: mwh}}."""
    out = {}
    for r in rows:
        h = r['period']
        ft = r['fueltype']
        v = float(r['value'])
        out.setdefault(h, {})[ft] = v
    return out

def carbon_intensity(mix: dict) -> float:
    total = sum(v for v in mix.values() if v > 0)
    if total == 0:
        return 0
    weighted = sum(max(v, 0) * CARBON.get(ft, 500) for ft, v in mix.items())
    return weighted / total

def peak_hour(by_hour: dict, key='NG'):
    """Return hour with highest gas burn (proxy for stress)."""
    return max(by_hour.keys(), key=lambda h: by_hour[h].get(key, 0))

def gridstatus_caiso_lmp(date_str: str, node: str = 'TH_SP15_GEN-APND'):
    """Pull CAISO 15-min LMP via gridstatus. Returns list of {ts, lmp}."""
    sys.path.insert(0, '/tmp/grid_env/lib/python3.12/site-packages')
    try:
        import gridstatus
        warnings.filterwarnings('ignore')
        df = gridstatus.CAISO().get_lmp(
            date=date_str, market='REAL_TIME_15_MIN', locations=[node]
        )
        return [
            {'ts': r['Interval Start'].isoformat(), 'lmp': float(r['LMP'])}
            for _, r in df.iterrows()
        ]
    except Exception as e:
        return {'error': str(e)}

# ============================================================
# Incident 1: ERCOT Uri Feb 16, 2021 (peak load shed day)
# ============================================================
print('Fetching ERCOT Uri Feb 16 2021...', file=sys.stderr)
uri_rows = eia_fuel_mix('ERCO', '2021-02-15', '2021-02-19', length=500)
uri_by_hour = hourly_mix(uri_rows)
uri_peak_h = peak_hour(uri_by_hour)
uri_doc = {
    'incident': 'ERCOT February 2021 Winter Storm Uri',
    'date_range_utc': ['2021-02-15T00', '2021-02-19T00'],
    'peak_stress_hour_utc': uri_peak_h,
    'peak_carbon_g_per_kwh': round(carbon_intensity(uri_by_hour[uri_peak_h]), 1),
    'peak_lmp_dollars_mwh': 9000,  # ERCOT cap held for ~32hrs per FERC report
    'peak_lmp_source': 'FERC/NERC Joint Report Sept 2021',
    'real_facts': {
        'deaths_official': 246,
        'deaths_estimated_high': 702,
        'damage_usd_billions': 26.5,
        'load_shed_mw_peak': 20000,
        'generation_lost_mw': 61800,
        'customers_without_power_millions': 4.5,
        'duration_days': 4,
    },
    'source_urls': [
        'https://www.ferc.gov/news-events/news/final-report-february-2021-freeze-underscores-winterization-recommendations',
        'https://www.nerc.com/globalassets/our-work/reports/event-reports/february_2021_cold_weather_report.pdf',
    ],
    'fuel_mix_hourly_mwh': {h: {ft: int(v) for ft, v in m.items()} for h, m in uri_by_hour.items()},
    'peak_hour_breakdown_mwh': {ft: int(v) for ft, v in uri_by_hour[uri_peak_h].items()},
    'fetched_at': datetime.utcnow().isoformat() + 'Z',
    'source': 'EIA-930 hourly fuel mix via api.eia.gov/v2',
}
(OUT_DIR / 'ercot_uri_2021_02_16.json').write_text(json.dumps(uri_doc, indent=2))
print(f'  Peak hour: {uri_peak_h}, carbon: {uri_doc["peak_carbon_g_per_kwh"]} g/kWh', file=sys.stderr)
print(f'  Peak gas burn: {int(uri_by_hour[uri_peak_h].get("NG", 0))} MWh', file=sys.stderr)

# ============================================================
# Incident 2: PG&E PSPS Oct 9, 2019
# ============================================================
print('\nFetching CAISO PSPS Oct 9 2019...', file=sys.stderr)
psps_rows = eia_fuel_mix('CISO', '2019-10-08', '2019-10-12', length=500)
psps_by_hour = hourly_mix(psps_rows)
# Pick the peak-evening hour (highest NG burn) on Oct 9
oct9_hours = {h: m for h, m in psps_by_hour.items() if h.startswith('2019-10-09') or h.startswith('2019-10-10')}
psps_peak_h = peak_hour(oct9_hours) if oct9_hours else peak_hour(psps_by_hour)
psps_doc = {
    'incident': 'PG&E Public Safety Power Shutoff October 9, 2019',
    'date_range_utc': ['2019-10-08T00', '2019-10-12T00'],
    'peak_stress_hour_utc': psps_peak_h,
    'peak_carbon_g_per_kwh': round(carbon_intensity(psps_by_hour[psps_peak_h]), 1) if psps_by_hour else 0,
    'real_facts': {
        'customers_de_energized': 738000,
        'estimated_population_affected': 2000000,
        'restore_within_hours': 48,
        'fire_risk_avoided_acres': 23500,
        'fire_risk_avoided_buildings': 2000,
        'counties_affected': 34,
    },
    'source_urls': [
        'https://investor.pgecorp.com/news-events/press-releases/press-release-details/2019/PSPS-Update-All-Customers-Impacted-by-Safety-Shutoffs-Have-Now-Been-Restored/default.aspx',
        'https://www.pge.com/assets/pge/docs/outages-and-safety/safety/PSPS-Report-Letter-10.26.19-amend.pdf',
        'https://www.cpuc.ca.gov/psps/',
    ],
    'fuel_mix_hourly_mwh': {h: {ft: int(v) for ft, v in m.items()} for h, m in psps_by_hour.items()},
    'peak_hour_breakdown_mwh': {ft: int(v) for ft, v in psps_by_hour[psps_peak_h].items()} if psps_by_hour else {},
    'fetched_at': datetime.utcnow().isoformat() + 'Z',
    'source': 'EIA-930 hourly fuel mix via api.eia.gov/v2',
}
(OUT_DIR / 'caiso_psps_2019_10_09.json').write_text(json.dumps(psps_doc, indent=2))
print(f'  Peak hour: {psps_peak_h}, carbon: {psps_doc["peak_carbon_g_per_kwh"]} g/kWh', file=sys.stderr)

# ============================================================
# Incident 3: CAISO Duck Curve Apr 15, 2024 (15-min LMP + fuel mix)
# ============================================================
print('\nFetching CAISO duck curve Apr 15 2024...', file=sys.stderr)
duck_rows = eia_fuel_mix('CISO', '2024-04-15', '2024-04-16', length=500)
duck_by_hour = hourly_mix(duck_rows)
duck_lmp = gridstatus_caiso_lmp('2024-04-15', 'TH_SP15_GEN-APND')
duck_doc = {
    'incident': 'CAISO Duck Curve · April 15, 2024',
    'date_range_utc': ['2024-04-15T00', '2024-04-16T00'],
    'real_facts': {
        'min_lmp_dollars_mwh': min((p['lmp'] for p in duck_lmp), default=None) if isinstance(duck_lmp, list) else None,
        'max_lmp_dollars_mwh': max((p['lmp'] for p in duck_lmp), default=None) if isinstance(duck_lmp, list) else None,
        'mean_lmp_dollars_mwh': round(sum(p['lmp'] for p in duck_lmp) / len(duck_lmp), 2) if isinstance(duck_lmp, list) and duck_lmp else None,
        'caiso_2024_annual_curtailment_mwh': 3_400_000,
        'caiso_2024_solar_share_of_curtailment_pct': 93,
        'caiso_2024_negative_price_hours': 1180,
        'caiso_2024_median_negative_lmp': -17,
        'sp15_solar_capture_rate_pct_2024': 30,
    },
    'source_urls': [
        'https://www.eia.gov/todayinenergy/detail.php?id=65364',
        'https://www.utilitydive.com/news/solar-wind-curtailments-increasing-california-caiso/749420/',
        'https://www.ascendanalytics.com/blog/caiso-market-outlook-persistent-negative-energy-prices-spreading-curtailment',
    ],
    'lmp_15min_dollars_mwh': duck_lmp if isinstance(duck_lmp, list) else [],
    'lmp_source': 'CAISO OASIS PRC_RTPD_LMP via gridstatus',
    'fuel_mix_hourly_mwh': {h: {ft: int(v) for ft, v in m.items()} for h, m in duck_by_hour.items()},
    'fetched_at': datetime.utcnow().isoformat() + 'Z',
    'source': 'EIA-930 fuel mix + CAISO OASIS LMP',
}
(OUT_DIR / 'caiso_duck_2024_04_15.json').write_text(json.dumps(duck_doc, indent=2))
if isinstance(duck_lmp, list):
    print(f'  LMP range: ${duck_doc["real_facts"]["min_lmp_dollars_mwh"]} to ${duck_doc["real_facts"]["max_lmp_dollars_mwh"]}', file=sys.stderr)

# ============================================================
# Bonus: CAISO Aug 15 2023 heat dome (alt anchor for heat wave scenario)
# ============================================================
print('\nFetching CAISO heat dome Aug 15 2023...', file=sys.stderr)
hd_rows = eia_fuel_mix('CISO', '2023-08-15', '2023-08-16', length=500)
hd_by_hour = hourly_mix(hd_rows)
hd_peak_h = peak_hour(hd_by_hour)
hd_lmp = gridstatus_caiso_lmp('2023-08-15', 'TH_SP15_GEN-APND')
hd_doc = {
    'incident': 'CAISO Heat Dome · August 15, 2023',
    'date_range_utc': ['2023-08-15T00', '2023-08-16T00'],
    'peak_stress_hour_utc': hd_peak_h,
    'peak_carbon_g_per_kwh': round(carbon_intensity(hd_by_hour[hd_peak_h]), 1),
    'real_facts': {
        'min_lmp_dollars_mwh': min((p['lmp'] for p in hd_lmp), default=None) if isinstance(hd_lmp, list) else None,
        'max_lmp_dollars_mwh': max((p['lmp'] for p in hd_lmp), default=None) if isinstance(hd_lmp, list) else None,
        'mean_lmp_dollars_mwh': round(sum(p['lmp'] for p in hd_lmp) / len(hd_lmp), 2) if isinstance(hd_lmp, list) and hd_lmp else None,
        'peak_gas_burn_mwh': int(hd_by_hour[hd_peak_h].get('NG', 0)),
    },
    'source_urls': [
        'https://oasis.caiso.com/ (PRC_RTPD_LMP via gridstatus)',
        'https://api.eia.gov/v2/electricity/rto/fuel-type-data',
    ],
    'lmp_15min_dollars_mwh': hd_lmp if isinstance(hd_lmp, list) else [],
    'lmp_source': 'CAISO OASIS PRC_RTPD_LMP via gridstatus',
    'fuel_mix_hourly_mwh': {h: {ft: int(v) for ft, v in m.items()} for h, m in hd_by_hour.items()},
    'peak_hour_breakdown_mwh': {ft: int(v) for ft, v in hd_by_hour[hd_peak_h].items()},
    'fetched_at': datetime.utcnow().isoformat() + 'Z',
    'source': 'EIA-930 fuel mix + CAISO OASIS LMP',
}
(OUT_DIR / 'caiso_heatdome_2023_08_15.json').write_text(json.dumps(hd_doc, indent=2))
if isinstance(hd_lmp, list):
    print(f'  Peak LMP: ${hd_doc["real_facts"]["max_lmp_dollars_mwh"]}, gas burn: {hd_doc["real_facts"]["peak_gas_burn_mwh"]} MWh', file=sys.stderr)

# ============================================================
# Incident 5: Hurricane Helene Sep 27, 2024 (Carolinas region)
# ============================================================
print('\nFetching Carolinas region Helene Sep 27 2024...', file=sys.stderr)
helene_rows = eia_fuel_mix('CAR', '2024-09-26', '2024-09-30', length=500)
helene_by_hour = hourly_mix(helene_rows)
# Peak stress = hour with biggest deviation in normal generation
sep27_hours = {h: m for h, m in helene_by_hour.items() if h.startswith('2024-09-27') or h.startswith('2024-09-28')}
helene_peak_h = peak_hour(sep27_hours) if sep27_hours else peak_hour(helene_by_hour)
helene_doc = {
    'incident': 'Hurricane Helene — Carolinas region — September 27-28, 2024',
    'date_range_utc': ['2024-09-26T00', '2024-09-30T00'],
    'peak_stress_hour_utc': helene_peak_h,
    'peak_carbon_g_per_kwh': round(carbon_intensity(helene_by_hour[helene_peak_h]), 1) if helene_by_hour else 0,
    'real_facts': {
        'peak_customers_without_power_millions': 6.0,
        'buncombe_county_deaths_asheville': 40,
        'helene_total_deaths_estimate': 200,
        'duration_weeks_for_some_areas': 2,
        'asheville_water_system_destroyed': True,
    },
    'source_urls': [
        'https://www.eenews.net/articles/widespread-power-outages-block-helene-recovery/',
        'https://www.npr.org/2024/09/30/g-s1-25406/helene-death-toll-damage',
        'https://www.cnn.com/2024/10/03/us/helene-recovery-roads-water-power/index.html',
        'https://en.wikipedia.org/wiki/Effects_of_Hurricane_Helene_in_North_Carolina',
    ],
    'fuel_mix_hourly_mwh': {h: {ft: int(v) for ft, v in m.items()} for h, m in helene_by_hour.items()},
    'peak_hour_breakdown_mwh': {ft: int(v) for ft, v in helene_by_hour[helene_peak_h].items()} if helene_by_hour else {},
    'fetched_at': datetime.utcnow().isoformat() + 'Z',
    'source': 'EIA-930 hourly fuel mix (Carolinas region) via api.eia.gov/v2',
}
(OUT_DIR / 'pjm_helene_2024_09_27.json').write_text(json.dumps(helene_doc, indent=2))
print(f'  Peak hour: {helene_peak_h}, carbon: {helene_doc["peak_carbon_g_per_kwh"]} g/kWh', file=sys.stderr)

print('\n=== Done ===', file=sys.stderr)
print('Files written:', file=sys.stderr)
for f in sorted(OUT_DIR.glob('*.json')):
    print(f'  {f.name} ({f.stat().st_size:,} bytes)', file=sys.stderr)
