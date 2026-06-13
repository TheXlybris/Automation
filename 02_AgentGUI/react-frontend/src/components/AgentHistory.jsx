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

export default function AgentHistory({ socket }) {
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

  return (
    <div className="history-sidebar">
      <button
        onClick={() => setOpen(!open)}
        className="history-toggle"
        title={open ? 'Ocultar histórico' : 'Ver histórico de tarefas'}
      >
        <span className="text-sm">{open ? '✕' : '☰'}</span>
        <span className="text-[10px] font-mono">{open ? 'FECHAR' : 'HISTÓRICO'}</span>
      </button>

      {open && (
        <div className="history-panel">
          <div className="history-header">
            <h3 className="text-xs font-mono uppercase tracking-wider" style={{ color:'var(--cyber-blue)' }}>
              Histórico de Tarefas
            </h3>
            <span className="text-[10px] text-[var(--text-dim)]">
              {history.filter(h=>h.status==='running').length} a correr
            </span>
          </div>

          <div className="history-list">
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
                  className="history-item"
                  style={{
                    borderLeftColor: meta.color,
                    background: meta.bg,
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
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
                    <span className="w-1 h-1 rounded-full animate-pulse"
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
