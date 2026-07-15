import { useState, useEffect, useRef } from 'react';
import SettingsModal from './SettingsModal';

const DEFAULT_AGENTS = [
  { id:'developer',   name:'Developer',     emoji:'💻', desc:'Coding, debugging, infra',        color:'#00d4ff', status:'Standby' },
  { id:'multimedia',  name:'Multimedia',    emoji:'🎨', desc:'Images, video, audio, ComfyUI',   color:'#ff7b00', status:'Standby' },
  { id:'researcher',  name:'Researcher',    emoji:'🔬', desc:'Web research, papers, synthesis', color:'#00ff41', status:'Standby' },
  { id:'wiki',        name:'Wiki Curator',  emoji:'📚', desc:'Obsidian, LLM Wiki, memory',     color:'#ffb800', status:'Standby' },
  { id:'dreamer',     name:'Dreamer',       emoji:'🌙', desc:'Self-improvement, audits, wiki lint, skill gaps', color:'#c084fc', status:'Standby' },
];

const STORAGE_KEY = (id) => `agent_model_${id}`;
const DREAM_TIMEOUT_SEC = 45; // assume failure if no progress change in 45s

// ─── ConversationLog component ──────────────────────
function ConversationLog({ profileId, logs, status, onClear, logEndRef }) {
  useEffect(() => {
    if (logEndRef.current) logEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="mt-3 mb-3">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>Conversa</span>
          {status === 'running' && (
            <span className="flex items-center gap-1 text-[9px] font-mono" style={{ color: 'var(--matrix-green)' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--matrix-green)] animate-pulse" />
              a processar...
            </span>
          )}
          {status === 'completed' && (
            <span className="text-[9px] font-mono" style={{ color: 'var(--matrix-green)' }}>concluido</span>
          )}
          {status === 'error' && (
            <span className="text-[9px] font-mono" style={{ color: 'var(--alert-red)' }}>erro</span>
          )}
        </div>
        {logs.length > 0 && (
          <button onClick={onClear} className="text-[9px] font-mono px-2 py-0.5 rounded border hover:bg-[var(--bg-hover)]" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }} title="Limpar conversa">Limpar</button>
        )}
      </div>
      {logs.length > 0 ? (
        <div className="rounded-lg border overflow-auto" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)', maxHeight: '400px' }}>
          {logs.map((entry, i) => (
            <div key={i} className="px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
              {entry.role === 'user' ? (
                <div>
                  <span className="text-[9px] font-mono font-bold" style={{ color: 'var(--cyber-blue)' }}>USER</span>
                  <span className="text-[9px] font-mono ml-2" style={{ color: 'var(--text-dim)' }}>{new Date(entry.ts).toLocaleTimeString()}</span>
                  <pre className="text-[11px] font-mono mt-1 whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>{entry.text}</pre>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono font-bold" style={{ color: entry.is_final ? 'var(--matrix-green)' : 'var(--amber-warn)' }}>AGENT</span>
                    <span className="text-[9px] font-mono" style={{ color: 'var(--text-dim)' }}>{new Date(entry.ts).toLocaleTimeString()}</span>
                    {entry.is_final && <span className="text-[8px] font-mono" style={{ color: 'var(--matrix-green)' }}>final</span>}
                  </div>
                  <pre className="text-[10px] font-mono mt-1 whitespace-pre-wrap overflow-auto" style={{ color: 'var(--text-primary)', maxHeight: '300px' }}>{entry.text}</pre>
                </div>
              )}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      ) : (
        <div className="rounded-lg border flex items-center justify-center text-[10px] font-mono" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-dim)', height: '60px' }}>
          Sem conversa. Envia uma tarefa para comecar.
        </div>
      )}
    </div>
  );
}

