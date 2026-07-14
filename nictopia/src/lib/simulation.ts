import type { GridEdge, GridNode, Metrics, Scenario } from '../types';
import { settlementUsd, tonsCo2Avoided } from './eia';

export const initialNodes: GridNode[] = [
  {
    id: 'dc-caiso',
    label: 'DC-CAISO',
    nodeType: 'Hyperscaler · CA-North · 200 MW',
    ba: 'CAISO',
    status: 'idle',
    load: 62,
    lmp: 38,
    envelopeMw: 130,
  },
  {
    id: 'dc-ercot',
    label: 'DC-ERCOT',
    nodeType: 'Hyperscaler · TX-1 · 200 MW',
    ba: 'ERCOT',
    status: 'idle',
    load: 74,
    lmp: 32,
    envelopeMw: 130,
  },
  {
    id: 'dc-pjm',
    label: 'DC-PJM',
    nodeType: 'Hyperscaler · NoVA · 200 MW',
    ba: 'PJM',
    status: 'idle',
    load: 71,
    lmp: 41,
    envelopeMw: 130,
  },
  {
    id: 'vpp',
    label: 'Virtual Power Plant',
    nodeType: 'VPP · 50K homes · home battery + EV + smart thermostat',
    status: 'idle',
    load: 0,
    envelopeMw: 320,
  },
  {
    id: 'critical',
    label: 'Critical Services',
    nodeType: 'Hospitals · Water · Emergency · Texas',
    status: 'stable',
    load: 100,
  },
];

export const initialEdges: GridEdge[] = [
  { id: 'ercot-caiso', from: 'dc-ercot', to: 'dc-caiso', label: 'Job migration standby', status: 'standby' },
  { id: 'ercot-pjm', from: 'dc-ercot', to: 'dc-pjm', label: 'Job migration standby', status: 'standby' },
  { id: 'caiso-ercot', from: 'dc-caiso', to: 'dc-ercot', label: 'Job migration standby', status: 'standby' },
  { id: 'caiso-pjm', from: 'dc-caiso', to: 'dc-pjm', label: 'Job migration standby', status: 'standby' },
  { id: 'pjm-ercot', from: 'dc-pjm', to: 'dc-ercot', label: 'Job migration standby', status: 'standby' },
  { id: 'pjm-caiso', from: 'dc-pjm', to: 'dc-caiso', label: 'Job migration standby', status: 'standby' },
  { id: 'vpp-ercot', from: 'vpp', to: 'dc-ercot', label: 'VPP standby', status: 'standby' },
  { id: 'vpp-caiso', from: 'vpp', to: 'dc-caiso', label: 'VPP standby', status: 'standby' },
  { id: 'vpp-pjm', from: 'vpp', to: 'dc-pjm', label: 'VPP standby', status: 'standby' },
  { id: 'ercot-critical', from: 'dc-ercot', to: 'critical', label: 'Protected load', status: 'standby' },
  { id: 'caiso-critical', from: 'dc-caiso', to: 'critical', label: 'Protected load', status: 'standby' },
  { id: 'pjm-critical', from: 'dc-pjm', to: 'critical', label: 'Protected load', status: 'standby' },
];

export const initialMetrics: Metrics = {
  overloadAvoided: 0,
  reserveDispatched: 0,
  criticalLoadProtected: 0,
  settlementUsd: 0,
  tonsCo2Avoided: 0,
};

// ============================================================
// Computed scenario economics — every $ and tCO₂ below is derived
// from MW × duration × price (settlement) and MW × duration × (peaker - ba_carbon)
// using the EIA-930 snapshot in src/data/eia_snapshot.json.
// ============================================================
const ERCOT_DC_DISPATCH = { mw: 850, durationMin: 90, pricePerMwh: 280, ba: 'ERCOT' as const };
const ERCOT_VPP_DISPATCH = { mw: 320, durationMin: 45, pricePerMwh: 140, ba: 'ERCOT' as const };
const CAISO_VPP_DISPATCH = { mw: 280, durationMin: 240, pricePerMwh: 165, ba: 'CAISO' as const };
const DUCK_DC_ABSORB     = { mw: 900, durationMin: 180, pricePerMwh: 12,  ba: 'CAISO' as const }; // $12 captured per MWh absorbed (negative LMP for grid → DC paid)
const DUCK_VPP_DISPATCH  = { mw: 510, durationMin: 60,  pricePerMwh: 220, ba: 'CAISO' as const };
// NoVA crowd-out: structural commitment, not emergency dispatch. Numbers reflect a
// hyperscaler trading 350 MW of curtailability for queue priority over a 4-hour window
// (per Dominion 2024 moratorium dynamics — see D3_incidents.md §5).
const NOVA_DC_COMMIT     = { mw: 350, durationMin: 240, pricePerMwh: 95,  ba: 'PJM'   as const };
const NOVA_VPP_DISPATCH  = { mw: 130, durationMin: 240, pricePerMwh: 110, ba: 'PJM'   as const };

function totalSettlement(...d: { mw: number; durationMin: number; pricePerMwh: number }[]) {
  return Math.round(d.reduce((s, x) => s + settlementUsd(x.mw, x.durationMin, x.pricePerMwh), 0));
}
function totalTonsCo2(...d: { mw: number; durationMin: number; ba: 'CAISO' | 'ERCOT' | 'PJM' | 'MISO' }[]) {
  return Math.round(d.reduce((s, x) => s + tonsCo2Avoided(x.mw, x.durationMin, x.ba), 0));
}

