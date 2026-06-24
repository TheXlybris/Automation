import { useState, useEffect } from 'react';

// ─── Model capabilities (from Ollama model cards + empirical knowledge) ───
const MODEL_TAGS = {
  // Cloud
  'kimi-k2.6':           { type: 'cloud',  strengths: ['reasoning', 'tool-calling', 'long-context', 'general'], note: 'Melhor geral' },
  'glm-5.2':             { type: 'cloud',  strengths: ['reasoning', 'instructions', 'general', 'fast'], note: 'Bom a seguir regras' },
  'deepseek-v4-pro':     { type: 'cloud',  strengths: ['reasoning', 'code', 'analysis', 'general'], note: 'Forte em análise' },
  'qwen3-coder:480b':    { type: 'cloud',  strengths: ['code', 'reasoning'], note: 'Especialista em código' },
  // Local — general purpose (todos podem fazer qualquer tarefa, com qualidade variável)
  'qwen2.5-coder:7b':    { type: 'local',  strengths: ['code', 'fast'], note: 'Rápido para código' },
  'qwen2.5-coder:latest':{ type: 'local',  strengths: ['code', 'fast'], note: 'Rápido para código' },
  'qwen3:8b':            { type: 'local',  strengths: ['reasoning', 'general', 'tool-calling'], note: 'Bom geral local' },
  'gemma4:26b':          { type: 'local',  strengths: ['reasoning', 'general'], note: 'Melhor raciocínio local (16GB VRAM limit)' },
  'gemma4:e2b':          { type: 'local',  strengths: ['general', 'lightweight'], note: 'Leve e rápido' },
  'gemma4-12b:q4':       { type: 'local',  strengths: ['general', 'lightweight'], note: 'Leve' },
  'llama3.1:8b':         { type: 'local',  strengths: ['general', 'chat'], note: 'Chat geral' },
  'phi3:mini':           { type: 'local',  strengths: ['lightweight', 'fast'], note: 'Muito leve — tarefas simples' },
  'qwen3-vl:30b-a3b-instruct': { type: 'local', strengths: ['vision', 'multimodal', 'reasoning'], note: 'Visão multimodal' },
  'qwen35-a3b:latest':   { type: 'local',  strengths: ['reasoning', 'general'], note: 'Raciocínio local' },
  'qwen3.5:35b-a3b':     { type: 'local',  strengths: ['reasoning', 'general'], note: 'Raciocínio local' },
};

// ─── Profile characteristics ───
const PROFILE_INFO = {
  orchestrator: { name: 'Orquestrador', focus: 'Coordenação + tool calling', needs: ['reasoning', 'tool-calling', 'general'] },
  developer:     { name: 'Developer', focus: 'Código + debugging', needs: ['code', 'reasoning', 'general'] },
  multimedia:    { name: 'Multimedia', focus: 'Geração de mídia + ComfyUI', needs: ['general', 'reasoning', 'instructions'] },
  researcher:    { name: 'Researcher', focus: 'Pesquisa + síntese', needs: ['reasoning', 'general', 'long-context'] },
  wiki:          { name: 'Wiki', focus: 'Gestão de wiki + markdown', needs: ['instructions', 'general', 'reasoning'] },
  dreamer:       { name: 'Dreamer', focus: 'Auditoria + auto-melhoria', needs: ['reasoning', 'analysis', 'general'] },
};