export default function AgentPanel({ socket }) {
  const [agents] = useState(DEFAULT_AGENTS);
  const [focused, setFocused] = useState(null);
  const [tasks, setTasks] = useState({});
  const [dispatched, setDispatched] = useState(null);
  const [customCount, setCustomCount] = useState(0);
  const [customAgents, setCustomAgents] = useState([]);
  const [curating, setCurating] = useState(false);
  const [curateProgress, setCurateProgress] = useState(0);
  const [curateMessage, setCurateMessage] = useState('');
  const [curateResults, setCurateResults] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(null);
  const [modelsList, setModelsList] = useState([]);

  // Agent conversation logs — keyed by profile id. Each entry: { role, text, ts, agent_id }
  // Persisted in component state (survives tab switches since App.jsx keeps all tabs mounted).
  const [agentLogs, setAgentLogs] = useState({});  // { researcher: [{role, text, ts, agent_id}], ... }
  const [agentStatus, setAgentStatus] = useState({});  // { researcher: 'running', ... }
  const logEndRef = useRef(null);

  // jcode-specific state (developer profile)
  const [useJcode, setUseJcode] = useState(() => {
    try { return localStorage.getItem('dev_use_jcode') === 'true'; } catch { return false; }
  }); // false = auto (classifier decides); true = force jcode
  const [jcodeRepo, setJcodeRepo] = useState(() => {
    try { return localStorage.getItem('dev_jcode_repo') || '/media/sf_AI_Ecosystem/10_Projects/'; } catch { return '/media/sf_AI_Ecosystem/10_Projects/'; }
  });
  const [jcodeToolProfile, setJcodeToolProfile] = useState(() => {
    try { return localStorage.getItem('dev_jcode_tool_profile') || 'minimal'; } catch { return 'minimal'; }
  });
  const [jcodeRepos, setJcodeRepos] = useState([]);
  const [jcodeRunId, setJcodeRunId] = useState(null);
  const [jcodeStatus, setJcodeStatus] = useState('idle'); // idle running completed error cancelled
  const [jcodeOutput, setJcodeOutput] = useState('');
  const [jcodeHistory, setJcodeHistory] = useState([]);
  const jcodePollRef = useRef(null);

  // Dreamer-specific state
  const [dreaming, setDreaming] = useState(false);
  const [dreamProgress, setDreamProgress] = useState(0);
  const [dreamMessage, setDreamMessage] = useState('');
  const [dreamResult, setDreamResult] = useState(null);
  const [dreamError, setDreamError] = useState(null); // {message, timestamp}
  const [dreamNotes, setDreamNotes] = useState(''); // user notes for dream/fix context
  const [lastReport, setLastReport] = useState(null);
  const [fixMode, setFixMode] = useState(false);

  // Timeout tracking refs
  const lastProgressRef = useRef(0);
  const lastProgressTimeRef = useRef(0);
  const pollRef = useRef(null);

  const allAgents = [...agents, ...customAgents];

  const getSavedModel = (id) => {
    try { return localStorage.getItem(STORAGE_KEY(id)) || ''; } catch { return ''; }
  };

  useEffect(() => {
    if (!socket) return;
    const onStarted = () => { setCurating(true); setCurateProgress(0); setCurateMessage('Iniciando curadoria...'); setCurateResults(null); };
    const onProgress = (data) => { setCurateProgress(data.percent || 0); setCurateMessage(data.message || ''); };
    const onComplete = (data) => { setCurating(false); setCurateProgress(100); setCurateMessage('Curadoria concluida!'); setCurateResults(data.results || []); };
    const onError = (data) => { setCurating(false); setCurateMessage(`Erro: ${data.message || 'Unknown'}`); };
    // jcode stream listener
    const onJcodeStream = (data) => {
      if (!data || !data.chunk) return;
      setJcodeOutput(prev => (prev + data.chunk).slice(-20000));
    };
    const onTaskDispatched = (data) => {
      if (data.jcode_run_id) {
        startJcodePolling(data.jcode_run_id);
      }
    };
    socket.on('wiki_curate_started', onStarted);
    socket.on('wiki_curate_progress', onProgress);
    socket.on('wiki_curate_complete', onComplete);
    socket.on('wiki_curate_error', onError);
    socket.on('jcode_stream', onJcodeStream);
    socket.on('task_dispatched', onTaskDispatched);

    // ─── Live agent output streaming ───
    const onAgentStream = (data) => {
      if (!data || !data.agent_id || !data.profile) return;
      const profile = data.profile;
      setAgentStatus(prev => ({ ...prev, [profile]: data.status || 'running' }));
      // Append stream chunk to the agent's log
      setAgentLogs(prev => {
        const logs = prev[profile] || [];
        // If the last entry is a stream from the same agent_id, append to it
        const last = logs[logs.length - 1];
        if (last && last.role === 'agent' && last.agent_id === data.agent_id && !last.is_final) {
          const updated = [...logs];
          updated[updated.length - 1] = { ...last, text: data.output || '', ts: data.timestamp || new Date().toISOString() };
          return { ...prev, [profile]: updated };
        }
        // Otherwise create a new entry
        return { ...prev, [profile]: [...logs, { role: 'agent', text: data.output || '', ts: data.timestamp || new Date().toISOString(), agent_id: data.agent_id, is_final: !!data.is_final }] };
      });
    };
    const onAgentCompleted = (data) => {
      if (!data || !data.agent_id) return;
      const profile = data.profile || data.agent_id.split('_')[0];
      setAgentStatus(prev => ({ ...prev, [profile]: data.status || 'completed' }));
    };
    socket.on('agent_stream', onAgentStream);
    socket.on('agent_completed', onAgentCompleted);

    return () => {
      socket.off('wiki_curate_started', onStarted);
      socket.off('wiki_curate_progress', onProgress);
      socket.off('wiki_curate_complete', onComplete);
      socket.off('wiki_curate_error', onError);
      socket.off('jcode_stream', onJcodeStream);
      socket.off('task_dispatched', onTaskDispatched);
      socket.off('agent_stream', onAgentStream);
      socket.off('agent_completed', onAgentCompleted);
    };
  }, [socket]);

  useEffect(() => {
    fetch(`${window.location.origin}/api/models`)
      .then(r => r.json())
      .then(d => setModelsList(d.models || []))
      .catch(() => {});
  }, []);

  // Fetch last Dreamer report on mount
  useEffect(() => {
    refreshLastReport();
  }, []);

  // Fetch jcode repos on mount
  useEffect(() => {
    fetch(`${window.location.origin}/api/jcode/repos`)
      .then(r => r.json())
      .then(d => setJcodeRepos(d.repos || []))
      .catch(() => {});
  }, []);

  // Load jcode history on mount
  useEffect(() => {
    fetch(`${window.location.origin}/api/jcode/runs`)
      .then(r => r.json())
      .then(d => {
        const runs = Array.isArray(d) ? d : [];
        setJcodeHistory(runs.filter(r => r.agent_id && r.agent_id.startsWith('dev_')).slice(0, 20));
      })
      .catch(() => {});
  }, []);

  const refreshLastReport = () => {
    fetch(`${window.location.origin}/api/dream/last-report`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && d.exists !== false) setLastReport(d); })
      .catch(() => {});
  };

  const getModelDisplay = (modelId) => {
    if (!modelId) return '';
    const m = modelsList.find(x => x.id === modelId);
    if (m) return m.name;
    return modelId.replace(/:.*$/, '');
  };

  const updateTask = (id, val) => setTasks(prev => ({ ...prev, [id]: val }));

  const dispatchTask = (id) => {
    const txt = (tasks[id] || '').trim();
    if (!txt || !socket) return;
    const model = getSavedModel(id);
    const payload = { target_profile: id, task: txt };
    if (model) payload.model = model;
    if (id === 'developer' && useJcode) {
      payload.use_jcode = true;
      payload.repo_path = jcodeRepo;
      payload.tool_profile = jcodeToolProfile;
      payload.timeout = 600;
      setJcodeOutput('');
      setJcodeStatus('running');
    }
    socket.emit('dispatch_task', payload);
    setDispatched(id);
    // Add user task to the agent's conversation log
    setAgentLogs(prev => {
      const logs = prev[id] || [];
      return { ...prev, [id]: [...logs, { role: 'user', text: txt, ts: new Date().toISOString() }] };
    });
    setAgentStatus(prev => ({ ...prev, [id]: 'running' }));
    setTasks(prev => ({ ...prev, [id]: '' }));
    setTimeout(() => setDispatched(null), 3000);
  };

  const clearAgentLog = (id) => setAgentLogs(prev => ({ ...prev, [id]: [] }));

  const toggleJcode = () => {
    const next = !useJcode;
    setUseJcode(next);
    try { localStorage.setItem('dev_use_jcode', String(next)); } catch {}
  };

  const handleJcodeRepoChange = (e) => {
    const val = e.target.value;
    setJcodeRepo(val);
    try { localStorage.setItem('dev_jcode_repo', val); } catch {}
  };

  const handleJcodeToolChange = (e) => {
    const val = e.target.value;
    setJcodeToolProfile(val);
    try { localStorage.setItem('dev_jcode_tool_profile', val); } catch {}
  };

  const killJcodeRun = async () => {
    if (!jcodeRunId) return;
    await fetch(`${window.location.origin}/api/jcode/${jcodeRunId}/kill`, { method: 'POST' });
    setJcodeStatus('cancelled');
    if (jcodePollRef.current) clearInterval(jcodePollRef.current);
  };

  const startJcodePolling = (runId) => {
    setJcodeRunId(runId);
    if (jcodePollRef.current) clearInterval(jcodePollRef.current);
    jcodePollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${window.location.origin}/api/jcode/${runId}`);
        if (!r.ok) return;
        const d = await r.json();
        setJcodeStatus(d.status || 'running');
        if (d.status && d.status !== 'running' && d.status !== 'pending') {
          clearInterval(jcodePollRef.current);
          jcodePollRef.current = null;
        }
      } catch {}
    }, 1500);
  };

  // ─── Dreamer-specific functions ───

  const clearDreamError = () => setDreamError(null);

  const startDream = async () => {
    if (dreaming) return;
    setDreaming(true);
    setFixMode(false);
    setDreamProgress(0);
    setDreamMessage('A iniciar ciclo de sonho...');
    setDreamResult(null);
    setDreamError(null);
    lastProgressRef.current = 0;
    lastProgressTimeRef.current = Date.now();
    try {
      const body = dreamNotes.trim() ? JSON.stringify({ notes: dreamNotes.trim() }) : '{}';
      const r = await fetch(`${window.location.origin}/api/dream/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
      const data = await r.json();
      if (data.error) {
        const errMsg = `Erro: ${data.error}`;
        setDreamMessage(errMsg);
        setDreaming(false);
        setDreamError({ message: data.error, timestamp: new Date().toISOString() });
        return;
      }
      const agentId = data.id;
      pollRef.current = setInterval(async () => {
        try {
          const pr = await fetch(`${window.location.origin}/api/agents/${agentId}/progress`);
          if (pr.ok) {
            const pd = await pr.json();
            const pct = pd.pct || pd.percent || 0;
            const msg = pd.msg || pd.message || '';
            setDreamProgress(pct);
            setDreamMessage(msg);

            // Track progress for timeout detection
            if (pct > lastProgressRef.current) {
              lastProgressRef.current = pct;
              lastProgressTimeRef.current = Date.now();
            }

            if (pd.status === 'error') {
              clearInterval(pollRef.current);
              setDreaming(false);
              const errMsg = pd.error || msg || 'Falhou';
              setDreamMessage(`Erro: ${errMsg}`);
              setDreamError({ message: errMsg, timestamp: new Date().toISOString(), agentId });
              setDreamResult(pd);
            } else if (pct >= 100 || pd.status === 'completed') {
              clearInterval(pollRef.current);
              setDreaming(false);
              setDreamProgress(100);
              setDreamMessage('Ciclo de sonho concluido!');
              setDreamResult(pd);
              setDreamError(null);
              fetch(`${window.location.origin}/api/dream/last-report`)
                .then(r => r.ok ? r.json() : null)
                .then(d => { if (d && d.exists !== false) setLastReport(d); })
                .catch(() => {});
            }

            // Timeout detection: no progress change in DREAM_TIMEOUT_SEC
            if (dreaming && (Date.now() - lastProgressTimeRef.current) > DREAM_TIMEOUT_SEC * 1000) {
              clearInterval(pollRef.current);
              setDreaming(false);
              const errMsg = `Timeout: sem progresso ha ${DREAM_TIMEOUT_SEC}s (parado nos ${lastProgressRef.current}%)`;
              setDreamMessage(`Erro: ${errMsg}`);
              setDreamError({ message: errMsg, timestamp: new Date().toISOString(), agentId });
            }
          }
        } catch { /* poll will retry */ }
      }, 2000);
    } catch (e) {
      clearInterval(pollRef.current);
      setDreaming(false);
      const errMsg = e.message || 'Erro de rede';
      setDreamMessage(`Erro: ${errMsg}`);
      setDreamError({ message: errMsg, timestamp: new Date().toISOString() });
    }
  };

  const startDreamFix = async () => {
    if (dreaming) return;
    setDreaming(true);
    setFixMode(true);
    setDreamProgress(0);
    setDreamMessage('A iniciar correcao automatica...');
    setDreamResult(null);
    setDreamError(null);
    lastProgressRef.current = 0;
    lastProgressTimeRef.current = Date.now();
    try {
      const body = dreamNotes.trim() ? JSON.stringify({ notes: dreamNotes.trim() }) : '{}';
      const r = await fetch(`${window.location.origin}/api/dream/fix`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
      const data = await r.json();
      if (data.error) {
        const errMsg = `Erro: ${data.error}`;
        setDreamMessage(errMsg);
        setDreaming(false);
        setDreamError({ message: data.error, timestamp: new Date().toISOString() });
        return;
      }
      const agentId = data.id;
      pollRef.current = setInterval(async () => {
        try {
          const pr = await fetch(`${window.location.origin}/api/agents/${agentId}/progress`);
          if (pr.ok) {
            const pd = await pr.json();
            const pct = pd.pct || pd.percent || 0;
            const msg = pd.msg || pd.message || '';
            setDreamProgress(pct);
            setDreamMessage(msg);

            if (pct > lastProgressRef.current) {
              lastProgressRef.current = pct;
              lastProgressTimeRef.current = Date.now();
            }

            if (pd.status === 'error') {
              clearInterval(pollRef.current);
              setDreaming(false);
              const errMsg = pd.error || msg || 'Falhou';
              setDreamMessage(`Erro: ${errMsg}`);
              setDreamError({ message: errMsg, timestamp: new Date().toISOString(), agentId });
              setDreamResult(pd);
            } else if (pct >= 100 || pd.status === 'completed') {
              clearInterval(pollRef.current);
              setDreaming(false);
              setDreamProgress(100);
              setDreamMessage('Correcao concluida!');
              setDreamResult(pd);
              setDreamError(null);
            }

            if (dreaming && (Date.now() - lastProgressTimeRef.current) > DREAM_TIMEOUT_SEC * 1000) {
              clearInterval(pollRef.current);
              setDreaming(false);
              const errMsg = `Timeout: sem progresso ha ${DREAM_TIMEOUT_SEC}s (parado nos ${lastProgressRef.current}%)`;
              setDreamMessage(`Erro: ${errMsg}`);
              setDreamError({ message: errMsg, timestamp: new Date().toISOString(), agentId });
            }
          }
        } catch { /* poll will retry */ }
      }, 2000);
    } catch (e) {
      clearInterval(pollRef.current);
      setDreaming(false);
      const errMsg = e.message || 'Erro de rede';
      setDreamMessage(`Erro: ${errMsg}`);
      setDreamError({ message: errMsg, timestamp: new Date().toISOString() });
    }
  };

  const startWikiCuration = () => { if (!socket || curating) return; socket.emit('wiki_curate_start'); };
  const addCard = () => { const n = customCount + 1; setCustomCount(n); setCustomAgents(a => [...a, { id:`custom-${n}`, name:`Custom #${n}`, emoji:'⚙️', desc:'User-defined agent', color:'#888', status:'Standby' }]); };
  const removeCard = (id) => { setCustomAgents(a => a.filter(x => x.id !== id)); if (focused === id) setFocused(null); };
  const handleSaveModel = async (agentId, modelId) => {
    try { localStorage.setItem(STORAGE_KEY(agentId), modelId || ''); } catch {}
    // Persist to backend so runner.py picks it up
    try {
      await fetch(`${window.location.origin}/api/profiles/${agentId}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId || null })
      });
    } catch (e) { /* silent */ }
    setSettingsOpen(null);
  };

  const ProgressBar = ({ percent, message, error, colorStart, colorEnd }) => {
    const barColor = error
      ? 'var(--alert-red)'
      : dreaming
        ? `linear-gradient(90deg, ${colorStart || 'var(--amber-warn)'}, ${colorEnd || 'var(--matrix-green)'})`
        : 'var(--matrix-green)';
    const barShadow = error ? '0 0 8px var(--alert-red)' : dreaming ? `0 0 8px ${colorStart || 'var(--amber-warn)'}` : 'none';
    const statusIcon = error ? '❌' : dreaming ? (fixMode ? '🔧' : '🌙') : dreamResult ? '✅' : '⏸️';
    const statusLabel = error ? 'ERRO' : dreaming ? (fixMode ? 'A corrigir...' : 'A sonhar...') : dreamResult ? 'Concluido' : 'Pronto';
    const pctColor = error ? 'var(--alert-red)' : dreaming ? (colorStart || 'var(--amber-warn)') : 'var(--matrix-green)';

    return (
      <div className="mt-3 p-3 rounded-lg border" style={{ borderColor: error ? 'var(--alert-red)' : 'var(--border-subtle)', background: error ? 'rgba(255,50,50,0.08)' : 'var(--bg-secondary)' }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono" style={{ color: error ? 'var(--alert-red)' : 'var(--text-secondary)' }}>{statusIcon} {statusLabel}</span>
          <span className="text-[10px] font-mono font-bold" style={{ color: pctColor }}>{percent}%</span>
        </div>
        <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
          <div className="h-full rounded-full transition-all duration-500 ease-out" style={{ width: `${percent}%`, background: barColor, boxShadow: barShadow }} />
        </div>
        {message && <p className="text-[9px] font-mono mt-1 truncate" style={{ color: error ? 'var(--alert-red)' : 'var(--text-dim)' }}>{message}</p>}
      </div>
    );
  };

  const ModelBadge = ({ agentId }) => {
    const m = getSavedModel(agentId);
    if (!m) return null;
    return (<span className="model-indicator" title={m}>{getModelDisplay(m)}</span>);
  };

  // ─── Focus Mode ───

  if (focused) {
    const ag = allAgents.find(a => a.id === focused);
    if (!ag) { setFocused(null); return null; }
    const isWiki = ag.id === 'wiki';
    const isDreamer = ag.id === 'dreamer';
    const hasDreamError = isDreamer && dreamError;

    return (
      <div className="agent-panel agent-panel-full-focus">
        {settingsOpen === ag.id && (
          <SettingsModal agentId={ag.id} agentName={ag.name} currentModel={getSavedModel(ag.id)} onSave={(model) => handleSaveModel(ag.id, model)} onClose={() => setSettingsOpen(null)} />
        )}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-mono uppercase tracking-wider" style={{ color: ag.color }}>{ag.name}</h2>
            <ModelBadge agentId={ag.id} />
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setSettingsOpen(ag.id)} className="agent-settings-btn" title="Settings">⚙️</button>
            <button onClick={() => setFocused(null)} className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border" style={{ background:'var(--bg-hover)', borderColor:'var(--border-subtle)', color: 'var(--text-secondary)' }}>← Retroceder</button>
          </div>
        </div>
        <div className="agent-card agent-card-focused-full">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2"><span className="text-2xl">{ag.emoji}</span><h3 className="text-base font-bold font-mono" style={{ color:ag.color }}>{ag.name}</h3></div>
            <div className="flex items-center gap-2">
              <span className={`w-1.5 h-1.5 rounded-full ${ag.status==='Active'?'bg-green-400 animate-pulse':'bg-gray-500'}`} />
              {ag.id.startsWith('custom-') && <button onClick={() => removeCard(ag.id)} className="text-xs text-red-400 hover:text-red-200" title="Remove">×</button>}
            </div>
          </div>
          <p className="text-[11px] text-[var(--text-dim)] leading-tight mb-4">{ag.desc}</p>

          {/* ─── Dreamer Focus UI ─── */}
          {isDreamer && (
            <div className="mb-3 space-y-3">
              {/* Error banner */}
              {hasDreamError && (
                <div className="p-3 rounded-lg border flex items-start gap-2" style={{ borderColor: 'var(--alert-red)', background: 'rgba(255,50,50,0.1)' }}>
                  <span className="text-base">❌</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-mono font-bold" style={{ color: 'var(--alert-red)' }}>Sonho falhou</p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>{dreamError.message}</p>
                    <p className="text-[8px] font-mono mt-1" style={{ color: 'var(--text-dim)' }}>{new Date(dreamError.timestamp).toLocaleTimeString()}</p>
                  </div>
                  <button onClick={clearDreamError} className="text-xs" style={{ color: 'var(--text-muted)' }} title="Dismiss">✕</button>
                </div>
              )}
              {lastReport && !hasDreamError && (
                <div className="p-3 rounded-lg border text-[10px] font-mono" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Ultimo relatorio: </span>
                  <span style={{ color: '#c084fc' }}>{lastReport.timestamp || 'desconhecido'}</span>
                  {lastReport.summary && <p className="mt-1" style={{ color: 'var(--text-dim)' }}>{lastReport.summary}</p>}
                </div>
              )}
              {!lastReport && !hasDreamError && (
                <div className="p-3 rounded-lg border text-[10px] font-mono flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
                  <span style={{ color: 'var(--text-dim)' }}>Nenhum relatorio encontrado</span>
                  <button onClick={refreshLastReport} className="text-[9px] font-mono px-2 py-1 rounded border" style={{ borderColor: 'var(--border-subtle)', color: '#c084fc', background: 'var(--bg-secondary)' }}>🔄 Verificar</button>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={startDream} disabled={dreaming} className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border transition-all duration-300" style={{ background: dreaming && !fixMode ? 'var(--bg-secondary)' : 'rgba(192,132,252,0.12)', borderColor: dreaming && !fixMode ? 'var(--border-subtle)' : '#c084fc', color: dreaming && !fixMode ? 'var(--text-muted)' : '#c084fc', cursor: dreaming ? 'not-allowed' : 'pointer', opacity: dreaming ? 0.6 : 1 }}>
                  {dreaming && !fixMode ? '⏳ A sonhar...' : '🌙 Sonhar'}
                </button>
                <button onClick={startDreamFix} disabled={dreaming || !lastReport} className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border transition-all duration-300" style={{ background: dreaming && fixMode ? 'var(--bg-secondary)' : 'rgba(192,132,252,0.08)', borderColor: dreaming && fixMode ? 'var(--border-subtle)' : '#a78bfa', color: dreaming && fixMode ? 'var(--text-muted)' : '#a78bfa', cursor: dreaming || !lastReport ? 'not-allowed' : 'pointer', opacity: dreaming || !lastReport ? 0.5 : 1 }}>
                  {dreaming && fixMode ? '⏳ A corrigir...' : '🔧 Corrigir'}
                </button>
              </div>
              {!lastReport && !hasDreamError && (
                <p className="text-[8px] text-[var(--text-dim)]">Corrigir requer um relatorio. Primeiro faz "Sonhar" ou clica "🔄 Verificar".</p>
              )}
              <textarea
                className="agent-input w-full text-[11px] mt-2"
                rows={3}
                placeholder="Notas para o Dreamer (ex: correcoes a fazer, coisas a ignorar)..."
                value={dreamNotes}
                onChange={e => setDreamNotes(e.target.value)}
                disabled={dreaming}
                style={{ opacity: dreaming ? 0.5 : 1, resize: 'vertical' }}
              />
              <p className="text-[8px] text-[var(--text-dim)]">Estas notas sao enviadas como contexto ao carregar em Sonhar ou Corrigir.</p>
              <ProgressBar percent={dreamProgress} message={dreamMessage} error={!!hasDreamError} colorStart="#c084fc" colorEnd="#a78bfa" />
              <ConversationLog
                profileId={ag.id}
                logs={agentLogs[ag.id] || []}
                status={agentStatus[ag.id]}
                onClear={() => clearAgentLog(ag.id)}
                logEndRef={logEndRef}
              />
            </div>
          )}

          {/* ─── Wiki Curator Focus UI ─── */}
          {isWiki && (
            <div className="mb-3">
              <button onClick={startWikiCuration} disabled={curating} className="btn-glow w-full text-[11px] py-2 px-4 rounded-lg font-mono font-bold border transition-all duration-300" style={{ background: curating ? 'var(--bg-secondary)' : 'rgba(255,184,0,0.12)', borderColor: curating ? 'var(--border-subtle)' : 'var(--amber-warn)', color: curating ? 'var(--text-muted)' : 'var(--amber-warn)', cursor: curating ? 'not-allowed' : 'pointer', opacity: curating ? 0.6 : 1 }}>
                {curating ? '⏳ A curar...' : '🔍 Curar Wiki Automaticamente'}
              </button>
              <p className="text-[9px] text-[var(--text-dim)] mt-1">Verifica links, adiciona ao index, arquiva orfaos, e atualiza datas.</p>
              <ProgressBar percent={curateProgress} message={curateMessage} colorStart="var(--amber-warn)" colorEnd="var(--matrix-green)" />
              <ConversationLog
                profileId={ag.id}
                logs={agentLogs[ag.id] || []}
                status={agentStatus[ag.id]}
                onClear={() => clearAgentLog(ag.id)}
                logEndRef={logEndRef}
              />
            </div>
          )}

          {/* ─── Standard agents: textarea + dispatch ─── */}
          {!isDreamer && !isWiki && (
            <>
              {/* ─── Conversation Log ─── */}
              <ConversationLog
                profileId={ag.id}
                logs={agentLogs[ag.id] || []}
                status={agentStatus[ag.id]}
                onClear={() => clearAgentLog(ag.id)}
                logEndRef={logEndRef}
              />
              {ag.id === 'developer' && (
                <div className="mb-3 p-3 rounded-lg border text-[10px] font-mono space-y-2" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={useJcode} onChange={toggleJcode} className="accent-[var(--cyber-blue)]" />
                      <span style={{ color: useJcode ? 'var(--cyber-blue)' : 'var(--text-secondary)' }}>{useJcode ? '⚡ jcode forçado' : '🤖 Auto (classificador)'}</span>
                    </label>
                    <span className="text-[8px]" style={{ color: 'var(--text-dim)' }}>{useJcode ? 'Força jcode para todas as tarefas' : 'jcode só se classificador detetar código'}</span>
                  </div>
                  <div className="text-[8px]" style={{ color: 'var(--text-dim)' }}>
                    Dica: escreve <code>no_jcode</code> na tarefa para forçar Hermes.
                  </div>
                  {useJcode && (
                    <>
                      <div className="flex gap-2">
                        <select value={jcodeRepo} onChange={handleJcodeRepoChange} className="flex-1 bg-[var(--bg-secondary)] border rounded px-2 py-1 text-[10px]" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}>
                          <option value="/media/sf_AI_Ecosystem/10_Projects/">/media/sf_AI_Ecosystem/10_Projects/</option>
                          {jcodeRepos.map(r => (
                            <option key={r.path} value={r.path}>{r.path}</option>
                          ))}
                        </select>
                        <select value={jcodeToolProfile} onChange={handleJcodeToolChange} className="bg-[var(--bg-secondary)] border rounded px-2 py-1 text-[10px]" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}>
                          <option value="none">none (leitura)</option>
                          <option value="minimal">minimal</option>
                          <option value="full">full</option>
                        </select>
                      </div>
                      <div className="text-[8px]" style={{ color: 'var(--text-dim)' }}>
                        Repo: {jcodeRepo} · Tool profile: {jcodeToolProfile}
                      </div>
                    </>
                  )}
                </div>
              )}
              <textarea className="agent-input w-full text-[12px] mb-3" rows={8} placeholder={`Task for ${ag.name}...`} value={tasks[ag.id] || ''} onChange={e => updateTask(ag.id, e.target.value)} onKeyDown={e => { if (e.key==='Enter' && e.ctrlKey) { e.preventDefault(); dispatchTask(ag.id); } }} />
              <div className="flex gap-2">
                <button onClick={() => dispatchTask(ag.id)} disabled={!(tasks[ag.id] || '').trim() || (ag.id === 'developer' && jcodeStatus === 'running')} className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border" style={{ background: !(tasks[ag.id] || '').trim() ? 'var(--bg-secondary)' : 'var(--bg-card)', borderColor: !(tasks[ag.id] || '').trim() ? 'var(--border-subtle)' : 'var(--matrix-green)', color: !(tasks[ag.id] || '').trim() ? 'var(--text-muted)' : 'var(--matrix-green)', cursor: !(tasks[ag.id] || '').trim() ? 'not-allowed' : 'pointer', opacity: !(tasks[ag.id] || '').trim() ? 0.5 : 1 }}>
                  {jcodeStatus === 'running' ? '⏳ jcode...' : dispatched===ag.id ? '✓ Dispatched!' : 'Dispatch'}
                </button>
                {ag.id === 'developer' && useJcode && jcodeStatus === 'running' && (
                  <button onClick={killJcodeRun} className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border" style={{ background: 'rgba(255,50,50,0.12)', borderColor: 'var(--alert-red)', color: 'var(--alert-red)' }}>Parar</button>
                )}
                <button onClick={() => setFocused(null)} className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border" style={{ background:'var(--bg-hover)', borderColor:'var(--border-subtle)', color: 'var(--text-secondary)' }}>←</button>
              </div>
              {ag.id === 'developer' && useJcode && jcodeOutput && (
                <div className="mt-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono" style={{ color: 'var(--cyber-blue)' }}>jcode output · {jcodeStatus}</span>
                    {jcodeStatus !== 'running' && jcodeStatus !== 'pending' && (
                      <span className="text-[8px] font-mono" style={{ color: jcodeStatus === 'completed' ? 'var(--matrix-green)' : 'var(--alert-red)' }}>{jcodeStatus}</span>
                    )}
                  </div>
                  <pre className="w-full p-2 rounded-lg border text-[10px] font-mono overflow-auto" style={{ maxHeight: '320px', borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{jcodeOutput}</pre>
                </div>
              )}
              <span className="text-[9px] text-[var(--text-dim)] mt-2 block">Ctrl+Enter para enviar</span>
            </>
          )}
        </div>
      </div>
    );
  }

  // ─── Grid Mode ───

  return (
    <div className="agent-panel">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-mono uppercase tracking-wider" style={{ color:'var(--cyber-blue)' }}>Agent Profiles</h2>
        <button onClick={addCard} className="btn-glow px-3 py-1.5 rounded-lg text-xs font-mono border" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-active)', color: 'var(--cyber-blue)' }}>+ New Card</button>
      </div>
      {settingsOpen && (
        <SettingsModal agentId={settingsOpen} agentName={allAgents.find(a => a.id === settingsOpen)?.name || settingsOpen} currentModel={getSavedModel(settingsOpen)} onSave={(model) => handleSaveModel(settingsOpen, model)} onClose={() => setSettingsOpen(null)} />
      )}
      {curating && <div className="mb-4"><ProgressBar percent={curateProgress} message={curateMessage} colorStart="var(--amber-warn)" colorEnd="var(--matrix-green)" /></div>}
      {dreaming && <div className="mb-4"><ProgressBar percent={dreamProgress} message={dreamMessage} colorStart="#c084fc" colorEnd="#a78bfa" /></div>}
      {dreamError && !dreaming && (
        <div className="mb-4 p-2 rounded-lg border flex items-center gap-2" style={{ borderColor: 'var(--alert-red)', background: 'rgba(255,50,50,0.08)' }}>
          <span className="text-sm">⚠️</span>
          <span className="text-[10px] font-mono" style={{ color: 'var(--alert-red)' }}>Ultimo sonho falhou: {dreamError.message}</span>
          <button onClick={clearDreamError} className="text-[10px] ml-auto" style={{ color: 'var(--text-muted)' }}>✕</button>
        </div>
      )}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {allAgents.map((ag) => (
          <div key={ag.id} onClick={() => setFocused(ag.id)} className="agent-card" style={{ cursor:'pointer', position:'relative' }}>
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2"><span className="text-xl">{ag.emoji}</span><h3 className="text-sm font-bold font-mono" style={{ color:ag.color }}>{ag.name}</h3></div>
              <div className="flex items-center gap-2">
                <ModelBadge agentId={ag.id} />
                <button onClick={e => { e.stopPropagation(); setSettingsOpen(ag.id); }} className="agent-settings-btn" title="Settings">⚙️</button>
                <span className={`w-1.5 h-1.5 rounded-full ${ag.status==='Active'?'bg-green-400 animate-pulse':'bg-gray-500'}`} />
                {ag.id.startsWith('custom-') && <button onClick={e => { e.stopPropagation(); removeCard(ag.id); }} className="text-xs text-red-400 hover:text-red-200" title="Remove">×</button>}
              </div>
            </div>
            <p className="text-[10px] text-[var(--text-dim)] leading-tight mb-3">{ag.desc}</p>
            {ag.id === 'wiki' && (
              <button onClick={e => { e.stopPropagation(); startWikiCuration(); }} disabled={curating} className="w-full mb-2 py-1.5 rounded-lg text-[9px] font-mono font-bold border transition-all duration-300" style={{ background: curating ? 'var(--bg-secondary)' : 'rgba(255,184,0,0.1)', borderColor: curating ? 'var(--border-subtle)' : 'var(--amber-warn)', color: curating ? 'var(--text-muted)' : 'var(--amber-warn)', cursor: curating ? 'not-allowed' : 'pointer', opacity: curating ? 0.5 : 1 }}>
                {curating ? '⏳ ...' : '🔍 Curar Wiki'}
              </button>
            )}
            {ag.id === 'dreamer' && (
              <button onClick={e => { e.stopPropagation(); startDream(); }} disabled={dreaming} className="w-full mb-2 py-1.5 rounded-lg text-[9px] font-mono font-bold border transition-all duration-300" style={{ background: dreaming ? 'var(--bg-secondary)' : 'rgba(192,132,252,0.1)', borderColor: dreaming ? 'var(--border-subtle)' : dreamError ? 'var(--alert-red)' : '#c084fc', color: dreaming ? 'var(--text-muted)' : dreamError ? 'var(--alert-red)' : '#c084fc', cursor: dreaming ? 'not-allowed' : 'pointer', opacity: dreaming ? 0.5 : 1 }}>
                {dreaming ? '⏳ ...' : dreamError ? '⚠️ Sonhar' : '🌙 Sonhar'}
              </button>
            )}
            <div className="text-[9px] text-[var(--text-dim)] text-center">Clicar para expandir</div>
          </div>
        ))}
      </div>
    </div>
  );
}