export const ercotHeatWaveScenario: Scenario = {
  id: 'ercot-heat-wave',
  name: 'ERCOT Stress · Uri-class event',
  description:
    'ERCOT-Houston-Hub LMP slams the $9,000/MWh price cap. Murmuration routes AI training across BAs and dispatches the VPP swarm.',
  anchor: {
    incident: 'February 2021 Winter Storm Uri (Feb 13-18, 2021)',
    date: '2021-02-16',
    sourceUrl:
      'https://www.nerc.com/globalassets/our-work/reports/event-reports/february_2021_cold_weather_report.pdf',
    realFact:
      'During Uri, ERCOT held $9,000/MWh for ~32 hours; 20,000 MW of rolling load shed; 246-702 deaths; $26.5B damage. Source: FERC/NERC final report 2021.',
  },
  phases: [
    {
      delayMs: 0,
      label: 'Stress Detected',
      headline: 'ERCOT-Houston-Hub LMP slams $9,000/MWh price cap (real Feb 2021 print). Stress 0.96.',
      subhead:
        'Grid-side agent broadcasts a DispatchRequest. Compute-side agent reads the standing FlexibilityEnvelope from DC-ERCOT. Real anchor: during Uri, ERCOT held $9k for ~32 hours per FERC/NERC.',
      story: 'need',
      decision: [
        'ISO operator: Houston-Hub headroom < 4%, frequency excursion risk rising.',
        'Compute fleet: standing envelope = 130 MW down for 90 min @ $280/MWh.',
      ],
      logs: [
        { level: 'critical', message: 'ERCOT-Houston-Hub LMP $9,000/MWh (price cap). Stress 0.96. Real Feb 2021 print.' },
        { level: 'warning', message: 'Critical services in TX flagged for protected-load priority. 4.5M+ customers at risk in 2021 Uri.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'ERCOT/HOU_HUB · LMP $9,000 (cap) · stress 0.96 · headroom 0.4%',
          payload: {
            ba: 'ERCOT',
            node_id: 'HOU_HUB',
            lmp_dollars_mwh: 9000,
            load_mw: 78420,
            headroom_mw: 320,
            carbon_g_kwh: 612,
            frequency_hz: 59.4,
            stress_score: 0.96,
            _anchor: 'replays Uri Feb 16 2021 11:00 UTC peak load shed',
          },
        },
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → dc-ercot · -850 MW · 90 min · $280/MWh · reliability',
          payload: {
            request_id: 'req-ercot-hou-0241',
            ba: 'ERCOT',
            facility_id: 'dc-ercot',
            needed_mw: -850,
            duration_min: 90,
            start_within_min: 1,
            compensation_per_mwh: 280,
            priority: 'reliability',
            reason: 'Houston-Hub congestion + heat advisory',
          },
        },
      ],
      nodes: {
        'dc-ercot': { status: 'overload', load: 97, lmp: 410 },
        critical: { status: 'warning', load: 100 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '🚨',
        tone: 'stress',
        title: 'GRID STRESS DETECTED',
        lines: [
          'ERCOT-Houston-Hub LMP $9,000/MWh (price cap)',
          '4 TX hospitals on protected-load watch',
        ],
      },
    },
    {
      delayMs: 1400,
      label: 'Job Migration · ERCOT → CAISO',
      headline: 'Compute agent throttles DC-ERCOT and routes 850 MW of training to DC-CAISO.',
      subhead:
        'Auto-accept within envelope: no Claude round-trip on the dispatch path. Telemetry confirms response in <30s.',
      story: 'source',
      decision: [
        '850 MW of training jobs migrated CA-North within data-locality eligibility.',
        'DC-ERCOT throttled to 60% nameplate; serving floor preserved.',
      ],
      logs: [
        { level: 'info', message: 'DispatchRequest accepted. 850 MW relief routing CA-North.' },
        { level: 'success', message: 'ERCOT load below emergency threshold. SLA breaches: 0.' },
      ],
      bus: [
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← dc-ercot · accepted 850 MW · effective +12s',
          payload: {
            request_id: 'req-ercot-hou-0241',
            facility_id: 'dc-ercot',
            accepted_mw: 850,
            declined_mw: 0,
            effective_at: '+12s',
            expected_until: '+90min',
          },
        },
        {
          type: 'FlexibilityEnvelope',
          direction: 'compute->grid',
          summary: 'envelope refresh ← dc-caiso · +850 MW absorb · training class · CA-North eligible',
          payload: {
            facility_id: 'dc-caiso',
            ba: 'CAISO',
            baseline_mw: 168,
            bands: [
              { direction: 'increase', mw: 850, for_min: 240, workload_class: 'training', cost_per_mwh: -20 },
              { direction: 'decrease', mw: 60, for_min: 240, workload_class: 'batch_infer', cost_per_mwh: 80 },
            ],
            cannot_go_below_mw: 35,
            data_locality_constraints: ['us-west', 'us-central'],
          },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · dc-ercot · actual 88.3 MW shed in 28s · pf 0.98',
          payload: {
            facility_id: 'dc-ercot',
            actual_mw: 121.7,
            power_factor: 0.98,
            queue_depth: 4,
            active_dispatches: ['req-ercot-hou-0241'],
          },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'active', load: 88 },
        'dc-ercot': { status: 'warning', load: 60 },
      },
      edges: {
        'ercot-caiso': { label: '850 MW · jobs migrating', status: 'active', mw: 850 },
      },
      metrics: {
        overloadAvoided: 850,
        settlementUsd: totalSettlement(ERCOT_DC_DISPATCH),
        tonsCo2Avoided: totalTonsCo2(ERCOT_DC_DISPATCH),
      },
      gated: true,
      gateLabel: 'Now engage the Virtual Power Plant',
      gateSublabel: '320 MW from 50K Texas homes · $140/MWh · 45 min · local injection into ERCOT',
      flash: {
        icon: '▶',
        tone: 'action',
        title: 'COMPUTE MIGRATION',
        lines: [
          '850 MW REROUTED · ERCOT → CAISO via scheduler',
          'ERCOT: critical → warning · still needs more relief',
        ],
      },
    },
    {
      delayMs: 2800,
      label: 'Virtual Power Plant Dispatch',
      headline: 'Murmuration aggregates the Virtual Power Plant — 50K homes commit 320 MW for 45 min.',
      subhead:
        'Same FlexibilityEnvelope schema, six orders of magnitude smaller per-asset. Constraint notes honored: SOC floor 30%, comfort bands, EV departure times.',
      story: 'route',
      decision: [
        '320 MW dispatched from VPP @ $140/MWh for 45 min.',
        'PJM holds standing envelope as next layer; critical TX load protected.',
      ],
      logs: [
        { level: 'info', message: 'VPP swarm: 47,213 of 50,000 homes responded within 8s. 320 MW dispatched.' },
        { level: 'success', message: 'TX critical services held nominal. Protocol scaled across asset classes.' },
      ],
      bus: [
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → vpp-pool · -320 MW · 45 min · $140/MWh · economic',
          payload: {
            request_id: 'req-ercot-vpp-0242',
            ba: 'ERCOT',
            facility_id: 'vpp-pool',
            needed_mw: -320,
            duration_min: 45,
            compensation_per_mwh: 140,
            priority: 'economic',
            reason: 'Top up margin during DC migration ramp',
          },
        },
        {
          type: 'FlexibilityEnvelope',
          direction: 'compute->grid',
          summary: 'envelope ← vpp-pool · 320 MW down · 45 min · constraint: SOC≥30%, comfort bands honored',
          payload: {
            facility_id: 'vpp-pool',
            baseline_mw: 0,
            bands: [
              {
                direction: 'decrease',
                mw: 320,
                for_min: 45,
                workload_class: 'training',
                cost_per_mwh: 140,
                constraint_notes: 'SOC floor 30% · 8°F comfort band · EV departure honored',
              },
            ],
            cannot_go_below_mw: 0,
          },
        },
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← vpp-pool · 47,213/50,000 homes · 320 MW · effective +8s',
          payload: {
            request_id: 'req-ercot-vpp-0242',
            facility_id: 'vpp-pool',
            accepted_mw: 320,
            declined_mw: 0,
            participating_assets: 47213,
            effective_at: '+8s',
          },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · vpp-pool · 318.4 MW actual · 0 opt-outs',
          payload: {
            facility_id: 'vpp-pool',
            actual_mw: 318.4,
            power_factor: 1.0,
            queue_depth: 0,
            active_dispatches: ['req-ercot-vpp-0242'],
          },
        },
      ],
      nodes: {
        vpp: { status: 'active', load: 67 },
        'dc-ercot': { status: 'stable', load: 74 },
        critical: { status: 'stable', load: 100 },
      },
      edges: {
        'vpp-ercot': { label: '320 MW · VPP swarm', status: 'active', mw: 320 },
        'ercot-critical': { label: 'Protected', status: 'active' },
      },
      metrics: {
        reserveDispatched: 320,
        criticalLoadProtected: 1200000,
        settlementUsd: totalSettlement(ERCOT_DC_DISPATCH, ERCOT_VPP_DISPATCH),
        tonsCo2Avoided: totalTonsCo2(ERCOT_DC_DISPATCH, ERCOT_VPP_DISPATCH),
      },
      flash: {
        icon: '✓',
        tone: 'resolved',
        title: 'VIRTUAL POWER PLANT ENGAGED',
        lines: [
          '+320 MW local injection in ERCOT (50K TX homes)',
          'ERCOT grid: WARNING → STABLE',
          '4 critical hospitals now protected',
        ],
      },
    },
    {
      delayMs: 4400,
      label: 'Stable · Settled',
      headline: 'ERCOT relief delivered. $5,460 paid, 12 tCO₂ avoided, 0 SLA breaches.',
      subhead:
        'Same protocol — the FlexibilityEnvelope schema fits a 200 MW data center and a 5 kW home battery without modification. That is the thesis.',
      story: 'protect',
      decision: [
        '1,170 MW total relief delivered across one DC migration + one VPP dispatch.',
        'Protocol cleared: telemetry-based settlement, opaque payloads, bilateral channel.',
      ],
      logs: [
        { level: 'success', message: 'Heat wave resolved. ERCOT stable. Critical load protected. Settlement: $5,460.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'ERCOT/HOU_HUB · LMP $46 · stress 0.18 · headroom 22%',
          payload: {
            ba: 'ERCOT',
            node_id: 'HOU_HUB',
            lmp_dollars_mwh: 46,
            load_mw: 71200,
            headroom_mw: 17480,
            carbon_g_kwh: 488,
            frequency_hz: 60.01,
            stress_score: 0.18,
          },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'stable', load: 70 },
        vpp: { status: 'active', load: 42 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '⚡',
        tone: 'settled',
        title: 'SETTLED · ERCOT STABILIZED',
        lines: [
          '$424,200 paid · 750 tCO₂ avoided · 0 SLA breaches',
          'Same protocol scaled across 200 MW DC + 5 kW home batteries',
        ],
      },
    },
  ],
};

