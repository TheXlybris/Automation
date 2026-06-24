import { useState, useRef, useEffect } from 'react';

const API_BASE = window.location.origin;

function VideoGenerator({ onVideoToPool, socket }) {
  const [imagePath, setImagePath] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [imagePrompt, setImagePrompt] = useState('');
  const [videoPrompt, setVideoPrompt] = useState('');
  const [translate, setTranslate] = useState(true);
  const [strength, setStrength] = useState(0.15);
  const [length, setLength] = useState(153);
  const [seed, setSeed] = useState(-1);
  const [steps, setSteps] = useState(50);
  const [cfg, setCfg] = useState(3.0);
  const [status, setStatus] = useState('idle'); // idle | uploading | submitted | running | completed | fetching | done | error
  const [jobId, setJobId] = useState(null);
  const [progressMsg, setProgressMsg] = useState('');
  const [resultVideo, setResultVideo] = useState(null);
  const pollRef = useRef(null);
  const dropRef = useRef(null);

  const clearJob = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setJobId(null);
    setStatus('idle');
    setProgressMsg('');
    setResultVideo(null);
    setImagePreview(null);
    setImagePath('');
  };

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleDrop = async (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (!files || !files.length) return;
    await uploadImage(files[0]);
  };

  const handleFileInput = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    await uploadImage(file);
  };

  const uploadImage = async (file) => {
    setStatus('uploading');
    setProgressMsg('Upload da imagem...');
    // Preview local antes do upload
    const reader = new FileReader();
    reader.onloadend = () => setImagePreview(reader.result);
    reader.readAsDataURL(file);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Upload falhou');
      setImagePath(data.path);
      setStatus('idle');
      setProgressMsg('Imagem pronta. Preenche o prompt e clica Gerar.');
      // Metadata extraction desativado — endpoint nao implementado
      // extractMetadata(data.path);
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro upload: ${err.message}`);
    }
  };

  const extractMetadata = async (path) => {
    try {
      const res = await fetch(`${API_BASE}/api/comfy/image/metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_path: path })
      });
      if (!res.ok) return;
      const data = await res.json();
      if (data.prompt) {
        setImagePrompt(data.prompt);
        if (translate) {
          // Frontend não traduz — envia para o backend traduzir no generate
        }
      }
    } catch (e) { /* ignore */ }
  };

  const generateVideo = async () => {
    if (!imagePath) {
      setProgressMsg('Seleciona uma imagem primeiro.');
      return;
    }
    clearJob();
    setStatus('submitted');
    setProgressMsg('A submeter job para ComfyUI...');
    try {
      const res = await fetch(`${API_BASE}/api/comfy/video/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_path: imagePath,
          image_prompt: imagePrompt,
          video_prompt: videoPrompt || undefined,
          negative: "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, artifacts, fused fingers, bad anatomy, weird hand, ugly",
          strength, length, seed, steps, cfg, translate
        })
      });
      const data = await res.json();
      if (data.status === 'error') throw new Error(data.message);
      setJobId(data.prompt_id);
      setStatus('running');
      setProgressMsg(`Job ${data.prompt_id} em execução...`);
      startPolling(data.prompt_id);
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro: ${err.message}`);
    }
  };

  const startPolling = (pid) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/comfy/video/status/${pid}`);
        const data = await res.json();
        if (data.status === 'completed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus('fetching');
          setProgressMsg('Vídeo pronto. A copiar para o Media Pool...');
          const v = data.videos?.[0];
          if (v) {
            await fetchToPool(v.filename, v.subfolder);
          } else {
            setStatus('error');
            setProgressMsg('Completado mas nenhum vídeo encontrado.');
          }
        } else if (data.status === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus('error');
          setProgressMsg(`Erro ComfyUI: ${data.message || 'unknown'}`);
        } else {
          setProgressMsg(`Em execução... (${data.status})`);
        }
      } catch (err) {
        // keep polling
      }
    }, 3000);
  };

  const fetchToPool = async (filename, subfolder) => {
    try {
      const res = await fetch(`${API_BASE}/api/comfy/video/fetch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, subfolder })
      });
      const data = await res.json();
      if (data.success) {
        setStatus('done');
        setProgressMsg(`Vídeo no Media Pool: ${data.filename}`);
        setResultVideo(data.filename);
        if (onVideoToPool) onVideoToPool(data.filename);
      } else {
        throw new Error(data.error || 'Fetch falhou');
      }
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro fetch: ${err.message}`);
    }
  };

  const isRunning = status === 'running' || status === 'submitted' || status === 'fetching';

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        ref={dropRef}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}
        onClick={() => document.getElementById('vg-file-input').click()}
      >
        <div className="text-2xl mb-2">🖼️</div>
        <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          Arrasta imagem PNG aqui ou clica para selecionar
        </p>
        <input id="vg-file-input" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleFileInput} />
      </div>

      {imagePreview && (
        <div className="rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
          <img src={imagePreview} alt="Preview" className="w-full object-contain" style={{ maxHeight: 200 }} />
        </div>
      )}

      {imagePath && (
        <div className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          Imagem: {imagePath.split(/[\\/]/).pop()}
        </div>
      )}

      {/* Prompts */}
      <div>
        <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Prompt da Imagem</label>
        <textarea
          className="w-full rounded-lg p-2 text-xs font-mono border"
          style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)', minHeight: 60 }}
          value={imagePrompt}
          onChange={(e) => setImagePrompt(e.target.value)}
          placeholder="Prompt original da imagem (auto-extrai se PNG ComfyUI)"
        />
      </div>

      <div className="flex items-center gap-2">
        <input type="checkbox" id="vg-translate" checked={translate} onChange={(e) => setTranslate(e.target.checked)} />
        <label htmlFor="vg-translate" className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>
          Traduzir prompt para movimento de vídeo
        </label>
      </div>

      {!translate && (
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Prompt do Vídeo (manual)</label>
          <textarea
            className="w-full rounded-lg p-2 text-xs font-mono border"
            style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)', minHeight: 60 }}
            value={videoPrompt}
            onChange={(e) => setVideoPrompt(e.target.value)}
            placeholder="Prompt específico para vídeo (ignora tradução)"
          />
        </div>
      )}

      {/* Parameters */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Strength</label>
          <input type="range" min="0" max="1" step="0.01" value={strength} onChange={(e) => setStrength(parseFloat(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{strength.toFixed(2)}</div>
        </div>
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Frames</label>
          <input type="range" min="25" max="257" step="1" value={length} onChange={(e) => setLength(parseInt(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{length}</div>
        </div>
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Steps</label>
          <input type="range" min="20" max="100" step="1" value={steps} onChange={(e) => setSteps(parseInt(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{steps}</div>
        </div>
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>CFG</label>
          <input type="range" min="1" max="10" step="0.1" value={cfg} onChange={(e) => setCfg(parseFloat(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{cfg.toFixed(1)}</div>
        </div>
        <div>
          <label className="block text-[10px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Seed</label>
          <input
            type="number" value={seed} onChange={(e) => setSeed(parseInt(e.target.value))}
            className="w-full rounded p-1 text-xs font-mono border"
            style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
          />
          <div className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>-1 = aleatório</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={generateVideo}
          disabled={isRunning || !imagePath}
          className="px-4 py-2 rounded-lg text-xs font-mono font-bold tracking-wider border transition-all"
          style={{
            borderColor: isRunning || !imagePath ? 'var(--text-dim)' : 'var(--cyber-blue)',
            color: isRunning || !imagePath ? 'var(--text-dim)' : 'var(--cyber-blue)',
            background: isRunning || !imagePath ? 'var(--bg-secondary)' : 'rgba(0,212,255,0.08)',
            opacity: isRunning || !imagePath ? 0.6 : 1,
            cursor: isRunning || !imagePath ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? '⏳ A GERAR...' : '🎬 GERAR VÍDEO'}
        </button>
        {isRunning && (
          <button
            onClick={clearJob}
            className="px-3 py-2 rounded-lg text-xs font-mono border"
            style={{ borderColor: 'var(--alert-red)', color: 'var(--alert-red)', background: 'rgba(255,59,48,0.08)' }}
          >
            ✕ Cancelar
          </button>
        )}
      </div>

      {/* Status */}
      {progressMsg && (
        <div className="rounded-lg p-3 text-xs font-mono border" style={{
          background: status === 'error' ? 'rgba(255,59,48,0.08)' : status === 'done' ? 'rgba(0,255,65,0.08)' : 'var(--bg-card)',
          borderColor: status === 'error' ? 'var(--alert-red)' : status === 'done' ? 'var(--matrix-green)' : 'var(--border-subtle)',
          color: status === 'error' ? 'var(--alert-red)' : status === 'done' ? 'var(--matrix-green)' : 'var(--text-secondary)',
        }}>
          {progressMsg}
        </div>
      )}

      {/* Result */}
      {resultVideo && (
        <div className="rounded-lg p-3 border" style={{ borderColor: 'var(--matrix-green)', background: 'rgba(0,255,65,0.05)' }}>
          <div className="text-[10px] font-mono mb-2" style={{ color: 'var(--matrix-green)' }}>✓ Vídeo no Media Pool</div>
          <video controls className="w-full rounded" style={{ maxHeight: 200 }}>
            <source src={`${API_BASE}/api/media/file/${encodeURIComponent(resultVideo)}`} />
          </video>
        </div>
      )}
    </div>
  );
}

export default VideoGenerator;
