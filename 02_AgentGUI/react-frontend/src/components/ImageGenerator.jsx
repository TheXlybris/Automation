import { useState, useEffect, useRef } from 'react';

const API_BASE = window.location.origin;

export default function ImageGenerator({ onImageGenerated }) {
  const [workflows, setWorkflows] = useState([]);
  const [workflow, setWorkflow] = useState('realistic');
  const [prompt, setPrompt] = useState(() => localStorage.getItem('imggen_prompt') || '');
  const [negative, setNegative] = useState(() => localStorage.getItem('imggen_negative') || '');
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(576);
  const [steps, setSteps] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [seed, setSeed] = useState(-1);
  const [batchSize, setBatchSize] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [statusType, setStatusType] = useState('');
  const [results, setResults] = useState([]);
  const [defaults, setDefaults] = useState({});
  const [elapsed, setElapsed] = useState(0);
  const [progress, setProgress] = useState({ step: 0, totalSteps: 0, node: '', status: '' });
  const pollRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/image/workflows`)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          setWorkflows(data);
          const def = data.find(w => w.key === 'realistic');
          if (def) {
            setDefaults(def.defaults || {});
            setWidth(def.defaults?.width || 1024);
            setHeight(def.defaults?.height || 576);
          }
        }
      })
      .catch(e => console.error('Erro ao buscar workflows:', e));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const handleWorkflowChange = (key) => {
    setWorkflow(key);
    const wf = workflows.find(w => w.key === key);
    if (wf?.defaults) {
      setDefaults(wf.defaults);
      setWidth(wf.defaults.width || 1024);
      setHeight(wf.defaults.height || 576);
      setSteps(null);
      setCfg(null);
    }
  };

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const generate = async () => {
    if (!prompt.trim()) return;
    setGenerating(true);
    setStatusMsg('A submeter ao ComfyUI...');
    setStatusType('info');
    setResults([]);
    setElapsed(0);
    setProgress({ step: 0, totalSteps: 0, node: '', status: 'queued' });

    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(((Date.now() - startTime) / 1000).toFixed(1));
    }, 100);

    try {
      const body = {
        workflow,
        prompt,
        negative: negative || undefined,
        width: parseInt(width, 10),
        height: parseInt(height, 10),
        steps: steps ? parseInt(steps, 10) : undefined,
        cfg: cfg ? parseFloat(cfg) : undefined,
        seed: parseInt(seed, 10),
        batch_size: parseInt(batchSize, 10),
      };

      const res = await fetch(`${API_BASE}/api/image/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (data.error) {
        setStatusMsg(`Erro: ${data.error}`);
        setStatusType('error');
        setGenerating(false);
        stopPolling();
        return;
      }

      if (data.success) {
        const promptId = data.prompt_id;
        const totalSteps = data.total_steps;
        setProgress({ step: 0, totalSteps, node: '', status: 'queued' });
        setStatusMsg('Na fila do ComfyUI...');

        // Start polling for status
        pollRef.current = setInterval(async () => {
          try {
            const sRes = await fetch(`${API_BASE}/api/image/status/${promptId}`);
            const sData = await sRes.json();

            if (sData.status === 'done' && sData.images?.length > 0) {
              stopPolling();
              setGenerating(false);
              setResults(sData.images);
              const finalElapsed = ((Date.now() - startTime) / 1000).toFixed(1);
              setStatusMsg(`Imagem gerada (${finalElapsed}s) — seed: ${data.seed}`);
              setStatusType('success');
              setProgress({ step: totalSteps, totalSteps, node: '', status: 'done' });
              if (onImageGenerated && sData.images[0]) {
                onImageGenerated({
                  url: sData.images[0].url,
                  filename: sData.images[0].filename,
                  seed: data.seed,
                });
              }
            } else if (sData.status === 'error') {
              stopPolling();
              setGenerating(false);
              setStatusMsg('Erro na execução do workflow no ComfyUI');
              setStatusType('error');
            } else if (sData.status === 'running') {
              const step = sData.step || 0;
              const max = sData.total_steps || totalSteps;
              const node = sData.node || '';
              setProgress({ step, totalSteps: max, node, status: 'running' });
              setStatusMsg(`A gerar — step ${step}/${max}${node ? ` (nó: ${node})` : ''}`);
            } else if (sData.status === 'queued') {
              setStatusMsg(`Na fila do ComfyUI... (posição: ${sData.queue_position || '?'})`);
            }
          } catch (err) {
            console.error('Poll error:', err);
          }
        }, 1000);
      }
    } catch (err) {
      setStatusMsg(`Erro de ligação: ${err.message}`);
      setStatusType('error');
      setGenerating(false);
      stopPolling();
    }
  };

  const inputCls = 'input-glow w-full text-[12px]';
  const labelCls = 'text-[10px] text-[var(--text-dim)] block mb-1.5 font-mono';

  // Real progress percentage: step / totalSteps * 100, capped at 99 while running
  const progressPct = progress.totalSteps > 0
    ? Math.min(progress.status === 'done' ? 100 : 99, (progress.step / progress.totalSteps) * 100)
    : 0;

  return (
    <div>
      {/* Prompt */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label className={labelCls}>Prompt (positivo)</label>
          <textarea
            className={inputCls}
            rows={4}
            placeholder="Descreve a imagem que queres gerar..."
            value={prompt}
            onChange={e => { setPrompt(e.target.value); localStorage.setItem('imggen_prompt', e.target.value); }}
            disabled={generating}
          />
        </div>
        <div>
          <label className={labelCls}>Prompt negativo (opcional)</label>
          <textarea
            className={inputCls}
            rows={4}
            placeholder="text, watermark, ugly, blurry..."
            value={negative}
            onChange={e => { setNegative(e.target.value); localStorage.setItem('imggen_negative', e.target.value); }}
            disabled={generating}
          />
        </div>
      </div>

      {/* Settings row */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div>
          <label className={labelCls}>Workflow</label>
          <select
            value={workflow}
            onChange={e => handleWorkflowChange(e.target.value)}
            disabled={generating}
            className="input-glow text-[12px] px-3 py-2"
          >
            {workflows.map(w => (
              <option key={w.key} value={w.key}>{w.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelCls}>Largura</label>
          <input
            type="number" min={256} max={2048} step={64}
            value={width}
            onChange={e => setWidth(e.target.value)}
            disabled={generating}
            className="input-glow w-20 text-center text-[12px]"
          />
        </div>
        <div>
          <label className={labelCls}>Altura</label>
          <input
            type="number" min={256} max={2048} step={64}
            value={height}
            onChange={e => setHeight(e.target.value)}
            disabled={generating}
            className="input-glow w-20 text-center text-[12px]"
          />
        </div>

        <div>
          <label className={labelCls}>Steps ({defaults.steps || '?'})</label>
          <input
            type="number" min={1} max={150}
            value={steps || ''}
            placeholder={defaults.steps?.toString() || ''}
            onChange={e => setSteps(e.target.value ? parseInt(e.target.value, 10) : null)}
            disabled={generating}
            className="input-glow w-16 text-center text-[12px]"
          />
        </div>

        <div>
          <label className={labelCls}>CFG ({defaults.cfg || '?'})</label>
          <input
            type="number" min={1} max={20} step={0.5}
            value={cfg || ''}
            placeholder={defaults.cfg?.toString() || ''}
            onChange={e => setCfg(e.target.value ? parseFloat(e.target.value) : null)}
            disabled={generating}
            className="input-glow w-16 text-center text-[12px]"
          />
        </div>

        <div>
          <label className={labelCls}>Seed (-1 = aleatório)</label>
          <input
            type="text"
            value={seed}
            onChange={e => {
              const v = e.target.value;
              if (v === '-' || v === '') { setSeed(-1); return; }
              const n = parseInt(v, 10);
              setSeed(isNaN(n) ? -1 : n);
            }}
            disabled={generating}
            className="input-glow w-28 text-center text-[12px]"
          />
        </div>

        <div>
          <label className={labelCls}>Batch</label>
          <input
            type="number" min={1} max={8}
            value={batchSize}
            onChange={e => setBatchSize(parseInt(e.target.value, 10) || 1)}
            disabled={generating}
            className="input-glow w-16 text-center text-[12px]"
          />
        </div>
      </div>

      {/* Generate button */}
      <button
        onClick={generate}
        disabled={!prompt.trim() || generating}
        className="btn-glow px-6 py-3 rounded-lg font-mono text-[12px] font-bold tracking-wider uppercase transition-all duration-300 mb-4"
        style={{
          opacity: (!prompt.trim() || generating) ? 0.4 : 1,
          cursor: (!prompt.trim() || generating) ? 'not-allowed' : 'pointer',
          background: 'var(--bg-card)',
          color: 'var(--amber-warn)',
          border: '1px solid rgba(255,184,0,0.3)',
          boxShadow: (!prompt.trim() || generating) ? 'none' : '0 2px 12px rgba(255,184,0,0.15)',
        }}
      >
        {generating ? 'A gerar...' : 'Gerar Imagem'}
      </button>

      {/* Progress bar — real progress from ComfyUI WebSocket */}
      {generating && (
        <div className="mb-4">
          <div className="flex justify-between text-[10px] font-mono mb-1">
            <span style={{ color: 'var(--text-muted)' }}>
              {statusMsg}
            </span>
            <span style={{ color: 'var(--amber-warn)' }}>
              {elapsed}s
            </span>
          </div>
          <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${progressPct}%`,
                background: 'linear-gradient(90deg, var(--amber-warn), #ff8c00)',
                boxShadow: '0 0 10px rgba(255,184,0,0.4)',
              }}
            />
          </div>
          {progress.totalSteps > 0 && (
            <div className="text-[10px] font-mono mt-1" style={{ color: 'var(--text-dim)' }}>
              {progress.step}/{progress.totalSteps} steps{progress.node ? ` — nó: ${progress.node}` : ''}
            </div>
          )}
        </div>
      )}

      {/* Status (non-generating) */}
      {!generating && statusMsg && (
        <div className="text-[11px] font-mono mb-4" style={{
          color: statusType === 'error' ? 'var(--alert-red)' : statusType === 'success' ? 'var(--matrix-green)' : 'var(--text-secondary)',
        }}>
          {statusMsg}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {results.map((img, i) => (
            <div key={i} className="rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border-subtle)' }}>
              <img
                src={img.url}
                alt={`Generated ${i + 1}`}
                className="w-full"
                style={{ display: 'block' }}
              />
              <div className="px-3 py-2 text-[10px] font-mono text-[var(--text-dim)] flex items-center justify-between" style={{ background: 'var(--bg-secondary)' }}>
                <span>{img.filename}</span>
                <a
                  href={img.url}
                  download={img.filename}
                  className="text-[var(--cyber-blue)] hover:underline"
                >
                  Download
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}