import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

const PROFILE_COLORS = {
  developer:   '#00d4ff',
  multimedia:  '#ff7b00',
  researcher:  '#00ff41',
  wiki:        '#ffb800',
  dreamer:     '#c084fc',
  orchestrator:'#888888',
};

const PROFILE_ICONS = {
  developer:   '💻',
  multimedia:  '🎨',
  researcher:  '🔍',
  wiki:        '📚',
  dreamer:     '✨',
  orchestrator:'🧠',
};

// Strip ANSI escape codes
function stripAnsi(str) {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
}

function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function AgentTerminal({ agent, streamData, onClose }) {
  const outputRef = useRef(null);
  const [restOutput, setRestOutput] = useState('');

  // Load initial output via REST
  useEffect(() => {
    let cancelled = false;
    fetch(`${window.location.origin}/api/agents/${agent.id}/output?lines=100`)
      .then(r => r.json())
      .then(data => {
        if (!cancelled) setRestOutput(stripAnsi(data.output || '(sem output)'));
      })
      .catch(() => {
        if (!cancelled) setRestOutput('(erro ao carregar output)');
      });
    return () => { cancelled = true; };
  }, [agent.id]);

  // Derive displayed output: stream takes priority over REST
  const output = useMemo(() => {
    if (streamData) return stripAnsi(streamData.output || '');
    return restOutput;
  }, [streamData, restOutput]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const color = PROFILE_COLORS[agent.profile] || '#888';
  const icon = PROFILE_ICONS[agent.profile] || '🤖';
  const isRunning = agent.status === 'running';

  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col"
      style={{
        borderColor: `${color}40`,
        background: 'var(--bg-card)',
        minHeight: 280,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b"
        style={{ borderColor: `${color}30`, background: `${color}0a` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base flex-shrink-0">{icon}</span>
          <span
            className="text-xs font-mono font-bold tracking-wider flex-shrink-0"
            style={{ color }}
          >
            {agent.profile?.toUpperCase()}
          </span>
          <span className="text-xs font-mono text-slate-500 truncate" title={agent.id}>
            {agent.id}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: isRunning ? '#fbbf24' : agent.status === 'completed' ? '#10b981' : '#ef4444',
              animation: isRunning ? 'pulse 1.5s infinite' : 'none',
            }}
          />
          <span className="text-[10px] font-mono text-slate-400">
            {isRunning ? 'A CORRER' : agent.status === 'completed' ? 'CONCLUÍDO' : agent.status?.toUpperCase()}
          </span>
          {agent.duration && (
            <span className="text-[10px] font-mono text-slate-500">
              {formatDuration(agent.duration)}
            </span>
          )}
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-red-400 text-xs ml-1"
            title="Fechar painel"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Terminal body */}
      <div
        ref={outputRef}
        className="flex-1 overflow-auto bg-black p-3"
        style={{ maxHeight: 320 }}
      >
        {output ? (
          <pre className="text-xs font-mono text-green-400 whitespace-pre-wrap break-all">
            {output}
          </pre>
        ) : (
          <pre className="text-xs font-mono text-slate-500">A carregar...</pre>
        )}
      </div>
    </div>
  );
}

export default function CommandCenter({ socket }) {
  const [agents, setAgents] = useState([]);
  const [streams, setStreams] = useState({});
  const [closedIds, setClosedIds] = useState(new Set());

  // Load initial agents list
  useEffect(() => {
    fetch(`${window.location.origin}/api/agents`)
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data.agents || []);
        setAgents(list);
      })
      .catch(err => console.error('Error loading agents:', err));
  }, []);

  // Listen for agent updates and streams
  useEffect(() => {
    if (!socket) return;

    const onAgentsUpdated = (data) => {
      const list = Array.isArray(data) ? data : (data.agents || []);
      setAgents(list);
    };

    const onTaskDispatched = (data) => {
      // A new task was dispatched — fetch updated agents list immediately
      fetch(`${window.location.origin}/api/agents`)
        .then(r => r.json())
        .then(d => {
          const list = Array.isArray(d) ? d : (d.agents || []);
          setAgents(list);
        })
        .catch(err => console.error('Error fetching agents after dispatch:', err));
    };

    const onAgentStream = (data) => {
      if (data.agent_id) {
        setStreams(prev => ({
          ...prev,
          [data.agent_id]: data,
        }));
      }
    };

    socket.on('agents_updated', onAgentsUpdated);
    socket.on('agents_list', onAgentsUpdated);
    socket.on('connected', onAgentsUpdated);
    socket.on('task_dispatched', onTaskDispatched);
    socket.on('agent_stream', onAgentStream);

    return () => {
      socket.off('agents_updated', onAgentsUpdated);
      socket.off('agents_list', onAgentsUpdated);
      socket.off('connected', onAgentsUpdated);
      socket.off('task_dispatched', onTaskDispatched);
      socket.off('agent_stream', onAgentStream);
    };
  }, [socket]);

  const handleClose = useCallback((agentId) => {
    setClosedIds(prev => new Set([...prev, agentId]));
  }, []);

  // Show all agents except closed ones
  const visibleAgents = agents.filter(a => !closedIds.has(a.id));

  return (
    <div className="command-center">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--cyber-blue)] animate-pulse" />
          <h2 className="text-xs font-mono font-bold tracking-wider text-[var(--cyber-blue)] uppercase">
            Command Center — Live Terminal Feed
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-500">
          {visibleAgents.length} agente(s) visível(is)
        </span>
      </div>

      {/* Grid of terminal panels */}
      {visibleAgents.length === 0 ? (
        <div className="text-center py-20 text-slate-500 font-mono text-sm">
          <div className="mb-4 text-4xl opacity-20">📡</div>
          Nenhum agente ativo. Despacha uma tarefa para ver o output em tempo real.
        </div>
      ) : (
        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
          }}
        >
          {visibleAgents.map(agent => (
            <AgentTerminal
              key={agent.id}
              agent={agent}
              streamData={streams[agent.id]}
              onClose={() => handleClose(agent.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}