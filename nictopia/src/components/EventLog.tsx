import type { LogEntry } from '../types';

interface EventLogProps {
  entries: LogEntry[];
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function EventLog({ entries, collapsed, onToggleCollapse }: EventLogProps) {
  return (
    <section
      className="panel event-log"
      aria-label="Event log"
      data-collapsed={collapsed ? 'true' : undefined}
    >
      <h2
        className={onToggleCollapse ? 'panel-toggle' : ''}
        onClick={onToggleCollapse}
        role={onToggleCollapse ? 'button' : undefined}
      >
        {onToggleCollapse && <span className="chevron">{collapsed ? '▸' : '▾'}</span>}
        Event Log
      </h2>
      <div className="log-list">
        {entries.map((entry) => (
          <article className={`log-entry log-${entry.level}`} key={entry.id}>
            <time>{entry.ts}</time>
            <span>{entry.message}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
