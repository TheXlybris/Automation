import { useState, useEffect } from 'react';

const PROFILE_META = {
  developer:  { label:'Dev',     color:'#00d4ff', bg:'rgba(0,212,255,0.08)', border:'rgba(0,212,255,0.3)' },
  multimedia: { label:'MM',      color:'#ff7b00', bg:'rgba(255,123,0,0.08)', border:'rgba(255,123,0,0.3)' },
  researcher: { label:'Res',     color:'#00ff41', bg:'rgba(0,255,65,0.08)',  border:'rgba(0,255,65,0.3)' },
  wiki:       { label:'Wiki',    color:'#ffb800', bg:'rgba(255,184,0,0.08)', border:'rgba(255,184,0,0.3)' },
};

const DEFAULT_HISTORY = [
  { id:'1', profile:'developer',  task:'Debug server.py crash on launch',            status:'completed', time:'2026-06-11 14:32' },
  { id:'2', profile:'multimedia', task:'Generate fantasy landscape images',            status:'running',   time:'2026-06-11 15:01' },
  { id:'3', profile:'researcher', task:'Find best LoRA for SDXL fantasy style',        status:'completed', time:'2026-06-11 13:45' },
];

export default function AgentHistory({ socket, compact = false }) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState(DEFAULT_HISTORY);

  useEffect(() => {
    if (!socket) return;

    const onAgentLaunched = (data) => {
      setHistory(prev => [
        {
          id: data.id,
          profile: data.profile,
          task: data.goal || data.task || 'New agent',
          status: 'running',
          time: new Date().toLocaleString('sv-SE', { hour12:false }).replace('T',' ').slice(0,16)
        },
        ...prev
      ]);
    };

    const onAgentKilled = (data) => {
      setHistory(prev => prev.map(h =>
        h.id === data.agent_id ? { ...h, status: 'completed' } : h
      ));
    };

    const onAgentError = (data) => {
      setHistory(prev => prev.map(h =>
        h.id === data.agent_id ? { ...h, status: 'error' } : h
      ));
    };

    socket.on('agent_launched', onAgentLaunched);
    socket.on('agent_killed', onAgentKilled);
    socket.on('agent_error', onAgentError);

    return () => {
      socket.off('agent_launched', onAgentLaunched);
      socket.off('agent_killed', onAgentKilled);
      socket.off('agent_error', onAgentError);
    };
  }, [socket]);

  const runningCount = history.filter(h => h.status === 'running').length;

  return (
    <div className="relative">
      {/* Toggle button */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all duration-200 text-left ${
          open
            ? 'bg-[var(--bg-card)] text-[var(--amber-warn)] border border-[var(--border-active)]'
            : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
        }`}
        title="Historico de Tarefas"
      >
        <span className="text-xl flex-shrink-0 w-6 text-center relative">
          {'\u25A0'}
          {runningCount > 0 && (
            <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[var(--matrix-green)] animate-pulse" />
          )}
        </span>
        {!compact && (
          <span className="text-[11px] font-mono font-bold tracking-wider whitespace-nowrap">
            HISTORICO
          </span>
        )}
      </button>

      {/* History panel */}
      {open && (
        <div
          className={`absolute z-50 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl shadow-2xl overflow-hidden ${
            compact ? 'left-14 bottom-0 w-72 max-h-[500px]' : 'left-0 bottom-12 w-72 max-h-[500px]'
          }`}
          style={{ boxShadow: '0 0 40px rgba(0,0,0,0.6)' }}
        >
          <div className="p-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
            <h3 className="text-[11px] font-mono font-bold tracking-wider text-[var(--cyber-blue)] uppercase">
              Historico
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-[var(--text-dim)]">
                {runningCount} a correr
              </span>
              <button
                onClick={() => setOpen(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs px-1"
              >
                {'\u2715'}
              </button>
            </div>
          </div>

          <div className="overflow-y-auto p-2 flex flex-col gap-2 max-h-[440px]">
            {history.length === 0 && (
              <div className="text-center text-[var(--text-dim)] text-[10px] py-8">
                Sem tarefas registadas.
              </div>
            )}
            {history.map(h => {
              const meta = PROFILE_META[h.profile] || PROFILE_META.developer;
              const statusColor = h.status === 'running' ? 'var(--matrix-green)'
                : h.status === 'error' ? 'var(--alert-red)'
                : 'var(--cyber-blue)';

              return (
                <div
                  key={h.id}
                  className="rounded-lg p-2.5 transition-colors hover:bg-[rgba(255,255,255,0.03)]"
                  style={{
                    borderLeft: `2px solid ${meta.color}`,
                    background: meta.bg,
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
                      style={{
                        color: meta.color,
                        border: `1px solid ${meta.border}`,
                        background: meta.bg,
                      }}
                    >
                      {meta.label}
                    </span>
                    <span className="text-[9px] font-mono text-[var(--text-muted)]">
                      {h.time}
                    </span>
                  </div>
                  <div className="text-[11px] text-[var(--text-primary)] leading-snug mb-1">
                    {h.task}
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full animate-pulse"
                      style={{ background: statusColor }}
                    />
                    <span className="text-[9px] font-mono uppercase" style={{ color: statusColor }}>
                      {h.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