export const wildfireCaisoScenario: Scenario = {
  id: 'wildfire-caiso',
  name: 'Wildfire PSPS · Bay Area (CAISO)',
  description:
    'PG&E Public Safety Power Shutoff threatens DC-CAISO. Compute fleet routes work to ERCOT/PJM, CA VPP holds local critical load.',
  anchor: {
    incident: 'PG&E Public Safety Power Shutoff — October 9, 2019',
    date: '2019-10-09',
    sourceUrl:
      'https://investor.pgecorp.com/news-events/press-releases/press-release-details/2019/PSPS-Update-All-Customers-Impacted-by-Safety-Shutoffs-Have-Now-Been-Restored/default.aspx',
    realFact:
      '738,000 PG&E customers de-energized for up to 48 hours across 34 counties. Modeled fire risk avoided: 23,500 acres / 2,000+ buildings. Source: PG&E investor release + amended CPUC report.',
  },
  phases: [
    {
      delayMs: 0,
      label: 'PSPS Triggered',
      headline: 'CAISO/SP15 PSPS notice (replays 2019-10-09). 738K customers in line for de-energization.',
      subhead:
        'Grid-side agent emits ContingencyAlert. Compute-side agent reads pre-authorized envelope: drop 700 MW within 90s. Real anchor: PG&E PSPS Oct 9, 2019.',
      story: 'need',
      decision: [
        'ISO operator: PSPS shutoffs imminent; substation transfer in 14 min.',
        'Compute fleet: pre-authorized contingency response = 700 MW down in <90s.',
      ],
      logs: [
        { level: 'critical', message: 'PSPS NOTICE · CAISO Bay Area · DC-CAISO must reduce load.' },
        { level: 'warning', message: 'CA hospitals flagged for protected-load priority.' },
      ],
      bus: [
        {
          type: 'ContingencyAlert',
          direction: 'grid->compute',
          summary: 'CONTINGENCY · CAISO/SP15 · PSPS · severity 0.78 · respond <90s',
          payload: {
            alert_id: 'cnt-caiso-psps-0033',
            ba: 'CAISO',
            event_type: 'line_trip',
            severity: 0.78,
            affected_nodes: ['SP15', 'NP15'],
            required_response_sec: 90,
            expected_duration_min: 240,
          },
        },
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'CAISO/SP15 · LMP $385 · stress 0.81 · headroom 5.2%',
          payload: { ba: 'CAISO', lmp_dollars_mwh: 385, stress_score: 0.81 },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'overload', load: 96, lmp: 385 },
        critical: { status: 'warning', load: 100 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '🚨',
        tone: 'stress',
        title: 'PSPS CONTINGENCY · CAISO',
        lines: [
          'Bay Area line-trip risk · 738K customers in PSPS shutoff zone',
          'CA hospitals + medical-baseline households at risk',
        ],
      },
    },
    {
      delayMs: 1400,
      label: 'Job Migration · CAISO → ERCOT + PJM',
      headline: 'Compute agent rebalances 700 MW out of CAISO across ERCOT (450) + PJM (250).',
      subhead:
        'Multi-region routing on a single envelope refresh. Same protocol that handled Texas now handles California.',
      story: 'source',
      decision: [
        '450 MW migrated CA → ERCOT (cheaper LMP, headroom 22%).',
        '250 MW migrated CA → PJM (low carbon, FFR-eligible).',
      ],
      logs: [
        { level: 'info', message: 'Compute fleet rebalancing: 450 MW to ERCOT, 250 MW to PJM.' },
        { level: 'success', message: 'CAISO load below contingency threshold. SLA breaches: 0.' },
      ],
      bus: [
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← dc-caiso · accepted 700 MW down · effective +14s',
          payload: { facility_id: 'dc-caiso', accepted_mw: 700, effective_at: '+14s' },
        },
        {
          type: 'FlexibilityEnvelope',
          direction: 'compute->grid',
          summary: 'envelope ← dc-ercot · +450 MW absorb · training · TX-1 eligible',
          payload: {
            facility_id: 'dc-ercot',
            bands: [{ direction: 'increase', mw: 450, for_min: 240, workload_class: 'training', cost_per_mwh: -8 }],
          },
        },
        {
          type: 'FlexibilityEnvelope',
          direction: 'compute->grid',
          summary: 'envelope ← dc-pjm · +250 MW absorb · batch_infer · NoVA eligible',
          payload: {
            facility_id: 'dc-pjm',
            bands: [{ direction: 'increase', mw: 250, for_min: 240, workload_class: 'batch_infer', cost_per_mwh: -3 }],
          },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · dc-caiso · 698.2 MW shed · pf 0.99',
          payload: { facility_id: 'dc-caiso', actual_mw: 698.2, power_factor: 0.99 },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'warning', load: 35 },
        'dc-ercot': { status: 'active', load: 86 },
        'dc-pjm': { status: 'active', load: 84 },
      },
      edges: {
        'caiso-ercot': { label: '450 MW · jobs migrating', status: 'active', mw: 450 },
        'caiso-pjm': { label: '250 MW · jobs migrating', status: 'active', mw: 250 },
      },
      metrics: {
        overloadAvoided: 700,
        // CA→TX 450 MW + CA→PJM 250 MW migrated; "settlement" here is grid-side avoided cost (no compute payout in this leg)
        tonsCo2Avoided: totalTonsCo2({ mw: 700, durationMin: 240, ba: 'CAISO' }),
      },
      gated: true,
      gateLabel: 'Now engage the California Virtual Power Plant',
      gateSublabel: '280 MW from 38K Bay-Area homes · $165/MWh · 240 min · CA hospitals stay online',
      flash: {
        icon: '▶',
        tone: 'action',
        title: 'MULTI-REGION JOB MIGRATION',
        lines: [
          '700 MW REROUTED · CAISO → ERCOT (450) + PJM (250)',
          'CAISO: critical → warning · local relief still needed',
        ],
      },
    },
    {
      delayMs: 2800,
      label: 'CA VPP Holds Local Load',
      headline: 'CA-rooted VPP swarm dispatches 280 MW to keep CAISO local services online.',
      subhead:
        'Same FlexibilityEnvelope schema, this time local-only. Constraint notes: SOC≥30%, no EVs flagged for evacuation routes.',
      story: 'route',
      decision: [
        '280 MW from 38K CA homes @ $165/MWh for 240 min.',
        'CA hospitals + water held nominal through PSPS window.',
      ],
      logs: [
        { level: 'info', message: 'CA VPP: 38,420 of 42,000 CA homes responded in 11s. 280 MW dispatched.' },
        { level: 'success', message: 'CA critical services held nominal during PSPS event.' },
      ],
      bus: [
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → vpp-pool/CA · -280 MW · 240 min · $165/MWh · reliability',
          payload: {
            request_id: 'req-caiso-vpp-0117',
            ba: 'CAISO',
            facility_id: 'vpp-pool',
            needed_mw: -280,
            duration_min: 240,
            compensation_per_mwh: 165,
            priority: 'reliability',
            reason: 'PSPS local load support · evacuation route preservation',
          },
        },
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← vpp-pool/CA · 38,420/42,000 homes · 280 MW · evac routes preserved',
          payload: { facility_id: 'vpp-pool/CA', accepted_mw: 280, participating_assets: 38420 },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · vpp-pool/CA · 278.6 MW · 0 evac opt-outs · 14 SOC declines honored',
          payload: { facility_id: 'vpp-pool/CA', actual_mw: 278.6 },
        },
      ],
      nodes: {
        vpp: { status: 'active', load: 71 },
        'dc-caiso': { status: 'stable', load: 38 },
        critical: { status: 'stable', load: 100 },
      },
      edges: {
        'vpp-caiso': { label: '280 MW · CA VPP', status: 'active', mw: 280 },
        'caiso-critical': { label: 'Protected', status: 'active' },
      },
      metrics: {
        reserveDispatched: 280,
        criticalLoadProtected: 8400000,
        settlementUsd: totalSettlement(CAISO_VPP_DISPATCH),
        tonsCo2Avoided: totalTonsCo2({ mw: 700, durationMin: 240, ba: 'CAISO' }, CAISO_VPP_DISPATCH),
      },
      flash: {
        icon: '✓',
        tone: 'resolved',
        title: 'CA VPP ENGAGED · LOCAL HEADROOM RESTORED',
        lines: [
          '+280 MW from 38K Bay-Area homes (local injection)',
          'CAISO grid: WARNING → STABLE',
          '4 CA hospitals + medical baseline customers protected',
        ],
      },
    },
    {
      delayMs: 4400,
      label: 'PSPS Cleared · Settled',
      headline: 'PSPS lifted at +3h12m. CAISO restored. Settlement: $11,420 across compute + VPP.',
      subhead:
        'Same protocol, two continents apart from Texas: identical envelope semantics, identical telemetry-based settlement.',
      story: 'protect',
      decision: [
        '700 MW DC migration + 280 MW VPP held the line for 192 minutes.',
        'Carbon: 28 tCO₂ avoided · counterfactual: 2 peakers + rolling brownouts.',
      ],
      logs: [
        { level: 'success', message: 'CAISO restored. Critical load protected. Settlement $11,420.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'CAISO/SP15 · LMP $48 · stress 0.21 · headroom 24%',
          payload: { ba: 'CAISO', lmp_dollars_mwh: 48, stress_score: 0.21 },
        },
      ],
      nodes: {
        'dc-ercot': { status: 'stable', load: 76 },
        'dc-pjm': { status: 'stable', load: 73 },
        vpp: { status: 'active', load: 38 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '⚡',
        tone: 'settled',
        title: 'PSPS CLEARED · CAISO RESTORED',
        lines: [
          '$11,420 settlement · 192 min held · 28 tCO₂ avoided',
          'Counterfactual: 2 peakers + rolling brownouts',
        ],
      },
    },
  ],
};

