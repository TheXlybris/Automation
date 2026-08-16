import { useState, useRef, useEffect } from 'react';

const API_BASE = window.location.origin;

const STYLES = {
  fantasy: {
    label: 'Fantasy',
    negative: 'static, still, motionless, blurry details, worst quality, low quality, JPEG artifacts, deformed, disfigured, morphological aberrations, messy background, overall gray, overexposed, realistic, photographic, live-action, real world, text, watermark, subtitle',
  },
  realistic: {
    label: 'Realista',
    negative: 'static, still, motionless, blurry details, worst quality, low quality, JPEG artifacts, deformed, disfigured, morphological aberrations, messy background, overexposed, cartoon, anime, illustration, painting, 3d render, text, watermark, subtitle',
  },
};

const DURATIONS = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200];

export default function VideoGenerator({ onVideoToPool }) {
  const [style, setStyle] = useState('fantasy');
  const [imageFilename, setImageFilename] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [scene, setScene] = useState('');
  const [duration, setDuration] = useState(40);
  const [prompts, setPrompts] = useState([]);
  const [negative, setNegative] = useState(STYLES.fantasy.negative);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [fps, setFps] = useState(16);
  const [upscale, setUpscale] = useState(1);
  const [steps, setSteps] = useState(8);
  const [cfg, setCfg] = useState(1.5);
  const [seed, setSeed] = useState(-1);
  const [generating, setGenerating] = useState(false);
  const [storyboardLoading, setStoryboardLoading] = useState(false);
  const [postProcessing, setPostProcessing] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [statusType, setStatusType] = useState('');
  const [resultVideo, setResultVideo] = useState(null);
  const [ppVideoFilename, setPpVideoFilename] = useState('');
  const [resultUrl, setResultUrl] = useState('');
  const pollRef = useRef(null);

  const [progress, setProgress] = useState(null); // {node, value, max, step}
  const [clientId, setClientId] = useState('');
  const wsRef = useRef(null);
  const COMFYUI_WS = 'ws://192.168.0.187:8188/ws';

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (wsRef.current) wsRef.current.close();
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };
  const stopWS = () => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
  };

  // ── Style ──
  const handleStyleChange = (s) => {
    setStyle(s);
    setNegative(STYLES[s].negative);
  };

  // ── Image upload ──
  const handleDrop = async (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) await uploadImage(file);
  };

  const handleFileInput = async (e) => {
    const file = e.target.files[0];
    if (file) await uploadImage(file);
  };

  const uploadImage = async (file) => {
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result);
    reader.readAsDataURL(file);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Upload falhou');
      setImageFilename(data.filename);
      setStatusMsg('Imagem carregada. Gera o script e depois o vídeo.');
      setStatusType('info');
    } catch (err) {
      setStatusMsg(`Erro upload: ${err.message}`);
      setStatusType('error');
    }
  };

  // ── Storyboard ──
  const generateStoryboard = async () => {
    if (!scene.trim()) return;
    setStoryboardLoading(true);
    setStatusMsg('A gerar script...');
    setStatusType('info');
    setPrompts([]);
    try {
      const res = await fetch(`${API_BASE}/api/video/storyboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene, duration, style }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setPrompts(data.positive || []);
      if (data.negative) setNegative(data.negative);
      setStatusMsg(`${data.positive?.length || 0} prompts gerados.`);
      setStatusType('success');
    } catch (err) {
      setStatusMsg(`Erro: ${err.message}`);
      setStatusType('error');
    }
    setStoryboardLoading(false);
  };

  const updatePrompt = (idx, val) => {
    setPrompts(prompts.map((p, i) => i === idx ? val : p));
  };

  // ── Generate ──
  const generateVideo = async () => {
    if (!imageFilename || prompts.length === 0) {
      setStatusMsg('Carrega imagem e gera o script primeiro.');
      setStatusType('error');
      return;
    }
    setGenerating(true);
    setResultVideo(null);
    setResultUrl('');
    setStatusMsg('A submeter ao ComfyUI...');
    setStatusType('info');
    stopPolling();
    try {
      const res = await fetch(`${API_BASE}/api/video/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_filename: imageFilename, prompts, negative, style,
          steps, cfg, seed,
        }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (data.client_id) {
        setClientId(data.client_id);
        startWS(data.client_id, data.prompt_id);
      }
      setStatusMsg('Na fila do ComfyUI...');
      startPolling(data.prompt_id);
    } catch (err) {
      setStatusMsg(`Erro: ${err.message}`);
      setStatusType('error');
      setGenerating(false);
    }
  };

  // ── WebSocket progress ──
  const [wsNodeCount, setWsNodeCount] = useState(0);
  const [wsTotalNodes, setWsTotalNodes] = useState(0);
  const startWS = (cid, pid) => {
    stopWS();
    setWsNodeCount(0);
    setWsTotalNodes(0);
    setProgress(null);
    try {
      const ws = new WebSocket(`${COMFYUI_WS}?clientId=${cid}`);
      wsRef.current = ws;
      let executedNodes = 0;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          // ComfyUI v0.23: executing/progress may not carry prompt_id
          // Only filter when prompt_id is present and doesn't match
          if (msg.data && msg.data.prompt_id && msg.data.prompt_id !== pid) return;

          if (msg.type === 'execution_start') {
            setStatusMsg('ComfyUI iniciou execução...');
            setStatusType('info');
          } else if (msg.type === 'executing') {
            // {node: id, display_node: name} — node null = finished
            if (msg.data.node === null || msg.data.node === undefined) return;
            executedNodes++;
            setWsNodeCount(executedNodes);
            const nodeName = msg.data.display_node || msg.data.node || '';
            setStatusMsg(`A executar node ${executedNodes}: ${nodeName}`);
          } else if (msg.type === 'progress') {
            // ComfyUI v0.23: {value, max, step} — actual sampling progress
            setProgress({
              value: msg.data.value || 0,
              max: msg.data.max || 0,
              step: msg.data.step || 0,
            });
            setStatusMsg(`A amostrar: ${msg.data.value}/${msg.data.max} (step ${msg.data.step || '?'})`);
          } else if (msg.type === 'executed') {
            setProgress(null);
          } else if (msg.type === 'execution_error' || msg.type === 'execution_interrupted') {
            setStatusMsg('Erro no ComfyUI');
            setStatusType('error');
          }
        } catch (e) {}
      };
      ws.onerror = () => {};
      ws.onopen = () => {
        setStatusMsg('WebSocket conectado — à espera do ComfyUI...');
      };
    } catch (e) {}
  };

  const startPolling = (pid) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/video/status/${pid}`);
        const data = await res.json();
        if (data.status === 'done') {
          stopPolling();
          stopWS();
          setProgress(null);
          const vids = data.videos || [];
          if (vids.length === 0) {
            setGenerating(false);
            setStatusMsg('Concluído mas sem vídeos.');
            setStatusType('error');
            return;
          }
          // Multiple chunks → fetch concatenates them; single → just fetch
          if (vids.length > 1) {
            setStatusMsg(`${vids.length} chunks gerados. A concatenar...`);
          } else {
            setStatusMsg('Vídeo pronto. A copiar...');
          }
          await fetchVideo(vids);
        } else if (data.status === 'error') {
          stopPolling();
          setGenerating(false);
          setStatusMsg(`Erro ComfyUI: ${data.error || 'desconhecido'}`);
          setStatusType('error');
        } else if (data.status === 'running') {
          setStatusMsg('A gerar vídeo...');
        } else {
          setStatusMsg(`Na fila... (${data.status})`);
        }
      } catch (e) { /* keep polling */ }
    }, 3000);
  };

  const fetchVideo = async (vids) => {
    try {
      const res = await fetch(`${API_BASE}/api/video/fetch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ videos: vids }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResultVideo(data.filename);
      setResultUrl(data.url);
      setGenerating(false);
      setStatusMsg('Vídeo pronto!');
      setStatusType('success');
    } catch (err) {
      setGenerating(false);
      setStatusMsg(`Erro: ${err.message}`);
      setStatusType('error');
    }
  };

  const runPostprocess = async () => {
    const targetVideo = ppVideoFilename || resultVideo;
    if (!targetVideo) {
      setStatusMsg('Fornece um vídeo para pós-processar.');
      setStatusType('error');
      return;
    }
    setPostProcessing(true);
    setProgress(null);
    setStatusMsg('A submeter pós-processamento...');
    setStatusType('info');
    stopPolling();
    try {
      const res = await fetch(`${API_BASE}/api/video/postprocess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: targetVideo, fps, upscale }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (data.client_id) {
        setClientId(data.client_id);
        startWS(data.client_id, data.prompt_id);
      }
      setStatusMsg('Pós-processamento na fila do ComfyUI...');
      // Poll for PP completion
      pollRef.current = setInterval(async () => {
        try {
          const sRes = await fetch(`${API_BASE}/api/video/status/${data.prompt_id}`);
          const sData = await sRes.json();
          if (sData.status === 'done') {
            stopPolling();
            stopWS();
            setProgress(null);
            const vids = sData.videos || [];
            if (vids.length > 0) {
              const fRes = await fetch(`${API_BASE}/api/video/fetch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ videos: vids, upscale }),
              });
              const fData = await fRes.json();
              if (fData.success) {
                setResultVideo(fData.filename);
                setResultUrl(fData.url);
                setStatusMsg('Vídeo melhorado!');
                setStatusType('success');
              }
            } else {
              setStatusMsg('Pós-proc concluído mas sem vídeo.');
              setStatusType('error');
            }
            setPostProcessing(false);
          } else if (sData.status === 'error') {
            stopPolling();
            stopWS();
            setPostProcessing(false);
            setStatusMsg('Erro no pós-processamento');
            setStatusType('error');
          } else {
            setStatusMsg(`Pós-processamento... (${sData.status})`);
          }
        } catch (e) {}
      }, 3000);
    } catch (err) {
      setPostProcessing(false);
      setStatusMsg(`Erro pós-proc: ${err.message}`);
      setStatusType('error');
    }
  };

  // ── Video upload for postprocess ──
  const handlePpVideoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Upload falhou');
      setPpVideoFilename(data.filename);
      setStatusMsg(`Vídeo carregado: ${data.filename}`);
      setStatusType('info');
    } catch (err) {
      setStatusMsg(`Erro upload vídeo: ${err.message}`);
      setStatusType('error');
    }
  };

  // ── Media Pool ──
  const sendToPool = () => {
    if (resultVideo && onVideoToPool) onVideoToPool(resultVideo);
  };

  // ── Extend ──
  const extendVideo = async () => {
    if (!resultVideo) return;
    setStatusMsg('A criar WF de extensão...');
    setStatusType('info');
    try {
      const res = await fetch(`${API_BASE}/api/video/extend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_filename: resultVideo, prompts, negative }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (data.prompt_id) {
        // Auto-submitted to ComfyUI
        setGenerating(true);
        setResultVideo(null);
        setResultUrl('');
        setStatusMsg('Extensão submetida ao ComfyUI...');
        startPolling(data.prompt_id);
      } else {
        setStatusMsg(`WF de extensão criado: ${data.wf_path || 'ok'}`);
        setStatusType('success');
      }
    } catch (err) {
      setStatusMsg(`Erro: ${err.message}`);
      setStatusType('error');
    }
  };

  // ── Render ──
  const labelCls = 'text-[10px] text-[var(--text-dim)] block mb-1.5 font-mono';
  const inputCls = 'input-glow w-full text-[12px]';
  const chipCls = (active) => ({
    padding: '4px 14px',
    borderRadius: '6px',
    fontSize: '11px',
    fontFamily: 'monospace',
    cursor: 'pointer',
    transition: 'all 0.3s',
    background: active ? 'var(--bg-card)' : 'transparent',
    border: `1px solid ${active ? 'var(--cyber-blue)' : 'var(--border-subtle)'}`,
    color: active ? 'var(--cyber-blue)' : 'var(--text-muted)',
    boxShadow: active ? '0 0 8px rgba(0,200,255,0.15)' : 'none',
  });

  const isBusy = generating || storyboardLoading || postProcessing;

  return (
    <div className="space-y-4">
      {/* Style selector */}
      <div className="flex items-center gap-3">
        <span className={labelCls} style={{ marginBottom: 0 }}>Estilo</span>
        {Object.entries(STYLES).map(([key, val]) => (
          <button
            key={key}
            onClick={() => handleStyleChange(key)}
            disabled={isBusy}
            style={chipCls(style === key)}
          >
            {val.label}
          </button>
        ))}
      </div>

      {/* Image upload */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors hover:border-[var(--cyber-blue)]"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}
        onClick={() => document.getElementById('vg-file-input').click()}
      >
        {imagePreview ? (
          <div className="rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
            <img src={imagePreview} alt="Preview" className="w-full object-contain" style={{ maxHeight: 180 }} />
          </div>
        ) : (
          <>
            <div className="text-2xl mb-1">🖼️</div>
            <p className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
              Arrasta imagem PNG aqui ou clica para selecionar
            </p>
          </>
        )}
        <input id="vg-file-input" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleFileInput} />
      </div>
      {imageFilename && (
        <div className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          📎 {imageFilename}
        </div>
      )}

      {/* Storyboard */}
      <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
        <div className="text-[11px] font-mono font-bold mb-3" style={{ color: 'var(--cyber-blue)' }}>
          📝 STORYBOARD
        </div>

        <div className="mb-3">
          <label className={labelCls}>Descrição da cena (Português)</label>
          <textarea
            className={inputCls}
            rows={3}
            placeholder="Ex: Um rio no meio de um vale a fluir, rodeado de arvores, com montanhas ao fundo"
            value={scene}
            onChange={(e) => setScene(e.target.value)}
            disabled={isBusy}
          />
        </div>

        <div className="flex items-end gap-3 mb-3">
          <div>
            <label className={labelCls}>Duração</label>
            <select
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value, 10))}
              disabled={isBusy}
              className="input-glow text-[12px] px-3 py-2"
            >
              {DURATIONS.map(d => (
                <option key={d} value={d}>{d}s ({Math.ceil(d / 5)} chunks)</option>
              ))}
            </select>
          </div>
          <button
            onClick={generateStoryboard}
            disabled={!scene.trim() || storyboardLoading}
            className="btn-glow px-4 py-2 rounded-lg font-mono text-[11px] font-bold tracking-wider uppercase transition-all"
            style={{
              opacity: (!scene.trim() || storyboardLoading) ? 0.4 : 1,
              cursor: (!scene.trim() || storyboardLoading) ? 'not-allowed' : 'pointer',
              background: 'var(--bg-secondary)',
              color: 'var(--cyber-blue)',
              border: '1px solid rgba(0,200,255,0.3)',
            }}
          >
            {storyboardLoading ? 'A gerar...' : 'Gerar Script'}
          </button>
        </div>

        {/* Prompt list */}
        {prompts.length > 0 && (
          <div className="space-y-2 mt-3">
            <div className="text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>
              Prompts ({prompts.length} chunks) — editável
            </div>
            {prompts.map((p, i) => {
              const wordCount = p.trim().split(/\s+/).length;
              const overLimit = wordCount > 15;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[10px] font-mono flex-shrink-0 w-16" style={{ color: 'var(--text-muted)' }}>
                    Chunk {i + 1}
                  </span>
                  <input
                    type="text"
                    className="input-glow flex-1 text-[12px]"
                    value={p}
                    onChange={(e) => updatePrompt(i, e.target.value)}
                    disabled={generating}
                    style={{ borderColor: overLimit ? 'var(--alert-red)' : 'var(--border-subtle)' }}
                  />
                  <span className="text-[9px] font-mono flex-shrink-0" style={{ color: overLimit ? 'var(--alert-red)' : 'var(--text-dim)' }}>
                    {wordCount}/15
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Negative prompt */}
      <div>
        <label className={labelCls}>Prompt negativo (partilhado)</label>
        <textarea
          className={inputCls}
          rows={2}
          value={negative}
          onChange={(e) => setNegative(e.target.value)}
          disabled={generating}
        />
      </div>

      {/* Advanced parameters */}
      <div className="rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between px-3 py-2 text-left transition-colors hover:bg-[var(--bg-hover)]"
        >
          <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
            ⚙ Parâmetros avançados
          </span>
          <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
            {showAdvanced ? '−' : '+'}
          </span>
        </button>
        {showAdvanced && (
          <div className="px-3 pb-3 flex flex-wrap gap-4">
            <div>
              <label className={labelCls}>Steps (4-20)</label>
              <input
                type="number" min={4} max={20}
                value={steps}
                onChange={(e) => setSteps(parseInt(e.target.value, 10) || 8)}
                disabled={generating}
                className="input-glow w-16 text-center text-[12px]"
              />
            </div>
            <div>
              <label className={labelCls}>CFG (1.0-3.0)</label>
              <input
                type="number" min={1} max={3} step={0.1}
                value={cfg}
                onChange={(e) => setCfg(parseFloat(e.target.value) || 1.5)}
                disabled={generating}
                className="input-glow w-16 text-center text-[12px]"
              />
            </div>
            <div>
              <label className={labelCls}>Seed (-1 = aleatório)</label>
              <input
                type="text"
                value={seed}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === '-' || v === '') { setSeed(-1); return; }
                  const n = parseInt(v, 10);
                  setSeed(isNaN(n) ? -1 : n);
                }}
                disabled={generating}
                className="input-glow w-28 text-center text-[12px]"
              />
            </div>
          </div>
        )}
      </div>

      {/* Generate button */}
      <button
        onClick={generateVideo}
        disabled={!imageFilename || prompts.length === 0 || generating}
        className="btn-glow px-6 py-3 rounded-lg font-mono text-[12px] font-bold tracking-wider uppercase transition-all duration-300"
        style={{
          opacity: (!imageFilename || prompts.length === 0 || generating) ? 0.4 : 1,
          cursor: (!imageFilename || prompts.length === 0 || generating) ? 'not-allowed' : 'pointer',
          background: 'var(--bg-card)',
          color: 'var(--cyber-blue)',
          border: '1px solid rgba(0,200,255,0.3)',
          boxShadow: (!imageFilename || prompts.length === 0 || generating) ? 'none' : '0 2px 12px rgba(0,200,255,0.15)',
        }}
      >
        {generating ? 'A gerar...' : '🎬 Gerar Video'}
      </button>

      {/* Status */}
      {statusMsg && (
        <div className="text-[11px] font-mono" style={{
          color: statusType === 'error' ? 'var(--alert-red)' : statusType === 'success' ? 'var(--matrix-green)' : 'var(--text-secondary)',
        }}>
          {statusMsg}
        </div>
      )}

      {/* Progress bar */}
      {generating && (
        <div className="space-y-1">
          {/* Sampling progress (value/max from ComfyUI) */}
          {progress && progress.max > 0 && (
            <>
              <div className="flex items-center justify-between text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                <span>A amostrar: {progress.value}/{progress.max} (step {progress.step})</span>
                <span className="animate-pulse">● KSampler</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.round((progress.value / progress.max) * 100)}%`,
                    background: 'linear-gradient(90deg, var(--cyber-blue), var(--matrix-green))',
                  }}
                />
              </div>
            </>
          )}
          {/* Node execution counter (fallback when no sampling progress) */}
          {wsNodeCount > 0 && (!progress || !progress.max) && (
            <>
              <div className="flex items-center justify-between text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                <span>Nodes executados: {wsNodeCount}</span>
                <span className="animate-pulse">● A processar...</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: '100%',
                    background: 'linear-gradient(90deg, var(--cyber-blue), var(--matrix-green))',
                  }}
                />
              </div>
            </>
          )}
          {/* Waiting state — WS connected but no events yet */}
          {wsNodeCount === 0 && (!progress || !progress.max) && (
            <div className="flex items-center justify-between text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
              <span className="animate-pulse">● À espera do ComfyUI...</span>
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {resultVideo && resultUrl && (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
          <div className="px-3 py-2 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>▶ Resultado</span>
            <div className="flex gap-2">
              <button
                onClick={sendToPool}
                className="btn-glow px-3 py-1 rounded font-mono text-[10px] tracking-wider border"
                style={{ background: 'var(--bg-secondary)', borderColor: 'var(--matrix-green)', color: 'var(--matrix-green)' }}
              >
                📦 Enviar para Media Pool
              </button>
              <button
                onClick={extendVideo}
                disabled={postProcessing}
                className="btn-glow px-3 py-1 rounded font-mono text-[10px] tracking-wider border"
                style={{ background: 'var(--bg-secondary)', borderColor: 'var(--amber-warn)', color: 'var(--amber-warn)', opacity: postProcessing ? 0.4 : 1 }}
              >
                ⏩ Extender Video
              </button>
            </div>
          </div>
          <video
            src={`${API_BASE}${resultUrl}`}
            controls
            className="w-full"
            style={{ display: 'block', maxHeight: 400 }}
          />
          <div className="px-3 py-2 text-[10px] font-mono" style={{ background: 'var(--bg-secondary)', color: 'var(--text-dim)' }}>
            {resultVideo}
          </div>
        </div>
      )}

      {/* Post-Process section — always available */}
      {!generating && (
        <div className="rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
          <div className="px-3 py-2 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
              ✦ Pós-processamento (RIFE + Upscale)
            </span>
          </div>
          <div className="px-3 py-3 flex flex-wrap items-end gap-4">
            <div>
              <label className={labelCls}>Vídeo de entrada</label>
              <div className="flex items-center gap-2">
                <input
                  type="file"
                  accept="video/*"
                  onChange={handlePpVideoUpload}
                  disabled={postProcessing}
                  className="text-[10px] font-mono"
                  style={{ maxWidth: 220 }}
                />
                {ppVideoFilename && (
                  <span className="text-[10px] font-mono" style={{ color: 'var(--matrix-green)' }}>✓ {ppVideoFilename}</span>
                )}
                {resultVideo && !ppVideoFilename && (
                  <span className="text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>→ usa vídeo gerado</span>
                )}
              </div>
            </div>
            <div>
              <label className={labelCls}>FPS (interpolação RIFE)</label>
              <select
                value={fps}
                onChange={(e) => setFps(parseInt(e.target.value, 10))}
                disabled={postProcessing}
                className="input-glow text-[12px] px-2 py-1.5"
              >
                <option value={16}>16 (nativo — sem interpolação)</option>
                <option value={32}>32 (RIFE 2x)</option>
                <option value={64}>64 (RIFE 4x)</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Upscale</label>
              <select
                value={upscale}
                onChange={(e) => setUpscale(parseInt(e.target.value, 10))}
                disabled={postProcessing}
                className="input-glow text-[12px] px-2 py-1.5"
              >
                <option value={1}>1x (original)</option>
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
            </div>
            <button
              onClick={runPostprocess}
              disabled={postProcessing || (fps === 16 && upscale === 1) || (!ppVideoFilename && !resultVideo)}
              className="btn-glow px-4 py-2 rounded-lg font-mono text-[11px] font-bold tracking-wider uppercase transition-all"
              style={{
                opacity: (postProcessing || (fps === 16 && upscale === 1) || (!ppVideoFilename && !resultVideo)) ? 0.4 : 1,
                cursor: (postProcessing || (fps === 16 && upscale === 1) || (!ppVideoFilename && !resultVideo)) ? 'not-allowed' : 'pointer',
                background: 'var(--bg-secondary)',
                color: 'var(--amber-warn)',
                border: '1px solid rgba(255,184,0,0.3)',
              }}
            >
              {postProcessing ? 'A processar...' : '✦ Melhorar Vídeo'}
            </button>
          </div>
          {(fps === 16 && upscale === 1) && (
            <div className="px-3 pb-2 text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>
              Seleciona FPS &gt; 16 ou Upscale &gt; 1x para ativar o pós-processamento.
            </div>
          )}
        </div>
      )}
    </div>
  );
}