import { useState, useEffect, useRef } from 'react';
import SettingsModal from './SettingsModal';

const DEFAULT_AGENTS = [
  { id:'dev',   name:'Developer',     emoji:'💻', desc:'Coding, debugging, infra',        color:'#00d4ff', status:'Standby' },
  { id:'mm',    name:'Multimedia',    emoji:'🎨', desc:'Images, video, audio, ComfyUI',   color:'#ff7b00', status:'Standby' },
  { id:'res',   name:'Researcher',    emoji:'🔬', desc:'Web research, papers, synthesis', color:'#00ff41', status:'Standby' },
  { id:'wiki',  name:'Wiki Curator',  emoji:'📚', desc:'Obsidian, LLM Wiki, memory',     color:'#ffb800', status:'Standby' },
  { id:'dream', name:'Dreamer',       emoji:'🌙', desc:'Self-improvement, audits, wiki lint, skill gaps', color:'#c084fc', status:'Standby' },
];

const STORAGE_KEY = (id) => `agent_model_${id}`;
const DREAM_TIMEOUT_SEC = 45; // assume failure if no progress change in 45s

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
    socket.on('wiki_curate_started', onStarted);
    socket.on('wiki_curate_progress', onProgress);
    socket.on('wiki_curate_complete', onComplete);
    socket.on('wiki_curate_error', onError);
    return () => {
      socket.off('wiki_curate_started', onStarted);
      socket.off('wiki_curate_progress', onProgress);
      socket.off('wiki_curate_complete', onComplete);
      socket.off('wiki_curate_error', onError);
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
    socket.emit('dispatch_task', payload);
    setDispatched(id);
    setTasks(prev => ({ ...prev, [id]: '' }));
    setTimeout(() => setDispatched(null), 3000);
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
    const isDreamer = ag.id === 'dream';
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
            </div>
          )}

          {/* ─── Standard agents: textarea + dispatch ─── */}
          {!isDreamer && !isWiki && (
            <>
              <textarea className="agent-input w-full text-[12px] mb-3" rows={8} placeholder={`Task for ${ag.name}...`} value={tasks[ag.id] || ''} onChange={e => updateTask(ag.id, e.target.value)} onKeyDown={e => { if (e.key==='Enter' && e.ctrlKey) { e.preventDefault(); dispatchTask(ag.id); } }} />
              <div className="flex gap-2">
                <button onClick={() => dispatchTask(ag.id)} disabled={!(tasks[ag.id] || '').trim()} className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border" style={{ background: !(tasks[ag.id] || '').trim() ? 'var(--bg-secondary)' : 'var(--bg-card)', borderColor: !(tasks[ag.id] || '').trim() ? 'var(--border-subtle)' : 'var(--matrix-green)', color: !(tasks[ag.id] || '').trim() ? 'var(--text-muted)' : 'var(--matrix-green)', cursor: !(tasks[ag.id] || '').trim() ? 'not-allowed' : 'pointer', opacity: !(tasks[ag.id] || '').trim() ? 0.5 : 1 }}>
                  {dispatched===ag.id ? '✓ Dispatched!' : 'Dispatch'}
                </button>
                <button onClick={() => setFocused(null)} className="btn-glow px-4 py-2 rounded-lg text-xs font-mono border" style={{ background:'var(--bg-hover)', borderColor:'var(--border-subtle)', color: 'var(--text-secondary)' }}>←</button>
              </div>
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
            {ag.id === 'dream' && (
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