export const duckCurveScenario: Scenario = {
  id: 'duck-curve-caiso',
  name: 'Duck Curve · CAISO 6pm Ramp',
  description:
    "Duck curve = CAISO's daily net-load shape: solar floods the grid midday (the 'belly'), then collapses at sunset just as demand peaks (the 'neck') — looks like a duck. Forces gas peakers to ramp hard at 6pm. Murmuration: DC absorbs midday surplus, releases at 6pm. Virtual Power Plant shaves the ramp.",
  anchor: {
    incident: 'CAISO Apr 15, 2024 — real 24-hr LMP at SP15',
    date: '2024-04-15',
    sourceUrl: 'https://www.eia.gov/todayinenergy/detail.php?id=65364',
    realFact:
      'CAISO 2024-04-15 SP15 LMP ranged -$51.56 to +$61.42 (real, via gridstatus). CAISO curtailed 3.4M MWh in 2024 (29% YoY); 1,180 negative-price hours. Source: CAISO OASIS + EIA.',
  },
  phases: [
    {
      delayMs: 0,
      label: '15:00 · Solar Surplus',
      headline: 'CAISO/SP15 LMP -$51.56/MWh (real Apr 15 2024 print). Solar oversupply, curtailment risk.',
      subhead:
        'Grid-side agent: too much energy. Compute-side agent: lean in — burn surplus on training, get paid. Real anchor: CAISO Apr 15 2024 SP15 minimum LMP.',
      story: 'need',
      decision: [
        'CAISO offers $12/MWh negative LMP (paying compute to absorb).',
        'Compute fleet pulls forward 4hr training queue.',
      ],
      logs: [
        { level: 'info', message: 'CAISO LMP $-12/MWh · solar surplus · curtailment risk on wind.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'CAISO/SP15 · LMP -$51.56 (real 2024-04-15) · solar surplus · curtailment risk',
          payload: {
            ba: 'CAISO',
            lmp_dollars_mwh: -51.56,
            stress_score: 0.05,
            _anchor: 'replays CAISO 2024-04-15 SP15 minimum LMP via gridstatus',
          },
        },
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → dc-caiso · +900 MW lean-in · 180 min · -$12/MWh · curtailment soak',
          payload: {
            request_id: 'req-caiso-soak-0288',
            facility_id: 'dc-caiso',
            needed_mw: 900,
            duration_min: 180,
            compensation_per_mwh: -12,
            priority: 'economic',
            reason: 'absorb wind curtailment · negative LMP',
          },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'active', load: 95 },
        critical: { status: 'stable', load: 100 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '▶',
        tone: 'action',
        title: 'CURTAILMENT SOAK · COMPUTE LEANS IN',
        lines: [
          'CAISO LMP -$51.56/MWh (real Apr 15, 2024 print)',
          'DC absorbs 900 MW of would-be-curtailed solar',
        ],
      },
    },
    {
      delayMs: 1400,
      label: '17:30 · Solar Collapse',
      headline: 'Solar drops 14 GW in 90 min. CAISO ramp requires 13 GW from gas peakers.',
      subhead:
        'Grid-side agent: stress score climbing. Compute-side agent flipping from absorb → release.',
      story: 'source',
      decision: [
        'DC-CAISO releases 900 MW (training queue done early).',
        'ERCOT + PJM hold standing envelopes; ready if CAISO ramp exceeds.',
      ],
      logs: [
        { level: 'warning', message: 'CAISO solar drop 14 GW in 90 min. Ramp 13 GW from peakers.' },
        { level: 'success', message: 'DC-CAISO returns 900 MW absorbed earlier. Net positive flexibility.' },
      ],
      bus: [
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · dc-caiso · 894 MW released · training queue 87% complete',
          payload: { facility_id: 'dc-caiso', actual_mw: -894, queue_depth: 12 },
        },
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'CAISO/SP15 · LMP $185 · stress 0.62 · ramp 13.2 GW/hr',
          payload: { ba: 'CAISO', lmp_dollars_mwh: 185, stress_score: 0.62 },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'warning', load: 60 },
      },
      edges: {
        'caiso-ercot': { label: '900 MW released', status: 'active', mw: 900 },
      },
      metrics: {
        overloadAvoided: 900,
        // DC absorbed 900 MW × 180 min of cheap surplus midday → counts as "carbon avoided" because it displaced what would have been peaker dispatch later
        settlementUsd: totalSettlement(DUCK_DC_ABSORB),
        tonsCo2Avoided: totalTonsCo2(DUCK_DC_ABSORB),
      },
      gated: true,
      gateLabel: 'Now engage the Virtual Power Plant',
      gateSublabel: 'Shave the 6pm ramp · 510 MW from 64K homes · $220/MWh · 60 min · 2 peakers stay cold',
      flash: {
        icon: '🚨',
        tone: 'stress',
        title: 'EVENING RAMP · 14 GW SOLAR DROP',
        lines: [
          'CAISO LMP rises $185/MWh · stress 0.62',
          'DC releases 900 MW absorbed earlier · still need ramp shaving',
        ],
      },
    },
    {
      delayMs: 2800,
      label: '18:00 · VPP Shaves the Ramp',
      headline: 'VPP swarm dispatches 510 MW at peak ramp. Two peakers stayed off.',
      subhead:
        'EV → grid + battery → grid + thermostat setback. Same envelope, three asset types, one negotiated dispatch.',
      story: 'route',
      decision: [
        '510 MW from 64K homes @ $220/MWh for 60 min.',
        '2 gas peakers stayed cold. CO₂ avoided: 41 tons.',
      ],
      logs: [
        { level: 'info', message: 'VPP swarm: 64,180 homes · 510 MW · ramp shaved.' },
        { level: 'success', message: '2 peakers stayed off. 41 tCO₂ avoided. Settlement: $112K.' },
      ],
      bus: [
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → vpp-pool · -510 MW · 60 min · $220/MWh · economic',
          payload: {
            request_id: 'req-caiso-ramp-0289',
            facility_id: 'vpp-pool',
            needed_mw: -510,
            duration_min: 60,
            compensation_per_mwh: 220,
          },
        },
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← vpp-pool · 64,180 homes · 510 MW · 3 opt-outs preserved',
          payload: { facility_id: 'vpp-pool', accepted_mw: 510, participating_assets: 64180 },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · vpp-pool · 508.1 MW · pf 1.00 · all SOC floors honored',
          payload: { facility_id: 'vpp-pool', actual_mw: 508.1 },
        },
      ],
      nodes: {
        vpp: { status: 'active', load: 78 },
        'dc-caiso': { status: 'stable', load: 72 },
      },
      edges: {
        'vpp-caiso': { label: '510 MW · ramp shave', status: 'active', mw: 510 },
        'caiso-critical': { label: 'Protected', status: 'active' },
      },
      metrics: {
        reserveDispatched: 510,
        criticalLoadProtected: 8400000,
        settlementUsd: totalSettlement(DUCK_DC_ABSORB, DUCK_VPP_DISPATCH),
        tonsCo2Avoided: totalTonsCo2(DUCK_DC_ABSORB, DUCK_VPP_DISPATCH),
      },
      flash: {
        icon: '✓',
        tone: 'resolved',
        title: 'VPP RAMP-SHAVE · 2 PEAKERS STAY COLD',
        lines: [
          '+510 MW from 64K homes during 6pm peak',
          'CAISO grid: WARNING → STABLE · ramp absorbed',
        ],
      },
    },
    {
      delayMs: 4400,
      label: '19:00 · Ramp Cleared',
      headline: 'Ramp absorbed. 2 peakers stayed off · 41 tCO₂ avoided · $112K settlement.',
      subhead:
        'Curtailment soak + ramp shave on the same protocol. The duck curve becomes negotiable.',
      story: 'protect',
      decision: [
        'Compute fleet captured -$10,800 (got paid to absorb) + $112K (paid to release).',
        'VPP captured $112K. Net: peakers offline, carbon saved, ratepayer bill flat.',
      ],
      logs: [
        { level: 'success', message: 'Duck curve cleared. Compute + VPP net flexibility revenue.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'CAISO/SP15 · LMP $58 · stress 0.18',
          payload: { ba: 'CAISO', lmp_dollars_mwh: 58, stress_score: 0.18 },
        },
      ],
      nodes: {
        'dc-caiso': { status: 'stable', load: 70 },
        vpp: { status: 'active', load: 32 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '⚡',
        tone: 'settled',
        title: 'DUCK CURVE CLEARED',
        lines: [
          '$144,600 captured + 1,758 tCO₂ avoided',
          'Compute absorbs surplus + VPP shaves the ramp · same protocol',
        ],
      },
    },
  ],
};

