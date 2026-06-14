import { useState } from 'react';

const DEFAULT_AGENTS = [
  { id:'dev',  name:'Developer',     emoji:'💻', desc:'Coding, debugging, infra',        color:'#00d4ff', status:'Standby' },
  { id:'mm',   name:'Multimedia',    emoji:'🎨', desc:'Images, video, audio, ComfyUI',   color:'#ff7b00', status:'Standby' },
  { id:'res',  name:'Researcher',    emoji:'🔬', desc:'Web research, papers, synthesis', color:'#00ff41', status:'Standby' },
  { id:'wiki', name:'Wiki Curator',  emoji:'📚', desc:'Obsidian, LLM Wiki, memory',     color:'#ffb800', status:'Standby' },
];

export default function AgentPanel({ socket }) {
  const [agents] = useState(DEFAULT_AGENTS);
  const [focused, setFocused] = useState(null);
  const [tasks, setTasks] = useState({});
  const [dispatched, setDispatched] = useState(null);
  const [customCount, setCustomCount] = useState(0);
  const [customAgents, setCustomAgents] = useState([]);

  const allAgents = [...agents, ...customAgents];

  const updateTask = (id, val) => {
    setTasks(prev => ({ ...prev, [id]: val }));
  };

  const dispatchTask = (id) => {
    const txt = (tasks[id] || '').trim();
    if (!txt || !socket) return;
    socket.emit('dispatch_task', { target_profile: id, task: txt });
    setDispatched(id);
    setTasks(prev => ({ ...prev, [id]: '' }));
    setTimeout(() => setDispatched(null), 3000);
  };

  const addCard = () => {
    const n = customCount + 1;
    setCustomCount(n);
    setCustomAgents(a => [...a, {
      id:`custom-${n}`, name:`Custom #${n}`, emoji:'⚙️',
      desc:'User-defined agent', color:'#888', status:'Standby'
    }]);
  };

  const removeCard = (id) => {
    setCustomAgents(a => a.filter(x => x.id !== id));
    if (focused === id) setFocused(null);
  };

  // FULL FOCUS MODE: if focused, only show that card
  if (focused) {
    const ag = allAgents.find(a => a.id === focused);
    if (!ag) { setFocused(null); return null; }

    return (
      <div className="agent-panel agent-panel-full-focus">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-mono uppercase tracking-wider" style={{ color:'var(--cyber-blue)' }}>
            {ag.name}
          </h2>
          <button
            onClick={() => setFocused(null)}
            className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border"
            style={{ background:'var(--bg-hover)', borderColor:'var(--border-subtle)', color: 'var(--text-secondary)' }}
          >
            ← Retroceder
          </button>
        </div>

        <div className="agent-card agent-card-focused-full">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{ag.emoji}</span>
              <h3 className="text-base font-bold font-mono" style={{ color:ag.color }}>{ag.name}</h3>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${ag.status==='Active'?'bg-green-400 animate-pulse':'bg-gray-500'}`} />
              {ag.id.startsWith('custom-') && (
                <button
                  onClick={() => removeCard(ag.id)}
                  className="text-xs text-red-400 hover:text-red-200"
                  title="Remove"
                >×</button>
              )}
            </div>
          </div>

          <p className="text-[11px] text-[var(--text-dim)] leading-tight mb-4">{ag.desc}</p>

          <textarea
            className="agent-input w-full text-[12px] mb-3"
            rows={8}
            placeholder={`Task for ${ag.name}...`}
            value={tasks[ag.id] || ''}
            onChange={e => updateTask(ag.id, e.target.value)}
            onKeyDown={e => {
              if (e.key==='Enter' && e.ctrlKey) {
                e.preventDefault();
                dispatchTask(ag.id);
              }
            }}
          />

          <div className="flex gap-2">
            <button
              onClick={() => dispatchTask(ag.id)}
              disabled={!(tasks[ag.id] || '').trim()}
              className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border"
              style={{
                background: !(tasks[ag.id] || '').trim() ? 'var(--bg-secondary)' : 'var(--bg-card)',
                borderColor: !(tasks[ag.id] || '').trim() ? 'var(--border-subtle)' : 'var(--matrix-green)',
                color: !(tasks[ag.id] || '').trim() ? 'var(--text-muted)' : 'var(--matrix-green)',
                cursor: !(tasks[ag.id] || '').trim() ? 'not-allowed' : 'pointer',
                opacity: !(tasks[ag.id] || '').trim() ? 0.5 : 1,
              }}
            >
              {dispatched===ag.id ? '✓ Dispatched!' : 'Dispatch'}
            </button>
            <button
              onClick={() => setFocused(null)}
              className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border"
              style={{ background:'var(--bg-hover)', borderColor:'var(--border-subtle)', color: 'var(--text-secondary)' }}
            >
              ←
            </button>
          </div>
          <span className="text-[9px] text-[var(--text-dim)] mt-2 block">
            Ctrl+Enter para enviar
          </span>
        </div>
      </div>
    );
  }

  // GRID MODE: all cards visible
  return (
    <div className="agent-panel">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono uppercase tracking-wider" style={{ color:'var(--cyber-blue)' }}>
          Agent Profiles
        </h2>
        <button 
          onClick={addCard} 
          className="btn-glow px-3 py-1.5 rounded-lg text-xs font-mono border"
          style={{ 
            background: 'var(--bg-card)', 
            borderColor: 'var(--border-active)', 
            color: 'var(--cyber-blue)',
          }}
        >
          + New Card
        </button>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {allAgents.map((ag) => (
          <div
            key={ag.id}
            onClick={() => setFocused(ag.id)}
            className="agent-card"
            style={{ cursor:'pointer' }}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">{ag.emoji}</span>
                <h3 className="text-sm font-bold font-mono" style={{ color:ag.color }}>{ag.name}</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${ag.status==='Active'?'bg-green-400 animate-pulse':'bg-gray-500'}`} />
                {ag.id.startsWith('custom-') && (
                  <button
                    onClick={e => { e.stopPropagation(); removeCard(ag.id); }}
                    className="text-xs text-red-400 hover:text-red-200"
                    title="Remove"
                  >×</button>
                )}
              </div>
            </div>

            <p className="text-[10px] text-[var(--text-dim)] leading-tight mb-3">{ag.desc}</p>

            <div className="text-[9px] text-[var(--text-dim)] text-center">
              Clicar para expandir
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}