import React, { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = window.location.origin;
const MAX_TRACKS = 8;

// ── File Tree Node ──
function TreeNode({ node, depth, selectedPath, onSelect, expanded, toggleExpand, onPreview }) {
  if (!node) return null;
  const pad = { paddingLeft: `${depth * 16 + 8}px` };

  if (node.is_dir) {
    const isExpanded = expanded[node.path];
    const hasChildren = node.children?.length > 0;
    return (
      <div>
        <button
          onClick={() => toggleExpand(node.path)}
          className="w-full text-left py-1.5 text-[11px] font-mono transition-colors hover:bg-[var(--bg-hover)] flex items-center gap-1"
          style={pad}
        >
          <span className="text-[var(--text-muted)] w-3">{hasChildren ? (isExpanded ? '▾' : '▸') : ''}</span>
          <span style={{ color: 'var(--amber-warn)' }}>📁</span>
          <span className="text-[var(--text-secondary)]">{node.name}</span>
        </button>
        {isExpanded && hasChildren && (
          <div>
            {node.children.map((child, i) => (
              <TreeNode key={i} node={child} depth={depth + 1} selectedPath={selectedPath}
                onSelect={onSelect} expanded={expanded} toggleExpand={toggleExpand} onPreview={onPreview} />
            ))}
          </div>
        )}
      </div>
    );
  }

  // File
  const isSelected = selectedPath === node.path;
  const handleDoubleClick = () => {
    const url = `${API_BASE}/api/music/serve?path=${encodeURIComponent(node.path)}`;
    if (onPreview) onPreview(url, node.name);
  };
  return (
    <button
      onClick={() => onSelect(node)}
      onDoubleClick={handleDoubleClick}
      className="w-full text-left py-1 text-[11px] font-mono transition-colors flex items-center gap-1"
      style={{
        ...pad,
        background: isSelected ? 'var(--bg-card)' : 'transparent',
        color: isSelected ? 'var(--cyber-blue)' : 'var(--text-secondary)',
      }}
    >
      <span className="w-3"></span>
      <span style={{ color: node.label === 'music' ? 'var(--matrix-green)' : 'var(--amber-warn)' }}>
        {node.label === 'music' ? '♪' : '🌊'}
      </span>
      <span className="truncate flex-1 text-left">{node.name}</span>
    </button>
  );
}

export default function MusicGenerator({ onMusicGenerated }) {
  const [tree, setTree] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedInfo, setSelectedInfo] = useState('');
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewName, setPreviewName] = useState('');
  const [mixTracks, setMixTracks] = useState([]);
  const [mixResult, setMixResult] = useState(null);
  const [pipelineFile, setPipelineFile] = useState(null); // file that goes into step1
  const [step1Result, setStep1Result] = useState(null);
  const [step2Result, setStep2Result] = useState(null);
  const [step3Result, setStep3Result] = useState(null);
  const [crossfade, setCrossfade] = useState(0.5);
  const [fadeIn, setFadeIn] = useState(10);
  const [fadeOut, setFadeOut] = useState(10);
  const [masterFadeIn, setMasterFadeIn] = useState(10);
  const [masterFadeOut, setMasterFadeOut] = useState(10);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('browser'); // browser | mixer | pipeline
  const [mixPreview, setMixPreview] = useState(false); // playing all tracks together
  const mixPreviewRef = useRef([]); // refs to audio elements

  useEffect(() => {
    fetch(`${API_BASE}/api/music/tree`)
      .then(r => r.json())
      .then(data => {
        setTree(data);
        // Auto-expand top-level
        const exp = {};
        if (data.music) exp[data.music.path] = true;
        if (data.nature) exp[data.nature.path] = true;
        setExpanded(exp);
      })
      .catch(e => console.error('Erro ao buscar tree:', e));
  }, []);

  const toggleExpand = useCallback((path) => {
    setExpanded(prev => ({ ...prev, [path]: !prev[path] }));
  }, []);

  const selectFile = (node) => {
    setSelectedFile(node);
    setSelectedInfo(`${node.name} | ${node.label}`);
    // Fetch file info on-demand
    fetch(`${API_BASE}/api/music/file-info?path=${encodeURIComponent(node.path)}`)
      .then(r => r.json())
      .then(data => {
        if (data.duration_sec) {
          setSelectedInfo(`${node.name} | ${data.duration_sec}s | ${data.size_mb}MB | ${node.label}`);
        }
      })
      .catch(() => {});
  };

  const addTrack = () => {
    if (!selectedFile || mixTracks.length >= MAX_TRACKS) return;
    // Avoid duplicates
    if (mixTracks.some(t => t.path === selectedFile.path)) return;
    setMixTracks([...mixTracks, {
      path: selectedFile.path,
      name: selectedFile.name,
      volume: 100,
      delay: 0,
      fade_in: 0,
      fade_out: 0,
    }]);
  };

  const removeTrack = (idx) => {
    setMixTracks(mixTracks.filter((_, i) => i !== idx));
  };

  const updateTrack = (idx, field, value) => {
    setMixTracks(mixTracks.map((t, i) => i === idx ? { ...t, [field]: value } : t));
  };

  const runMixer = async () => {
    if (mixTracks.length === 0) return;
    setBusy('mixer');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/music/mixer`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracks: mixTracks,
          master_fade_in: masterFadeIn,
          master_fade_out: masterFadeOut,
        }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else {
        setMixResult(data);
        setPipelineFile(data.output); // mixer output feeds the pipeline
      }
    } catch (e) { setError(e.message); }
    setBusy('');
  };

  const useSingleFile = () => {
    if (!selectedFile) return;
    setPipelineFile(selectedFile.path);
    setMixResult(null);
    setMixTracks([]);
    setActiveTab('pipeline');
  };

  const runStep1 = async () => {
    if (!pipelineFile) return;
    setBusy('step1');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/music/step1`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: pipelineFile }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else { setStep1Result(data); }
    } catch (e) { setError(e.message); }
    setBusy('');
  };

  const runStep2 = async () => {
    if (!step1Result?.output) return;
    setBusy('step2');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/music/step2`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: step1Result.output, crossfade }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else { setStep2Result(data); }
    } catch (e) { setError(e.message); }
    setBusy('');
  };

  const runStep3 = async () => {
    if (!step2Result?.output) return;
    setBusy('step3');
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/music/step3`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: step2Result.output }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else { setStep3Result(data); }
    } catch (e) { setError(e.message); }
    setBusy('');
  };

  const runExport = async () => {
    if (!step3Result?.output) return;
    setBusy('export');
    setError('');
    try {
      const name = (pipelineFile || 'output').split('/').pop().replace(/\.[^.]+$/, '');
      const res = await fetch(`${API_BASE}/api/music/export`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filepath: step3Result.output, fade_in: fadeIn, fade_out: fadeOut, name }),
      });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else {
        if (onMusicGenerated) {
          onMusicGenerated({
            loopPath: step2Result.output,
            loopDuration: step2Result.duration,
            exportPath: data.output,
            exportDuration: data.duration,
          });
        }
      }
    } catch (e) { setError(e.message); }
    setBusy('');
  };

  const labelCls = 'text-[10px] text-[var(--text-dim)] block mb-1 font-mono';
  const btnStyle = (active, disabled) => ({
    opacity: (!active || disabled) ? 0.4 : 1,
    cursor: disabled ? 'not-allowed' : 'pointer',
    background: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    transition: 'all 0.3s',
  });
  const stepCls = 'p-3 rounded-lg border';

  // ── Mix Preview: play all tracks together with volume/delay ──
  const toggleMixPreview = () => {
    if (mixPreview) {
      // Stop all
      mixPreviewRef.current.forEach(el => { if (el) { el.pause(); el.currentTime = 0; } });
      setMixPreview(false);
    } else {
      // Start all tracks with their delay
      mixTracks.forEach((t, i) => {
        const el = mixPreviewRef.current[i];
        if (el) {
          el.volume = t.volume / 100;
          el.currentTime = 0;
          if (t.delay > 0) {
            setTimeout(() => { el.play().catch(() => {}); }, t.delay * 1000);
          } else {
            el.play().catch(() => {});
          }
        }
      });
      setMixPreview(true);
    }
  };

  // Stop preview when tracks change
  useEffect(() => {
    if (mixPreview) {
      mixPreviewRef.current.forEach(el => { if (el) { el.pause(); el.currentTime = 0; } });
      setMixPreview(false);
    }
    // eslint-disable-next-line
  }, [mixTracks.length]);

  return (
    <div>
      {/* Tabs: Browser | Mixer | Pipeline */}
      <div className="flex gap-1 mb-4 border-b border-[var(--border-subtle)]">
        {[
          { key: 'browser', label: '📂 Browser' },
          { key: 'mixer', label: '🎛️ Mixer' },
          { key: 'pipeline', label: '🔄 Pipeline' },
        ].map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className="px-4 py-2 text-[11px] font-mono tracking-wider transition-all border-b-2"
            style={{
              borderColor: activeTab === t.key ? 'var(--cyber-blue)' : 'transparent',
              color: activeTab === t.key ? 'var(--cyber-blue)' : 'var(--text-muted)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Browser */}
      {activeTab === 'browser' && tree && (
        <div>
          <div className="flex gap-4">
            {/* Music tree */}
            <div className="flex-1">
              <h4 className="text-[10px] font-mono text-[var(--matrix-green)] mb-2 tracking-wider">MÚSICA</h4>
              <div className="max-h-64 overflow-y-auto rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}>
                <TreeNode node={tree.music} depth={0} selectedPath={selectedFile?.path}
                  onSelect={selectFile} expanded={expanded} toggleExpand={toggleExpand}
                  onPreview={(url, name) => { setPreviewUrl(url); setPreviewName(name); }} />
              </div>
            </div>
            {/* Nature tree */}
            <div className="flex-1">
              <h4 className="text-[10px] font-mono text-[var(--amber-warn)] mb-2 tracking-wider">NATUREZA</h4>
              <div className="max-h-64 overflow-y-auto rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}>
                <TreeNode node={tree.nature} depth={0} selectedPath={selectedFile?.path}
                  onSelect={selectFile} expanded={expanded} toggleExpand={toggleExpand}
                  onPreview={(url, name) => { setPreviewUrl(url); setPreviewName(name); }} />
              </div>
            </div>
          </div>
          {selectedInfo && (
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[11px] font-mono text-[var(--text-secondary)]">{selectedInfo}</span>
              <div className="flex gap-2">
                <button onClick={addTrack} disabled={!selectedFile || mixTracks.length >= MAX_TRACKS}
                  className="px-3 py-1.5 rounded-lg font-mono text-[10px] tracking-wider"
                  style={btnStyle(true, !selectedFile || mixTracks.length >= MAX_TRACKS)}>
                  ➕ Mixer ({mixTracks.length}/{MAX_TRACKS})
                </button>
              </div>
            </div>
          )}

          {/* Audio player */}
          {previewUrl && (
            <div className="mt-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-mono text-[var(--cyber-blue)]">▶</span>
                <span className="text-[11px] font-mono text-[var(--text-secondary)] truncate flex-1">{previewName}</span>
                <button onClick={() => { setPreviewUrl(''); setPreviewName(''); }}
                  className="text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                  title="Fechar player">✕</button>
              </div>
              <audio controls src={previewUrl} style={{ width: '100%', height: '32px' }} />
            </div>
          )}
        </div>
      )}

      {/* Tab: Mixer */}
      {activeTab === 'mixer' && (
        <div>
          <p className="text-[10px] font-mono text-[var(--text-dim)] mb-3">
            Adiciona samples no Browser → Mixer. Cada track tem volume, delay e fade individual.
          </p>
          <div className="space-y-2 mb-4">
            {mixTracks.length === 0 && (
              <div className="text-center py-8 text-[var(--text-dim)] font-mono text-xs">
                Nenhuma track no mixer. Vai ao Browser para adicionar.
              </div>
            )}
            {mixTracks.map((t, i) => (
              <div key={i} className="flex items-center gap-2 p-2 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
                <span className="text-[10px] font-mono text-[var(--text-dim)] w-5">{i + 1}</span>
                <span className="text-[11px] font-mono text-[var(--text-secondary)] truncate flex-1" title={t.path}>{t.name}</span>
                <label className="flex items-center gap-1">
                  <span className="text-[9px] font-mono text-[var(--text-dim)]">Vol%</span>
                  <input type="number" min={0} max={200} value={t.volume}
                    onChange={e => updateTrack(i, 'volume', parseInt(e.target.value, 10))}
                    className="input-glow w-14 text-center text-[10px]" />
                </label>
                <label className="flex items-center gap-1">
                  <span className="text-[9px] font-mono text-[var(--text-dim)]">Delay</span>
                  <input type="number" min={0} value={t.delay}
                    onChange={e => updateTrack(i, 'delay', parseInt(e.target.value, 10))}
                    className="input-glow w-14 text-center text-[10px]" />
                </label>
                <label className="flex items-center gap-1">
                  <span className="text-[9px] font-mono text-[var(--text-dim)]">FI</span>
                  <input type="number" min={0} step={0.5} value={t.fade_in}
                    onChange={e => updateTrack(i, 'fade_in', parseFloat(e.target.value) || 0)}
                    className="input-glow w-12 text-center text-[10px]" />
                </label>
                <label className="flex items-center gap-1">
                  <span className="text-[9px] font-mono text-[var(--text-dim)]">FO</span>
                  <input type="number" min={0} step={0.5} value={t.fade_out}
                    onChange={e => updateTrack(i, 'fade_out', parseFloat(e.target.value) || 0)}
                    className="input-glow w-12 text-center text-[10px]" />
                </label>
                <button onClick={() => removeTrack(i)}
                  className="w-5 h-5 flex items-center justify-center rounded-full text-[10px] text-red-400 hover:text-red-200 hover:bg-red-400/10 transition-all">
                  ✕
                </button>
              </div>
            ))}
          </div>

          {mixTracks.length > 0 && (
            <>
              <div className="flex items-center gap-4 mb-3">
                <div>
                  <label className={labelCls}>Master Fade In (s)</label>
                  <input type="number" min={0} value={masterFadeIn}
                    onChange={e => setMasterFadeIn(parseInt(e.target.value, 10) || 0)} disabled={busy}
                    className="input-glow w-20 text-center text-[11px]" />
                </div>
                <div>
                  <label className={labelCls}>Master Fade Out (s)</label>
                  <input type="number" min={0} value={masterFadeOut}
                    onChange={e => setMasterFadeOut(parseInt(e.target.value, 10) || 0)} disabled={busy}
                    className="input-glow w-20 text-center text-[11px]" />
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={toggleMixPreview} disabled={busy}
                  className="px-4 py-3 rounded-lg font-mono text-[11px] font-bold tracking-wider uppercase transition-all"
                  style={{
                    opacity: busy ? 0.5 : 1, cursor: busy ? 'not-allowed' : 'pointer',
                    background: mixPreview ? 'rgba(0,255,65,0.08)' : 'var(--bg-card)',
                    color: 'var(--matrix-green)',
                    border: '1px solid rgba(0,255,65,0.3)',
                  }}>
                  {mixPreview ? '⏹ Parar Preview' : '▶ Preview Mix'}
                </button>
                <button onClick={runMixer} disabled={busy}
                  className="px-6 py-3 rounded-lg font-mono text-[12px] font-bold tracking-wider uppercase transition-all"
                  style={{
                    opacity: busy ? 0.5 : 1, cursor: busy ? 'wait' : 'pointer',
                    background: 'var(--bg-card)', color: 'var(--cyber-blue)',
                    border: '1px solid rgba(0,212,255,0.3)',
                    boxShadow: busy ? 'none' : '0 2px 12px rgba(0,212,255,0.15)',
                  }}>
                  {busy === 'mixer' ? 'A misturar...' : 'Exportar Mix'}
                </button>
              </div>
              {/* Hidden audio elements for preview */}
              <div style={{ display: 'none' }}>
                {mixTracks.map((t, i) => (
                  <audio key={i} ref={el => mixPreviewRef.current[i] = el}
                    src={`${API_BASE}/api/music/serve?path=${encodeURIComponent(t.path)}`} preload="auto" />
                ))}
              </div>
            </>
          )}

          {mixResult && (
            <div className="mt-3 p-3 rounded-lg border" style={{ borderColor: 'var(--matrix-green)', background: 'rgba(0,255,65,0.03)' }}>
              <div className="text-[11px] font-mono text-[var(--matrix-green)]">
                Mix exportado: {mixResult.tracks} tracks | {mixResult.duration}s | {mixResult.size_mb}MB
              </div>
              <button onClick={() => setActiveTab('pipeline')}
                className="mt-2 px-3 py-1 rounded-lg font-mono text-[10px] text-[var(--cyber-blue)] border border-[var(--border-subtle)]">
                Ir para Pipeline →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab: Pipeline */}
      {activeTab === 'pipeline' && (
        <div>
          <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}>
            <div className="text-[10px] font-mono text-[var(--text-dim)] mb-1">Ficheiro para pipeline:</div>
            <div className="text-[11px] font-mono text-[var(--text-secondary)]">
              {pipelineFile ? pipelineFile.split('/').pop() : 'Nenhum — selecciona no Browser ou usa o Mixer'}
            </div>
            {mixResult && pipelineFile === mixResult.output && (
              <span className="text-[10px] font-mono text-[var(--matrix-green)]"> (mix de {mixResult.tracks} tracks)</span>
            )}
          </div>

          <div className="space-y-3 mb-4">
            {/* Step 1 */}
            <div className={stepCls} style={{
              borderColor: step1Result?.success ? 'var(--matrix-green)' : 'var(--border-subtle)',
              background: step1Result?.success ? 'rgba(0,255,65,0.03)' : 'var(--bg-card)',
            }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-mono font-bold text-[var(--matrix-green)]">Passo 1: Remover Silêncio</span>
                <button onClick={runStep1} disabled={!pipelineFile || busy} style={btnStyle(true, !pipelineFile || busy)}
                  className="px-4 py-1.5 rounded-lg font-mono text-[10px] tracking-wider">
                  {busy === 'step1' ? '...' : step1Result?.success ? '✓' : 'Executar'}
                </button>
              </div>
              {step1Result && <div className="text-[10px] font-mono text-[var(--text-dim)]">{step1Result.duration}s (removidos: {step1Result.removed}s)</div>}
            </div>

            {/* Step 2 */}
            <div className={stepCls} style={{
              borderColor: step2Result?.success ? 'var(--matrix-green)' : 'var(--border-subtle)',
              background: step2Result?.success ? 'rgba(0,255,65,0.03)' : 'var(--bg-card)',
            }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-mono font-bold text-[var(--matrix-green)]">Passo 2: Loop Perfeito</span>
                <button onClick={runStep2} disabled={!step1Result || busy} style={btnStyle(true, !step1Result || busy)}
                  className="px-4 py-1.5 rounded-lg font-mono text-[10px] tracking-wider">
                  {busy === 'step2' ? '...' : step2Result?.success ? '✓' : 'Executar'}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-[var(--text-dim)]">Crossfade:</span>
                <input type="number" min={0.1} max={10} step={0.1} value={crossfade}
                  onChange={e => setCrossfade(parseFloat(e.target.value))} disabled={busy}
                  className="input-glow w-16 text-center text-[10px]" />
                <span className="text-[10px] font-mono text-[var(--text-dim)]">s</span>
              </div>
              {step2Result && <div className="text-[10px] font-mono text-[var(--text-dim)] mt-1">{step2Result.duration}s | {step2Result.size_mb}MB</div>}
            </div>

            {/* Step 3 */}
            <div className={stepCls} style={{
              borderColor: step3Result?.success ? 'var(--matrix-green)' : 'var(--border-subtle)',
              background: step3Result?.success ? 'rgba(0,255,65,0.03)' : 'var(--bg-card)',
            }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-mono font-bold text-[var(--matrix-green)]">Passo 3: Estender a 8h</span>
                <button onClick={runStep3} disabled={!step2Result || busy} style={btnStyle(true, !step2Result || busy)}
                  className="px-4 py-1.5 rounded-lg font-mono text-[10px] tracking-wider">
                  {busy === 'step3' ? '...' : step3Result?.success ? '✓' : 'Executar'}
                </button>
              </div>
              {step3Result && <div className="text-[10px] font-mono text-[var(--text-dim)]">{step3Result.duration_h}h | {step3Result.size_mb}MB</div>}
            </div>

            {/* Export */}
            <div className={stepCls} style={{ borderColor: 'var(--cyber-blue)', background: 'var(--bg-card)' }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-mono font-bold text-[var(--cyber-blue)]">Export Final (Fade In/Out)</span>
                <button onClick={runExport} disabled={!step3Result || busy}
                  className="px-4 py-1.5 rounded-lg font-mono text-[10px] tracking-wider"
                  style={{
                    opacity: (!step3Result || busy) ? 0.4 : 1, cursor: (!step3Result || busy) ? 'not-allowed' : 'pointer',
                    background: 'var(--bg-card)', color: 'var(--cyber-blue)',
                    border: '1px solid rgba(0,212,255,0.3)',
                  }}>
                  {busy === 'export' ? '...' : 'Exportar MP3'}
                </button>
              </div>
              <div className="flex gap-4">
                <div>
                  <label className={labelCls}>Fade In (s)</label>
                  <input type="number" min={0} value={fadeIn}
                    onChange={e => setFadeIn(parseInt(e.target.value, 10) || 0)} disabled={busy}
                    className="input-glow w-20 text-center text-[11px]" />
                </div>
                <div>
                  <label className={labelCls}>Fade Out (s)</label>
                  <input type="number" min={0} value={fadeOut}
                    onChange={e => setFadeOut(parseInt(e.target.value, 10) || 0)} disabled={busy}
                    className="input-glow w-20 text-center text-[11px]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error + busy (shared) */}
      {error && <div className="text-[11px] font-mono mt-3" style={{ color: 'var(--alert-red)' }}>Erro: {error}</div>}
      {busy && <div className="text-[11px] font-mono mt-3" style={{ color: 'var(--amber-warn)' }}>A processar: {busy}...</div>}
    </div>
  );
}