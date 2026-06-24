import { useState, useRef, useCallback, useEffect } from 'react';

const API_BASE = window.location.origin;

function CascadeWaterInpaint({ onVideoToPool }) {
  const [imagePath, setImagePath] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [status, setStatus] = useState('idle');
  const [progressMsg, setProgressMsg] = useState('');
  const [brushSize, setBrushSize] = useState(20);
  const [maskDataUrl, setMaskDataUrl] = useState(null);

  // Parametros do efeito
  const [fallSpeed, setFallSpeed] = useState(2.0);
  const [foamIntensity, setFoamIntensity] = useState(0.7);
  const [streakDensity, setStreakDensity] = useState(30);
  const [blurAmount, setBlurAmount] = useState(3.0);
  const [duration, setDuration] = useState(10);
  const [fps, setFps] = useState(24);

  const imgCanvasRef = useRef(null);
  const maskCanvasRef = useRef(null);
  const imgRef = useRef(new Image());
  const isDrawing = useRef(false);

  // Upload da imagem
  const handleFile = async (file) => {
    if (!file || !file.type.startsWith('image/')) {
      setProgressMsg('Seleciona uma imagem valida.');
      return;
    }
    const reader = new FileReader();
    reader.onloadend = () => {
      setImagePreview(reader.result);
      const img = new Image();
      img.onload = () => {
        imgRef.current = img;
        drawImageAndInitMask(img);
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);

    // Upload para servidor
    setStatus('uploading');
    setProgressMsg('A fazer upload...');
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Upload falhou');
      setImagePath(data.path);
      setStatus('idle');
      setProgressMsg('Imagem pronta. Pinta a zona da cascata no canvas abaixo.');
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro upload: ${err.message}`);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (files?.length) handleFile(files[0]);
  };

  const handleFileInput = (e) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  };

  // Canvas setup
  const drawImageAndInitMask = (img) => {
    const imgCanvas = imgCanvasRef.current;
    const maskCanvas = maskCanvasRef.current;
    if (!imgCanvas || !maskCanvas) return;

    // Resize para max 800px width mantendo aspect ratio
    const maxW = 800;
    let w = img.width;
    let h = img.height;
    if (w > maxW) {
      h = Math.round((h * maxW) / w);
      w = maxW;
    }

    imgCanvas.width = w;
    imgCanvas.height = h;
    maskCanvas.width = w;
    maskCanvas.height = h;

    const ctx = imgCanvas.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);

    const mCtx = maskCanvas.getContext('2d');
    mCtx.fillStyle = '#000000';
    mCtx.fillRect(0, 0, w, h);

    setMaskDataUrl(null);
  };

  // Drawing na mascara
  const getPos = (e) => {
    const canvas = maskCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: ((clientX - rect.left) * canvas.width) / rect.width,
      y: ((clientY - rect.top) * canvas.height) / rect.height,
    };
  };

  const startDraw = (e) => {
    isDrawing.current = true;
    draw(e);
  };

  const endDraw = () => {
    isDrawing.current = false;
    const maskCanvas = maskCanvasRef.current;
    if (maskCanvas) setMaskDataUrl(maskCanvas.toDataURL('image/png'));
  };

  const draw = useCallback((e) => {
    if (!isDrawing.current) return;
    const canvas = maskCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const pos = getPos(e);
    ctx.globalCompositeOperation = 'source-over';
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, brushSize, 0, Math.PI * 2);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
  }, [brushSize]);

  // Limpar mascara
  const clearMask = () => {
    const canvas = maskCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    setMaskDataUrl(null);
  };

  // Enviar mascara como blob PNG para o servidor
  const uploadMask = async () => {
    const canvas = maskCanvasRef.current;
    if (!canvas) return null;
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/png'));
    const form = new FormData();
    form.append('file', new File([blob], 'mask.png', { type: 'image/png' }));
    const res = await fetch(`${API_BASE}/api/media/upload`, { method: 'POST', body: form });
    const data = await res.json();
    return data.success ? data.path : null;
  };

  // Gerar video
  const generate = async () => {
    if (!imagePath) {
      setProgressMsg('Faz upload da imagem primeiro.');
      return;
    }
    if (!maskDataUrl) {
      setProgressMsg('Pinta a zona da cascata na imagem primeiro (canvas branco).');
      return;
    }

    setStatus('running');
    setProgressMsg('A gerar mascara no servidor...');

    try {
      const maskPath = await uploadMask();
      if (!maskPath) throw new Error('Falha ao fazer upload da mascara');

      setProgressMsg('A renderizar cascata (Pillow + FFmpeg)...');
      const res = await fetch(`${API_BASE}/api/video/cascade/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_path: imagePath,
          mask_path: maskPath,
          duration: parseFloat(duration),
          fps: parseInt(fps),
          effects: [{
            name: 'cascading_water',
            params: {
              fall_speed: parseFloat(fallSpeed),
              foam_intensity: parseFloat(foamIntensity),
              streak_density: parseInt(streakDensity),
              blur_amount: parseFloat(blurAmount),
              water_color: '#4a7fb5',
            },
          }],
        }),
      });

      const data = await res.json();
      if (data.status === 'error') throw new Error(data.message);

      setStatus('done');
      setProgressMsg(`Video gerado: ${data.filename}`);
      if (onVideoToPool) onVideoToPool(data.filename);
    } catch (err) {
      setStatus('error');
      setProgressMsg(`Erro: ${err.message}`);
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop zone / Upload */}
      {!imagePreview && (
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed border-[var(--border-subtle)] rounded-xl p-8 text-center cursor-pointer hover:border-[var(--matrix-green)] transition-colors"
          onClick={() => document.getElementById('cascade-upload').click()}
        >
          <span className="text-4xl block mb-2">📁</span>
          <p className="text-sm font-mono" style={{ color: 'var(--text-muted)' }}>
            Arrasta imagem ou clica para carregar
          </p>
          <input id="cascade-upload" type="file" accept="image/*" className="hidden" onChange={handleFileInput} />
        </div>
      )}

      {imagePreview && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              Pinta de <strong>branco</strong> a zona da cascata
            </p>
            <button
              onClick={() => { setImagePreview(null); setImagePath(''); clearMask(); setStatus('idle'); }}
              className="text-xs font-mono px-2 py-1 rounded border hover:bg-[var(--bg-hover)]"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}
            >
              Substituir imagem
            </button>
          </div>

          {/* Canvas container */}
          <div className="relative inline-block">
            <canvas
              ref={imgCanvasRef}
              style={{ position: 'absolute', top: 0, left: 0, zIndex: 1 }}
              className="rounded-lg"
            />
            <canvas
              ref={maskCanvasRef}
              style={{ position: 'relative', zIndex: 2, cursor: 'crosshair', opacity: 0.65 }}
              className="rounded-lg"
              onMouseDown={startDraw}
              onMouseMove={draw}
              onMouseUp={endDraw}
              onMouseLeave={endDraw}
              onTouchStart={startDraw}
              onTouchMove={draw}
              onTouchEnd={endDraw}
            />
          </div>

          {/* Brush controls */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>Pincel:</span>
            <input
              type="range" min="5" max="80" value={brushSize}
              onChange={(e) => setBrushSize(parseInt(e.target.value))}
              className="w-24"
            />
            <span className="text-xs font-mono w-6">{brushSize}px</span>
            <button
              onClick={clearMask}
              className="text-xs font-mono px-2 py-1 rounded border hover:bg-[var(--bg-hover)]"
              style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}
            >
              Limpar mascara
            </button>
          </div>

          {/* Parameters */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Velocidade Queda</label>
              <input type="number" step="0.5" min="0.5" max="10" value={fallSpeed}
                onChange={(e) => setFallSpeed(parseFloat(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Espuma</label>
              <input type="number" step="0.1" min="0" max="1" value={foamIntensity}
                onChange={(e) => setFoamIntensity(parseFloat(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Streaks</label>
              <input type="number" step="5" min="0" max="100" value={streakDensity}
                onChange={(e) => setStreakDensity(parseInt(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Blur</label>
              <input type="number" step="0.5" min="0" max="10" value={blurAmount}
                onChange={(e) => setBlurAmount(parseFloat(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>Duracao (s)</label>
              <input type="number" step="1" min="1" max="60" value={duration}
                onChange={(e) => setDuration(parseInt(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>FPS</label>
              <input type="number" step="1" min="12" max="60" value={fps}
                onChange={(e) => setFps(parseInt(e.target.value))}
                className="w-full px-2 py-1 rounded text-xs font-mono bg-[var(--bg-primary)] border"
                style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}
              />
            </div>
          </div>

          {/* Generate button */}
          <button
            onClick={generate}
            disabled={status === 'running' || status === 'uploading'}
            className="w-full py-2 rounded-lg font-mono text-xs font-bold tracking-wider border transition-all"
            style={{
              background: 'var(--matrix-green)',
              color: '#000',
              borderColor: 'var(--matrix-green)',
              opacity: status === 'running' ? 0.6 : 1,
              cursor: status === 'running' ? 'not-allowed' : 'pointer',
            }}
          >
            {status === 'running' ? 'A RENDERIZAR...' : '🌊 GERAR CASCATA'}
          </button>

          {/* Status */}
          {progressMsg && (
            <p className="text-xs font-mono text-center" style={{ color: status === 'error' ? 'var(--alert-red)' : 'var(--cyber-blue)' }}>
              {progressMsg}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default CascadeWaterInpaint;
