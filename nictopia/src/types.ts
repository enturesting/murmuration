export type NodeStatus = 'idle' | 'warning' | 'overload' | 'active' | 'stable' | 'offline';
export type LogLevel = 'info' | 'warning' | 'critical' | 'success';
export type ISO = 'CAISO' | 'ERCOT' | 'PJM' | 'MISO' | 'NYISO' | 'ISO-NE' | 'SPP';

export type NodeId = 'dc-caiso' | 'dc-ercot' | 'dc-pjm' | 'vpp' | 'critical';

export interface GridNode {
  id: NodeId;
  label: string;
  nodeType: string;
  ba?: ISO;
  status: NodeStatus;
  load: number;
  lmp?: number;
  envelopeMw?: number;
}

export interface GridEdge {
  id: string;
  from: NodeId;
  to: NodeId;
  label: string;
  status: 'standby' | 'active' | 'warning';
  mw?: number;
}

export interface Metrics {
  overloadAvoided: number;
  reserveDispatched: number;
  criticalLoadProtected: number;
  settlementUsd: number;
  tonsCo2Avoided: number;
}

export interface LogEntry {
  id: number;
  ts: string;
  message: string;
  level: LogLevel;
}

export type BusMessageType =
  | 'GridStateUpdate'
  | 'GridForecast'
  | 'FlexibilityEnvelope'
  | 'DispatchRequest'
  | 'DispatchAck'
  | 'TelemetryFrame'
  | 'ContingencyAlert';

export type BusDirection = 'grid->compute' | 'compute->grid';

export interface BusMessage {
  id: number;
  ts: string;
  type: BusMessageType;
  direction: BusDirection;
  summary: string;
  payload: Record<string, unknown>;
}

export interface Phase {
  delayMs: number;
  label: string;
  headline: string;
  subhead: string;
  story: 'need' | 'source' | 'route' | 'protect';
  decision: string[];
  logs: Omit<LogEntry, 'id' | 'ts'>[];
  bus: Omit<BusMessage, 'id' | 'ts'>[];
  nodes: Partial<Record<NodeId, Partial<GridNode>>>;
  edges: Partial<Record<string, Partial<GridEdge>>>;
  metrics: Partial<Metrics>;
  /** When true, scenario engine pauses AFTER applying this phase until user clicks the resume button. */
  gated?: boolean;
  /** Big-button label shown when paused at this phase. Defaults to "Continue →". */
  gateLabel?: string;
  /** Optional small line under the resume button. */
  gateSublabel?: string;
  /** When set, a 1.5-sec flash overlay appears center-screen showing what just happened in plain English. */
  flash?: {
    icon: '🚨' | '▶' | '✓' | '⚡';
    tone: 'stress' | 'action' | 'resolved' | 'settled';
    title: string;        // big, ALL CAPS
    lines: string[];      // 1-3 short descriptive lines underneath
  };
}

export interface ScenarioAnchor {
  incident: string;
  date: string;
  sourceUrl: string;
  realFact: string;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  anchor?: ScenarioAnchor;
  phases: Phase[];
}
