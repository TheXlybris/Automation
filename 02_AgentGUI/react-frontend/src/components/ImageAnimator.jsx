import { useState, useRef, useEffect } from 'react';

const API_BASE = 'http://192.168.0.187:5021';  // ImageAnimator Windows Service (LAN)
const POLL_INTERVAL = 500; // ms
const MAX_POLL_TIME = 900000; // 15 min timeout

function ImageAnimator({ onVideoToPool, socket }) {
  const [imagePath, setImagePath] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | uploading | queued | running | done | error
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState('');
  const [resultVideo, setResultVideo] = useState(null);
  const [availableEffects, setAvailableEffects] = useState([]);
  const [activeEffects, setActiveEffects] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [errorDetail, setErrorDetail] = useState('');
  const [duration, setDuration] = useState(10);
  const [fps, setFps] = useState(24);
  const [useGpu, setUseGpu] = useState(true); // 🖥️ GPU Windows vs ⚡ CPU VM
  const pollRef = useRef(null);
  const pollStartRef = useRef(null);
  const dropRef = useRef(null);

  // Carregar efeitos disponíveis do backend
  useEffect(() => {
    fetch(`${API_BASE}/api/video/effects`)
      .then((r) => r.json())
      .then((data) => {
        if (data.effects) setAvailableEffects(data.effects);
      })
      .catch(() => setAvailableEffects([]));
  }, []);

  // Cleanup polling on unmount
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
    setProgressMsg('A fazer upload da imagem...');
    setErrorDetail('');
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
      setProgressMsg('Imagem pronta. Seleciona efeitos e clica Gerar.');
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro upload: ${err.message}`);
      setErrorDetail(err.message);
    }
  };

  const toggleEffect = (effectName) => {
    setActiveEffects((prev) => {
      const exists = prev.find((e) => e.name === effectName);
      if (exists) return prev.filter((e) => e.name !== effectName);
      const fx = availableEffects.find((e) => e.name === effectName);
      if (!fx) return prev;
      const clonedParams = JSON.parse(JSON.stringify(fx.params));
      return [...prev, { name: effectName, params: clonedParams }];
    });
  };

  const updateParam = (effectName, paramKey, value) => {
    setActiveEffects((prev) =>
      prev.map((e) => {
        if (e.name !== effectName) return e;
        if (Array.isArray(e.params[paramKey])) {
          const idx = parseInt(value.idx);
          const newArr = [...e.params[paramKey]];
          newArr[idx] = parseFloat(value.val);
          return { ...e, params: { ...e.params, [paramKey]: newArr } };
        }
        let parsed = value;
        if (typeof value === 'string' && value.trim() !== '') {
          parsed = isNaN(+value) ? value : +value;
        }
        return { ...e, params: { ...e.params, [paramKey]: parsed } };
      })
    );
  };

  const startPolling = (jid) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollStartRef.current = Date.now();
    pollRef.current = setInterval(async () => {
      // Timeout detection
      if (Date.now() - pollStartRef.current > MAX_POLL_TIME) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setStatus('error');
        setProgressMsg('Timeout: o servidor demorou demasiado tempo.');
        setErrorDetail('O job excedeu o tempo máximo de 5 minutos. Verifica o servidor.');
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/video/animate/status/${jid}`);
        const data = await res.json();
        if (data.status === 'done') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus('done');
          setProgress(100);
          setProgressMsg(data.message);
          setResultVideo(data.filename);
          if (onVideoToPool) onVideoToPool(data.filename);
        } else if (data.status === 'error') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setStatus('error');
          setProgress(0);
          setProgressMsg('Erro na geração do vídeo.');
          setErrorDetail(data.message || 'Erro desconhecido no servidor.');
        } else {
          setStatus('running');
          setProgress(Math.round((data.progress || 0) * 100));
          setProgressMsg(data.message || 'A processar...');
        }
      } catch (err) {
        // Keep polling on network errors
        setProgressMsg('A aguardar resposta do servidor...');
      }
    }, POLL_INTERVAL);
  };

  const generateVideo = async () => {
    if (!imagePath) { setProgressMsg('Seleciona uma imagem primeiro.'); return; }
    if (activeEffects.length === 0) { setProgressMsg('Seleciona pelo menos um efeito.'); return; }
    setResultVideo(null);
    setErrorDetail('');
    setStatus('queued');
    setProgress(0);
    setProgressMsg('A submeter job...');
    try {
      const res = await fetch(`${API_BASE}/api/video/animate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
        image_path: imagePath,
        effects: activeEffects,
        duration,
        fps,
        use_gpu: useGpu,
        }),
      });
      const data = await res.json();
      if (data.status === 'queued' && data.job_id) {
        setJobId(data.job_id);
        setStatus('running');
        setProgressMsg('Job submetido. A processar...');
        startPolling(data.job_id);
      } else {
        throw new Error(data.message || 'Falha ao submeter job');
      }
    } catch (err) {
      setStatus('error');
      setProgressMsg('Erro ao submeter job.');
      setErrorDetail(err.message);
    }
  };

  const cancelJob = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setStatus('idle');
    setProgress(0);
    setProgressMsg('Cancelado pelo utilizador.');
    setJobId(null);
  };

  const isRunning = status === 'running' || status === 'queued';

  // Render slider / input / color picker for param
  const renderParamControl = (effectName, key, value) => {
    const label = key.replace(/_/g, ' ').toUpperCase();
    // Color param detection
    if (typeof value === 'string' && value.startsWith('#')) {
      return (
        <div key={key} className="mb-1">
          <label className="block text-[9px] font-mono uppercase mb-0.5" style={{ color: 'var(--text-muted)' }}>{label}</label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={value}
              onChange={(e) => updateParam(effectName, key, e.target.value)}
              className="h-6 w-8 rounded border cursor-pointer"
              style={{ borderColor: 'var(--border-subtle)', background: 'transparent', padding: 0 }}
            />
            <input
              type="text"
              value={value}
              onChange={(e) => updateParam(effectName, key, e.target.value)}
              className="flex-1 rounded px-1 py-0.5 text-[10px] font-mono border"
              style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
            />
          </div>
        </div>
      );
    }
    // Array of hex colors (like fireflies color: ["#FFD700", "#00FFFF"])
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'string' && value[0].startsWith('#')) {
      return (
        <div key={key} className="mb-1">
          <label className="block text-[9px] font-mono uppercase mb-0.5" style={{ color: 'var(--text-muted)' }}>{label}</label>
          <div className="flex gap-2">
            {value.map((c, i) => (
              <div key={i} className="flex items-center gap-1">
                <input
                  type="color"
                  value={c}
                  onChange={(e) => {
                    const newArr = [...value];
                    newArr[i] = e.target.value;
                    updateParam(effectName, key, newArr);
                  }}
                  className="h-5 w-5 rounded border cursor-pointer"
                  style={{ borderColor: 'var(--border-subtle)', padding: 0 }}
                />
                <span className="text-[9px] font-mono" style={{ color: 'var(--text-dim)' }}>{i + 1}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    if (Array.isArray(value) && typeof value[0] === 'number') {
      const min = key.includes('zoom') || key.includes('brightness') ? 0.5 : -1;
      const max = key.includes('zoom') || key.includes('brightness') ? 3 : 1;
      const step = 0.01;
      return (
        <div key={key} className="mb-1">
          <label className="block text-[9px] font-mono uppercase mb-0.5" style={{ color: 'var(--text-muted)' }}>{label}</label>
          <div className="flex gap-1">
            {value.map((v, i) => (
              <input
                key={i}
                type="range" min={min} max={max} step={step}
                value={v}
                onChange={(e) => updateParam(effectName, key, { idx: i, val: e.target.value })}
                className="flex-1"
              />
            ))}
          </div>
          <div className="text-[9px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>
            [{value.map((v) => v.toFixed(2)).join(', ')}]
          </div>
        </div>
      );
    }
    if (typeof value === 'number') {
      const min = key === 'count' ? 1 : key === 'speed' || key === 'intensity' || key === 'glow' || key === 'density' || key === 'drift' || key === 'opacity' ? 0 : 0;
      const max = key === 'count' ? 200 :
                  key === 'speed' ? 5 :
                  key === 'ray_count' ? 12 :
                  key === 'intensity' || key === 'glow' || key === 'density' ? 1 :
                  key === 'opacity' ? 255 :
                  key === 'angle' ? 90 :
                  10;
      const step = key === 'count' || key === 'ray_count' || key === 'opacity' ? 1 : 0.01;
      return (
        <div key={key} className="mb-1">
          <label className="block text-[9px] font-mono uppercase mb-0.5" style={{ color: 'var(--text-muted)' }}>{label}</label>
          <input
            type="range" min={min} max={max} step={step}
            value={value}
            onChange={(e) => updateParam(effectName, key, e.target.value)}
            className="w-full"
          />
          <div className="text-[9px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{value}</div>
        </div>
      );
    }
    if (typeof value === 'boolean') {
      return (
        <div key={key} className="flex items-center gap-1 mb-1">
          <input
            type="checkbox"
            checked={value}
            onChange={(e) => updateParam(effectName, key, e.target.checked)}
          />
          <label className="text-[9px] font-mono" style={{ color: 'var(--text-muted)' }}>{label}</label>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-4">
      {/* Drop zone / Preview — alternam baseado no estado */}
      {!imagePreview ? (
        <div
          ref={dropRef}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}
          onClick={() => document.getElementById('ia-file-input').click()}
        >
          <div className="text-2xl mb-2">🖼️</div>
          <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            Arrasta imagem PNG aqui ou clica para selecionar
          </p>
          <input id="ia-file-input" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleFileInput} />
        </div>
      ) : (
        <div
          className="rounded-lg overflow-hidden border cursor-pointer relative group"
          style={{ borderColor: 'var(--border-subtle)' }}
          onClick={() => document.getElementById('ia-file-input').click()}
          title="Clica para substituir a imagem"
        >
          <img
            src={imagePreview}
            alt="Preview"
            className="w-full object-contain"
            style={{ maxHeight: 350, minHeight: 120 }}
          />
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
               style={{ background: 'rgba(0,0,0,0.5)' }}>
            <span className="text-xs font-mono font-bold text-white">🖼️ CLICA PARA SUBSTITUIR</span>
          </div>
          <input id="ia-file-input" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleFileInput} />
        </div>
      )}

      {imagePath && (
        <div className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
          Imagem: {imagePath.split(/[\\/]/).pop()}
        </div>
      )}

      {/* Global settings */}
      <div className="flex gap-4 items-end">
        <div className="flex-1">
          <label className="block text-[9px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>DURAÇÃO (s)</label>
          <input type="range" min="1" max="30" step="1" value={duration} onChange={(e) => setDuration(parseInt(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{duration}s</div>
        </div>
        <div className="flex-1">
          <label className="block text-[9px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>FPS</label>
          <input type="range" min="12" max="60" step="1" value={fps} onChange={(e) => setFps(parseInt(e.target.value))} className="w-full" />
          <div className="text-[10px] font-mono text-right" style={{ color: 'var(--matrix-green)' }}>{fps}</div>
        </div>
      </div>

      {/* Effects grid — 3 columns */}
      <div>
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>EFEITOS</h3>
        {availableEffects.length === 0 && (
          <p className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>A carregar efeitos...</p>
        )}
        <div className="grid grid-cols-3 gap-2">
          {availableEffects.map((fx) => {
            const isActive = !!activeEffects.find((e) => e.name === fx.name);
            const activeCfg = activeEffects.find((e) => e.name === fx.name);
            return (
              <div
                key={fx.name}
                className="rounded-lg border overflow-hidden"
                style={{
                  borderColor: isActive ? 'var(--matrix-green)' : 'var(--border-subtle)',
                  background: isActive ? 'var(--bg-card)' : 'rgba(255,255,255,0.02)',
                }}
              >
                <button
                  onClick={() => toggleEffect(fx.name)}
                  className="w-full flex items-center justify-between px-3 py-2 text-left"
                >
                  <span className="flex items-center gap-2">
                    <span className="text-sm">{isActive ? '☑' : '☐'}</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider" style={{ color: isActive ? 'var(--matrix-green)' : 'var(--text-muted)' }}>
                      {fx.name.replace(/_/g, ' ')}
                    </span>
                  </span>
                  <span className="text-[8px] font-mono" style={{ color: 'var(--text-dim)' }}>{isActive ? 'ON' : 'OFF'}</span>
                </button>
                {isActive && activeCfg?.params && (
                  <div className="px-3 pb-2 space-y-1 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                    {Object.entries(activeCfg.params).map(([k, v]) =>
                      renderParamControl(fx.name, k, v)
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Toggle CPU / GPU */}
      <div className="flex items-center gap-3 rounded-lg border p-2" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
        <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Motor:</span>
        <button
          onClick={() => setUseGpu(false)}
          className="px-2 py-1 rounded text-[10px] font-mono font-bold border transition-all"
          style={{
            borderColor: !useGpu ? 'var(--amber-warn)' : 'var(--border-subtle)',
            color: !useGpu ? 'var(--amber-warn)' : 'var(--text-muted)',
            background: !useGpu ? 'rgba(255,184,0,0.08)' : 'transparent',
          }}
        >
          ⚡ CPU (VM)
        </button>
        <button
          onClick={() => setUseGpu(true)}
          className="px-2 py-1 rounded text-[10px] font-mono font-bold border transition-all"
          style={{
            borderColor: useGpu ? 'var(--cyber-blue)' : 'var(--border-subtle)',
            color: useGpu ? 'var(--cyber-blue)' : 'var(--text-muted)',
            background: useGpu ? 'rgba(0,212,255,0.08)' : 'transparent',
          }}
        >
          🖥️ GPU (Windows)
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={generateVideo}
          disabled={isRunning || !imagePath || activeEffects.length === 0}
          className="px-4 py-2 rounded-lg text-xs font-mono font-bold tracking-wider border transition-all"
          style={{
            borderColor: isRunning || !imagePath || activeEffects.length === 0 ? 'var(--text-dim)' : 'var(--matrix-green)',
            color: isRunning || !imagePath || activeEffects.length === 0 ? 'var(--text-dim)' : 'var(--matrix-green)',
            background: isRunning || !imagePath || activeEffects.length === 0 ? 'var(--bg-secondary)' : 'rgba(0,255,65,0.08)',
            opacity: isRunning || !imagePath || activeEffects.length === 0 ? 0.6 : 1,
            cursor: isRunning || !imagePath || activeEffects.length === 0 ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? '⏳ A GERAR...' : '🎬 GERAR VÍDEO'}
        </button>

        {isRunning && (
          <button
            onClick={cancelJob}
            className="px-3 py-2 rounded-lg text-xs font-mono border"
            style={{ borderColor: 'var(--alert-red)', color: 'var(--alert-red)', background: 'rgba(255,59,48,0.08)' }}
          >
            ✕ CANCELAR
          </button>
        )}
      </div>

      {/* Progress bar */}
      {(status === 'running' || status === 'queued') && (
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>{progressMsg}</span>
            <span className="text-[10px] font-mono" style={{ color: 'var(--matrix-green)' }}>{progress}%</span>
          </div>
          <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${progress}%`,
                background: 'var(--matrix-green)',
              }}
            />
          </div>
        </div>
      )}

      {status === 'running' && progressMsg?.includes('Windows') && (
        <div className="flex items-center gap-2 text-[10px] font-mono" style={{ color: 'var(--cyber-blue)' }}>
          <span>🖥️ GPU WINDOWS</span>
        </div>
      )}
      {progressMsg && status !== 'running' && status !== 'queued' && (
        <div className="rounded-lg p-3 text-xs font-mono border" style={{
          background: status === 'error' ? 'rgba(255,59,48,0.08)' : status === 'done' ? 'rgba(0,255,65,0.08)' : 'var(--bg-card)',
          borderColor: status === 'error' ? 'var(--alert-red)' : status === 'done' ? 'var(--matrix-green)' : 'var(--border-subtle)',
          color: status === 'error' ? 'var(--alert-red)' : status === 'done' ? 'var(--matrix-green)' : 'var(--text-secondary)',
        }}>
          {progressMsg}
        </div>
      )}

      {/* Error detail */}
      {errorDetail && (
        <div className="rounded-lg p-3 text-[10px] font-mono border" style={{
          background: 'rgba(255,59,48,0.05)',
          borderColor: 'var(--alert-red)',
          color: 'var(--alert-red)',
        }}>
          <div className="font-bold mb-1">⚠ ERRO:</div>
          {errorDetail}
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

export default ImageAnimator;