function scoreModel(modelId, profileId) {
  const tags = MODEL_TAGS[modelId];
  if (!tags) return 0;
  const info = PROFILE_INFO[profileId];
  if (!info) return tags.strengths.length * 2; // unknown profile — generic score

  let score = 0;
  const reasons = [];

  // 1. Base score: every model can do any task (quality varies)
  score += 5;
  reasons.push('base 5');

  // 2. Need matching: +15 per matching strength
  for (const need of info.needs) {
    if (tags.strengths.includes(need)) {
      score += 15;
      reasons.push(`${need} +15`);
    }
  }

  // 3. Quality bonus: reasoning-capable models get boost for complex profiles
  if (tags.strengths.includes('reasoning')) {
    if (['orchestrator', 'developer', 'researcher', 'dreamer'].includes(profileId)) {
      score += 10;
      reasons.push('reasoning+complex +10');
    }
  }

  // 4. Tool calling bonus for orchestrator
  if (tags.strengths.includes('tool-calling') && profileId === 'orchestrator') {
    score += 20;
    reasons.push('tool-calling+orch +20');
  }

  // 5. Code bonus for developer
  if (tags.strengths.includes('code') && profileId === 'developer') {
    score += 25;
    reasons.push('code+dev +25');
  }

  // 6. Instructions bonus for wiki
  if (tags.strengths.includes('instructions') && profileId === 'wiki') {
    score += 20;
    reasons.push('instructions+wiki +20');
  }

  // 7. Cloud gets small bonus for complex tasks (better quality)
  if (tags.type === 'cloud' && ['orchestrator', 'developer', 'dreamer', 'researcher'].includes(profileId)) {
    score += 8;
    reasons.push('cloud+complex +8');
  }

  // 8. Lightweight penalty for complex profiles (can do it but not ideal)
  if (tags.strengths.includes('lightweight') && ['orchestrator', 'developer', 'researcher', 'dreamer'].includes(profileId)) {
    score -= 10;
    reasons.push('lightweight-complex -10');
  }

  // 9. VRAM check: gemma4:26b needs >16GB, add warning penalty
  if (modelId === 'gemma4:26b') {
    score -= 5;
    reasons.push('VRAM>16GB -5');
  }

  return { score, reasons };
}

