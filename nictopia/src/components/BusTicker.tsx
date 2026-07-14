import { useEffect, useRef } from 'react';
import type { BusMessage, BusMessageType } from '../types';

interface Props {
  messages: BusMessage[];
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const TYPE_CLASS: Record<BusMessageType, string> = {
  GridStateUpdate: 'bus-state',
  GridForecast: 'bus-forecast',
  FlexibilityEnvelope: 'bus-envelope',
  DispatchRequest: 'bus-request',
  DispatchAck: 'bus-ack',
  TelemetryFrame: 'bus-telemetry',
  ContingencyAlert: 'bus-contingency',
};

const TYPE_LABEL: Record<BusMessageType, string> = {
  GridStateUpdate: 'GRID STATE',
  GridForecast: 'FORECAST',
  FlexibilityEnvelope: 'ENVELOPE',
  DispatchRequest: 'DISPATCH REQ',
  DispatchAck: 'DISPATCH ACK',
  TelemetryFrame: 'TELEMETRY',
  ContingencyAlert: 'CONTINGENCY',
};

export function BusTicker({ messages, collapsed, onToggleCollapse }: Props) {
  const listRef = useRef<HTMLDivElement>(null);
  const recent = messages.slice(-40).reverse();

  useEffect(() => {
    listRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [messages.length]);

  return (
    <section
      className="panel bus-ticker"
      aria-label="Murmuration Bus"
      data-collapsed={collapsed ? 'true' : undefined}
    >
      <div
        className={`bus-head ${onToggleCollapse ? 'panel-toggle' : ''}`}
        onClick={onToggleCollapse}
        role={onToggleCollapse ? 'button' : undefined}
      >
        <h2>
          {onToggleCollapse && <span className="chevron">{collapsed ? '▸' : '▾'}</span>}
          Murmuration Bus
        </h2>
        <span className="bus-cadence">live · pub/sub</span>
      </div>
      <div className="bus-list" ref={listRef}>
        {recent.map((m) => {
          const anchor =
            m.payload && typeof m.payload === 'object' && '_anchor' in m.payload
              ? String((m.payload as Record<string, unknown>)._anchor)
              : null;
          return (
            <article key={m.id} className={`bus-msg ${TYPE_CLASS[m.type]}`}>
              <header>
                <span className="bus-type">{TYPE_LABEL[m.type]}</span>
                {anchor && <span className="bus-real" title={anchor}>REAL</span>}
                <span className="bus-dir">
                  {m.direction === 'grid->compute' ? 'grid → compute' : 'compute → grid'}
                </span>
                <time>{m.ts}</time>
              </header>
              <div className="bus-summary">{m.summary}</div>
              {anchor && <div className="bus-anchor">↳ {anchor}</div>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