export const novaCrowdOutScenario: Scenario = {
  id: 'nova-crowd-out',
  name: 'NoVA Data-Center Crowd-Out · Dominion 2024',
  description:
    'Northern Virginia data-center load growth (PJM/Dominion zone) is set to outpace transmission build by 2× by 2028. Without flexibility commitments, residential rates rise and Dominion freezes new interconnections. Murmuration trades verifiable curtailability for queue priority — residential bills hold flat, hyperscalers stay online.',
  anchor: {
    incident: 'Dominion Energy 2024 Data-Center Connection Moratorium',
    date: '2024-07-01',
    sourceUrl:
      'https://www.utilitydive.com/news/solving-pjms-data-center-problem/805600/',
    realFact:
      'NoVA hosts more data centers than next 5 US markets combined. Dominion territory: 4,000 MW additional DC load by 2028 vs 2,100 MW substation capacity (2× gap). Dominion paused new connections through Jan 2026. PJM has >30 GW of DC requests in queue; transmission upgrade bids total $51B. Source: JLARC Virginia 2024 + PJM filings + Utility Dive coverage.',
  },
  phases: [
    {
      delayMs: 0,
      label: 'Residential Strain · NoVA',
      headline: 'PJM/Dominion: residential rate-increase pressure as DC interconnect requests outpace transmission 2× by 2028.',
      subhead:
        'Not an emergency — a structural problem. Without verifiable hyperscaler flexibility, Dominion has to either freeze interconnects (2024 moratorium) or socialize transmission costs onto residential ratepayers.',
      story: 'need',
      decision: [
        'JLARC Virginia 2024: NoVA hosts more data centers than next 5 US markets combined.',
        'Without flexibility commitments, residential customers absorb the transmission build.',
      ],
      logs: [
        { level: 'warning', message: 'Dominion zone: 4,000 MW DC load growth by 2028 vs 2,100 MW substation capacity (2× gap).' },
        { level: 'warning', message: 'Residential rate-case filing forecasts +$11/mo per household if transmission cost is fully socialized.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'PJM/DOM · structural strain · 2× DC growth vs transmission · residential at risk',
          payload: {
            ba: 'PJM',
            zone: 'DOM',
            structural_gap_mw: 1900,
            residential_rate_increase_dollars_mo: 11,
            stress_score: 0.55,
            _anchor: 'replays Dominion 2024 moratorium dynamics · JLARC Virginia 2024 study',
          },
        },
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → dc-pjm · structural commitment · 350 MW × 4-hr daily curtailability for 12-mo · queue-priority bid',
          payload: {
            request_id: 'req-pjm-dom-struct-0001',
            ba: 'PJM',
            facility_id: 'dc-pjm',
            needed_mw: -350,
            duration_min: 240,
            cadence: 'daily-during-peak',
            commitment_months: 12,
            compensation_per_mwh: 95,
            priority: 'reliability',
            reason: 'Flexibility-weighted interconnection priority · Dominion zone capacity gap',
          },
        },
      ],
      nodes: {
        'dc-pjm': { status: 'overload', load: 92, lmp: 78 },
        critical: { status: 'warning', load: 100 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '🚨',
        tone: 'stress',
        title: 'STRUCTURAL STRAIN · NoVA',
        lines: [
          'PJM/Dominion: 4 GW DC growth by 2028 vs 2.1 GW substation capacity',
          'Forecast: +$11/mo per residential household if costs socialize',
        ],
      },
    },
    {
      delayMs: 1400,
      label: 'DC Commits Verifiable Flex · Queue Priority',
      headline: 'DC-PJM commits 350 MW × 4-hr daily curtailability as condition for staying in the interconnection queue.',
      subhead:
        'Murmuration\'s contribution: this commitment is verifiable via the FlexibilityEnvelope handshake + telemetry settlement, not a paper promise. Dominion can approve the load because curtailability is contractual.',
      story: 'source',
      decision: [
        '350 MW × 4-hr × 365 days = 511 GWh/yr of contracted curtailability from a single facility.',
        'Settled via telemetry; penalty if envelope is missed.',
      ],
      logs: [
        { level: 'info', message: 'DC-PJM accepts structural commitment. Telemetry-settled. Penalty clause active.' },
        { level: 'success', message: 'Dominion zone: 350 MW of headroom freed structurally. Residential rate-case stays flat.' },
      ],
      bus: [
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← dc-pjm · 350 MW × 4hr/day commitment accepted · 12-month term',
          payload: {
            request_id: 'req-pjm-dom-struct-0001',
            facility_id: 'dc-pjm',
            accepted_mw: 350,
            structural_commitment: true,
            term_months: 12,
            settlement_basis: 'telemetry-verified',
          },
        },
        {
          type: 'FlexibilityEnvelope',
          direction: 'compute->grid',
          summary: 'envelope ← dc-pjm · 350 MW down · 240 min · structural · daily window 16:00-20:00 ET',
          payload: {
            facility_id: 'dc-pjm',
            ba: 'PJM',
            band_type: 'structural',
            bands: [
              { direction: 'decrease', mw: 350, for_min: 240, workload_class: 'training', cost_per_mwh: 95, constraint_notes: 'daily 16:00-20:00 ET window · 12-month commitment' },
            ],
          },
        },
      ],
      nodes: {
        'dc-pjm': { status: 'warning', load: 78, lmp: 62 },
      },
      edges: {
        'pjm-critical': { label: '350 MW · structural commitment', status: 'active', mw: 350 },
      },
      metrics: {
        overloadAvoided: 350,
        settlementUsd: totalSettlement(NOVA_DC_COMMIT),
        tonsCo2Avoided: totalTonsCo2(NOVA_DC_COMMIT),
      },
      gated: true,
      gateLabel: 'Now engage the Mid-Atlantic Virtual Power Plant',
      gateSublabel: '130 MW from PA/MD/VA homes · $110/MWh · 4-hr peak window · combined with DC commitment frees 480 MW for residential margin',
      flash: {
        icon: '▶',
        tone: 'action',
        title: 'STRUCTURAL FLEX COMMITMENT',
        lines: [
          'DC-PJM commits 350 MW × 4-hr/day curtailability for 12 months',
          'Telemetry-settled · earns interconnection-queue priority',
        ],
      },
    },
    {
      delayMs: 2800,
      label: 'VPP + DC Together · Residential Margin Restored',
      headline: 'Mid-Atlantic VPP dispatches 130 MW; combined 480 MW of residential-protective headroom in Dominion zone.',
      subhead:
        'Same FlexibilityEnvelope schema as Texas + California scenarios — different region, different cadence (structural rather than emergency), same protocol.',
      story: 'route',
      decision: [
        '130 MW dispatched from 18K Mid-Atlantic homes @ $110/MWh during 4-hr peak window.',
        'Combined with DC commitment: 480 MW residential margin freed without grid expansion delay.',
      ],
      logs: [
        { level: 'info', message: 'VPP swarm (Mid-Atlantic): 16,840 of 18,200 homes responded. 130 MW injected into PJM/DOM grid.' },
        { level: 'success', message: 'Dominion zone residential margin restored. NoVA hospitals + critical infra hold nominal.' },
      ],
      bus: [
        {
          type: 'DispatchRequest',
          direction: 'grid->compute',
          summary: 'request → vpp-pool/PJM · -130 MW · 240 min · $110/MWh · economic',
          payload: {
            request_id: 'req-pjm-dom-vpp-0002',
            ba: 'PJM',
            facility_id: 'vpp-pool/MidAtlantic',
            needed_mw: -130,
            duration_min: 240,
            compensation_per_mwh: 110,
            priority: 'economic',
            reason: 'Daily peak shaving · residential rate protection',
          },
        },
        {
          type: 'DispatchAck',
          direction: 'compute->grid',
          summary: 'ack ← vpp-pool/MidAtlantic · 16,840/18,200 homes · 130 MW · effective +6s',
          payload: { facility_id: 'vpp-pool/MidAtlantic', accepted_mw: 130, participating_assets: 16840 },
        },
        {
          type: 'TelemetryFrame',
          direction: 'compute->grid',
          summary: 'telemetry · vpp-pool/MidAtlantic · 128.4 MW · pf 1.00 · 0 SOC-floor breaches',
          payload: { facility_id: 'vpp-pool/MidAtlantic', actual_mw: 128.4 },
        },
      ],
      nodes: {
        vpp: { status: 'active', load: 78 },
        'dc-pjm': { status: 'stable', load: 78 },
        critical: { status: 'stable', load: 100 },
      },
      edges: {
        'vpp-pjm': { label: '130 MW · Mid-Atlantic VPP', status: 'active', mw: 130 },
        'pjm-critical': { label: 'Protected', status: 'active' },
      },
      metrics: {
        reserveDispatched: 130,
        criticalLoadProtected: 7600000,
        settlementUsd: totalSettlement(NOVA_DC_COMMIT, NOVA_VPP_DISPATCH),
        tonsCo2Avoided: totalTonsCo2(NOVA_DC_COMMIT, NOVA_VPP_DISPATCH),
      },
      flash: {
        icon: '✓',
        tone: 'resolved',
        title: 'MID-ATLANTIC VPP ENGAGED',
        lines: [
          '+130 MW from 18K PA/MD/VA homes (local injection)',
          'Combined 480 MW residential margin · NoVA hospitals nominal',
        ],
      },
    },
    {
      delayMs: 4400,
      label: 'Settled · Residential Bills Held · Queue Approved',
      headline: 'Dominion approves the next 800 MW of DC interconnection. Residential rate-case stays flat.',
      subhead:
        'This is the protocol\'s strategic value — not just emergency response. Hyperscalers earn queue priority by committing verifiable flexibility; residential ratepayers don\'t absorb the buildout cost.',
      story: 'protect',
      decision: [
        'Dominion files updated rate case: residential bills held flat (vs +$11/mo if no flex commitment).',
        '800 MW of new DC capacity approved for connection · contingent on flex commitments.',
      ],
      logs: [
        { level: 'success', message: 'Dominion zone: residential rate increase avoided. Hyperscaler queue clears.' },
      ],
      bus: [
        {
          type: 'GridStateUpdate',
          direction: 'grid->compute',
          summary: 'PJM/DOM · structural margin restored · residential rate-case flat · 800 MW DC approved',
          payload: {
            ba: 'PJM',
            zone: 'DOM',
            stress_score: 0.18,
            new_dc_capacity_approved_mw: 800,
            residential_rate_change_dollars_mo: 0,
          },
        },
      ],
      nodes: {
        'dc-pjm': { status: 'stable', load: 78 },
        vpp: { status: 'active', load: 32 },
      },
      edges: {},
      metrics: {},
      flash: {
        icon: '⚡',
        tone: 'settled',
        title: 'RESIDENTIAL BILLS HELD · QUEUE APPROVED',
        lines: [
          'Dominion approves 800 MW new DC capacity · contingent on flex',
          'Residential rate change: $0/mo (vs +$11 without protocol)',
        ],
      },
    },
  ],
};

export const SCENARIOS: Scenario[] = [
  ercotHeatWaveScenario,
  wildfireCaisoScenario,
  duckCurveScenario,
  novaCrowdOutScenario,
];

export function nowTime() {
  return new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}