export default function ModelRecommendations({ socket }) {
  const [models, setModels] = useState([]);
  const [configs, setConfigs] = useState({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [justApplied, setJustApplied] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const modelsRes = await fetch(`${window.location.origin}/api/models`).then(r => r.json());
        setModels(modelsRes.models || []);

        const configMap = {};
        await Promise.all(Object.keys(PROFILE_INFO).map(async (id) => {
          try {
            const r = await fetch(`${window.location.origin}/api/profiles/${id}/config`);
            if (r.ok) configMap[id] = (await r.json()).model || null;
          } catch {}
        }));
        setConfigs(configMap);
        setLoading(false);
      } catch (e) {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getRecommendations = (profileId) => {
    const recs = models.map(m => {
      const { score, reasons } = scoreModel(m.id, profileId);
      const tags = MODEL_TAGS[m.id] || { type: m.source, strengths: [], note: '' };
      return { ...m, score, tags, reasons };
    }).sort((a, b) => b.score - a.score);
    return recs;
  };

  const applyModel = async (agentId, modelId) => {
    try {
      await fetch(`${window.location.origin}/api/profiles/${agentId}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId || null })
      });
      setConfigs(prev => ({ ...prev, [agentId]: modelId }));
      setJustApplied(agentId);
      setTimeout(() => setJustApplied(null), 2000);
    } catch (e) {}
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-[11px] font-mono text-[var(--text-dim)] animate-pulse">
        A carregar recomendações...
      </div>
    );
  }

  const formatSize = (bytes) => {
    if (!bytes) return '';
    const gb = bytes / (1024 * 1024 * 1024);
    return gb >= 1 ? `${gb.toFixed(1)}GB` : `${(bytes / (1024 * 1024)).toFixed(0)}MB`;
  };

  return (
    <div className="model-recommendations-panel" style={{ padding: '12px', border: '1px solid var(--border-subtle)', borderRadius: '12px', background: 'var(--bg-primary)' }}>
      <h3 className="text-xs font-mono font-bold tracking-wider mb-3" style={{ color: 'var(--cyber-blue)' }}>
        🎯 Recomendações de Modelos
      </h3>
      <div className="space-y-2">
        {Object.entries(PROFILE_INFO).map(([profileId, info]) => {
          const recs = getRecommendations(profileId);
          const currentModel = configs[profileId] || null;
          const isExpanded = expanded === profileId;
          const topRec = recs[0];
          const topLocal = recs.find(r => r.tags.type === 'local');
          const topCloud = recs.find(r => r.tags.type === 'cloud' || r.source === 'cloud');
          const justSet = justApplied === profileId;

          return (
            <div key={profileId} className="rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
              <div
                className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-[var(--bg-hover)] transition-colors"
                onClick={() => setExpanded(isExpanded ? null : profileId)}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
                    {info.name}
                  </span>
                  <span className="text-[9px] font-mono text-[var(--text-dim)] truncate">
                    {info.focus}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border" style={{ borderColor: 'var(--border-subtle)', color: currentModel ? 'var(--text-primary)' : 'var(--text-dim)' }}>
                    {currentModel || 'default'}
                  </span>
                  {justSet && <span className="text-[9px] font-mono text-[var(--matrix-green)] animate-pulse">✓</span>}
                  <span className="text-[10px] text-[var(--text-muted)]">{isExpanded ? '▼' : '▶'}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="px-3 pb-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                  {/* Top local + cloud badges */}
                  <div className="flex gap-2 py-2">
                    {topCloud && (
                      <div className="flex-1 rounded px-2 py-1.5 border" style={{ borderColor: 'var(--cyber-blue)', background: 'rgba(0,212,255,0.05)' }}>
                        <div className="text-[8px] font-mono text-[var(--text-dim)]">MELHOR CLOUD</div>
                        <div className="text-[10px] font-mono" style={{ color: 'var(--cyber-blue)' }}>☁️ {topCloud.name || topCloud.id}</div>
                        {topCloud.tags.note && <div className="text-[8px] font-mono text-[var(--text-dim)]">{topCloud.tags.note}</div>}
                      </div>
                    )}
                    {topLocal && (
                      <div className="flex-1 rounded px-2 py-1.5 border" style={{ borderColor: 'var(--matrix-green)', background: 'rgba(0,255,65,0.05)' }}>
                        <div className="text-[8px] font-mono text-[var(--text-dim)]">MELHOR LOCAL</div>
                        <div className="text-[10px] font-mono" style={{ color: 'var(--matrix-green)' }}>💻 {topLocal.name || topLocal.id}</div>
                        {topLocal.tags.note && <div className="text-[8px] font-mono text-[var(--text-dim)]">{topLocal.tags.note}</div>}
                      </div>
                    )}
                  </div>

                  {/* Full ranking */}
                  <div className="space-y-0.5" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {recs.slice(0, 10).map((rec, idx) => {
                      const isCurrent = currentModel === rec.id;
                      const isTop = idx === 0;
                      const isTopLocal = rec.tags.type === 'local' && rec === topLocal;
                      return (
                        <div
                          key={rec.id}
                          className="flex items-center justify-between py-1 px-2 rounded transition-colors hover:bg-[var(--bg-hover)]"
                          style={{ background: isTop ? 'rgba(0,255,65,0.04)' : isTopLocal ? 'rgba(0,255,65,0.02)' : 'transparent' }}
                        >
                          <div className="flex items-center gap-1.5 flex-1 min-w-0">
                            <span className="text-[10px] font-mono flex-shrink-0" style={{ color: isTop ? 'var(--matrix-green)' : 'var(--text-dim)' }}>
                              {isTop ? '⭐' : `#${idx+1}`}
                            </span>
                            <span className="text-xs flex-shrink-0">
                              {rec.tags.type === 'cloud' || rec.source === 'cloud' ? '☁️' : '💻'}
                            </span>
                            <span className="text-[10px] font-mono truncate" style={{ color: 'var(--text-primary)' }}>
                              {rec.name || rec.id}
                            </span>
                            {rec.tags.note && (
                              <span className="text-[9px] font-mono truncate hidden lg:inline" style={{ color: 'var(--text-dim)' }}>
                                — {rec.tags.note}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {rec.size > 0 && (
                              <span className="text-[9px] font-mono text-[var(--text-muted)]">{formatSize(rec.size)}</span>
                            )}
                            <span className="text-[9px] font-mono text-[var(--text-dim)]" title={rec.reasons ? rec.reasons.join(', ') : ''}>
                              {rec.score}
                            </span>
                            <button
                              onClick={(e) => { e.stopPropagation(); applyModel(profileId, rec.id); }}
                              className="text-[9px] font-mono px-2 py-0.5 rounded border transition-colors"
                              style={{
                                borderColor: isCurrent ? 'var(--matrix-green)' : 'var(--border-subtle)',
                                color: isCurrent ? 'var(--matrix-green)' : 'var(--text-muted)',
                                background: isCurrent ? 'rgba(0,255,65,0.08)' : 'transparent',
                              }}
                            >
                              {isCurrent ? '✓' : 'Usar'}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Reset */}
                  <div className="flex items-center justify-between py-1.5 px-2 mt-1 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="text-[9px] font-mono text-[var(--text-dim)]">Default (kimi-k2.6 cloud)</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); applyModel(profileId, null); }}
                      className="text-[9px] font-mono px-2 py-0.5 rounded border text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                      style={{ borderColor: 'var(--border-subtle)' }}
                    >
                      Reset
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
