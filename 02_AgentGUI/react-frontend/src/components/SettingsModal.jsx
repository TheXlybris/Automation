import { useState, useEffect } from 'react';

const CATEGORY_LABELS = {
  'autonomous-ai-agents': 'AI Agents',
  'creative': 'Creative',
  'data-science': 'Data Science',
  'devops': 'DevOps',
  'email': 'Email',
  'gaming': 'Gaming',
  'github': 'GitHub',
  'mcp': 'MCP',
  'media': 'Media',
  'mlops': 'MLOps',
  'mlops_models': 'ML Models',
  'note-taking': 'Notes',
  'productivity': 'Productivity',
  'red-teaming': 'Red Teaming',
  'research': 'Research',
  'smart-home': 'Smart Home',
  'social-media': 'Social',
  'software-development': 'Software Dev',
  'wiki': 'Wiki',
};

export default function SettingsModal({ agentId, agentName, currentModel, onSave, onClose }) {
  // ─── Model state ───
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [selectedModel, setSelectedModel] = useState(currentModel || '');
  const [modelsError, setModelsError] = useState(null);

  // ─── Skills state ───
  const [categories, setCategories] = useState({});
  const [skillsConfig, setSkillsConfig] = useState({ enabled: [], disabled: [] });
  const [loadingSkills, setLoadingSkills] = useState(true);
  const [skillsError, setSkillsError] = useState(null);
  const [filterCategory, setFilterCategory] = useState('all');

  // ─── SOUL state ───
  const [soulContent, setSoulContent] = useState('');
  const [loadingSoul, setLoadingSoul] = useState(true);
  const [soulError, setSoulError] = useState(null);
  const [soulDirty, setSoulDirty] = useState(false);

  const [saving, setSaving] = useState(false);

  // ─── Load models ───
  useEffect(() => {
    fetch(`${window.location.origin}/api/models`)
      .then(r => r.json())
      .then(data => {
        setModels(data.models || []);
        if (!selectedModel && data.default) setSelectedModel(data.default);
        setLoadingModels(false);
      })
      .catch(() => {
        setModelsError('Falha ao carregar modelos');
        setLoadingModels(false);
      });
  }, []);

  // ─── Load skills ───
  useEffect(() => {
    Promise.all([
      fetch(`${window.location.origin}/api/skills?profile=${agentId}`).then(r => r.json()),
      fetch(`${window.location.origin}/api/profiles/${agentId}/skills-config`).then(r => r.json())
    ])
      .then(([skillsData, configData]) => {
        setCategories(skillsData.categories || {});
        setSkillsConfig(configData);
        setLoadingSkills(false);
      })
      .catch(() => {
        setSkillsError('Falha ao carregar skills');
        setLoadingSkills(false);
      });
  }, [agentId]);

  // ─── Load SOUL ───
  useEffect(() => {
    setLoadingSoul(true);
    fetch(`${window.location.origin}/api/profiles/${agentId}/soul`)
      .then(r => r.json())
      .then(data => {
        setSoulContent(data.content || '');
        setSoulDirty(false);
        setLoadingSoul(false);
      })
      .catch(() => {
        setSoulError('Falha ao carregar SOUL.md');
        setLoadingSoul(false);
      });
  }, [agentId]);

  // ─── Handlers ───
  const toggleSkill = (skillName) => {
    setSkillsConfig(prev => {
      const enabled = [...prev.enabled];
      const disabled = [...prev.disabled];
      if (enabled.includes(skillName)) {
        return { enabled: enabled.filter(n => n !== skillName), disabled: [...disabled, skillName] };
      } else if (disabled.includes(skillName)) {
        return { enabled: [...enabled, skillName], disabled: disabled.filter(n => n !== skillName) };
      } else {
        return { enabled: [...enabled, skillName], disabled };
      }
    });
  };

  const handleSave = async () => {
    setSaving(true);
    // 1. Save model
    onSave(selectedModel);
    // 2. Save skills
    try {
      await fetch(`${window.location.origin}/api/profiles/${agentId}/skills-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(skillsConfig)
      });
    } catch (e) { /* silent */ }
    // 3. Save SOUL.md (only if changed)
    if (soulDirty) {
      try {
        await fetch(`${window.location.origin}/api/profiles/${agentId}/soul`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: soulContent })
        });
      } catch (e) { /* silent */ }
    }
    setSaving(false);
    onClose();
  };

  const formatSize = (bytes) => {
    if (!bytes) return '';
    const gb = bytes / (1024 * 1024 * 1024);
    return gb >= 1 ? ` (${gb.toFixed(1)} GB)` : ` (${(bytes / (1024 * 1024)).toFixed(0)} MB)`;
  };

  // ─── Build filtered skills list ───
  const allSkills = [];
  const catNames = Object.keys(categories).sort();
  for (const cat of catNames) {
    if (filterCategory !== 'all' && cat !== filterCategory) continue;
    for (const s of categories[cat]) {
      allSkills.push({ ...s, category: cat });
    }
  }

  const enabledCount = allSkills.filter(s => skillsConfig.enabled.includes(s.name)).length;
  const totalCount = allSkills.length;

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div className="settings-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '520px', maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-mono font-bold tracking-wider" style={{ color: 'var(--cyber-blue)' }}>
            ⚙️ Settings — {agentName}
          </h3>
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-lg">
            ×
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>

          {/* ─── MODELO ─── */}
          <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
            <label className="text-[11px] font-mono text-[var(--text-secondary)] block mb-2">
              🤖 MODELO
            </label>
            {loadingModels ? (
              <div className="text-[10px] text-[var(--text-dim)] font-mono animate-pulse">A carregar modelos...</div>
            ) : modelsError ? (
              <div className="text-[10px] text-[var(--alert-red)] font-mono">{modelsError}</div>
            ) : (
              <select
                value={selectedModel}
                onChange={e => setSelectedModel(e.target.value)}
                className="settings-select"
              >
                <option value="">Default (kimi-k2.6)</option>
                {models.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.source === 'cloud' ? '☁️' : '💻'} {m.name}{m.source === 'cloud' ? ' (cloud)' : ''}{formatSize(m.size)}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* ─── SKILLS ─── */}
          <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
            <label className="text-[11px] font-mono text-[var(--text-secondary)] block mb-2">
              🧠 SKILLS
            </label>
            {loadingSkills ? (
              <div className="text-[10px] text-[var(--text-dim)] font-mono animate-pulse py-2">A carregar skills...</div>
            ) : skillsError ? (
              <div className="text-[10px] text-[var(--alert-red)] font-mono py-2">{skillsError}</div>
            ) : (
              <>
                {/* Filter + counter */}
                <div className="flex items-center justify-between mb-2">
                  <select
                    value={filterCategory}
                    onChange={e => setFilterCategory(e.target.value)}
                    className="settings-select text-[10px]"
                    style={{ width: 'auto', padding: '2px 8px' }}
                  >
                    <option value="all">Todas as categorias</option>
                    {catNames.map(cat => (
                      <option key={cat} value={cat}>{CATEGORY_LABELS[cat] || cat}</option>
                    ))}
                  </select>
                  <span className="text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>
                    {enabledCount} / {totalCount} ativas
                  </span>
                </div>

                {/* Skills grid */}
                <div className="space-y-0.5" style={{ maxHeight: '260px', overflowY: 'auto' }}>
                  {allSkills.length === 0 ? (
                    <p className="text-[10px] text-[var(--text-dim)] font-mono py-2">Nenhuma skill nesta categoria.</p>
                  ) : (
                    allSkills.map(s => {
                      const isEnabled = skillsConfig.enabled.includes(s.name);
                      return (
                        <div
                          key={s.name}
                          className="flex items-center gap-2 py-1 px-1.5 rounded cursor-pointer transition-colors hover:bg-[var(--bg-hover)]"
                          onClick={() => toggleSkill(s.name)}
                        >
                          <span className="text-xs flex-shrink-0" style={{ color: isEnabled ? 'var(--matrix-green)' : 'var(--text-muted)' }}>
                            {isEnabled ? '✅' : '⬜'}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-[10px] font-mono truncate" style={{ color: isEnabled ? 'var(--text-primary)' : 'var(--text-dim)' }}>
                              {s.name}
                            </p>
                            {s.description && (
                              <p className="text-[8px] font-mono truncate" style={{ color: 'var(--text-dim)' }}>
                                {s.description}
                              </p>
                            )}
                          </div>
                          <span className="text-[8px] font-mono flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
                            {CATEGORY_LABELS[s.category] || s.category}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            )}
          </div>

          {/* ─── SOUL (System Prompt) ─── */}
          <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-primary)' }}>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-mono text-[var(--text-secondary)]">
                🧬 SOUL.md (System Prompt)
              </label>
              {soulDirty && (
                <span className="text-[9px] font-mono text-[var(--amber-warn)]">● não guardado</span>
              )}
            </div>
            {loadingSoul ? (
              <div className="text-[10px] text-[var(--text-dim)] font-mono animate-pulse py-2">A carregar SOUL.md...</div>
            ) : soulError ? (
              <div className="text-[10px] text-[var(--alert-red)] font-mono py-2">{soulError}</div>
            ) : (
              <textarea
                value={soulContent}
                onChange={e => { setSoulContent(e.target.value); setSoulDirty(true); }}
                placeholder="Escreve aqui o system prompt (persona) deste agente..."
                className="settings-select"
                style={{
                  width: '100%',
                  minHeight: '120px',
                  maxHeight: '300px',
                  resize: 'vertical',
                  fontFamily: 'monospace',
                  fontSize: '10px',
                  lineHeight: '1.5',
                  padding: '8px',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                }}
              />
            )}
          </div>

          {/* ─── FUTURE SECTIONS GO HERE ─── */}
          {/* Add new setting blocks above the footer; Guardar handles all */}

        </div>

        {/* Footer — single Save button */}
        <div className="flex gap-2 pt-3 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-glow flex-1 text-[11px] py-2 px-4 rounded-lg font-mono font-bold border"
            style={{
              background: 'var(--bg-card)',
              borderColor: 'var(--matrix-green)',
              color: 'var(--matrix-green)',
              opacity: saving ? 0.6 : 1
            }}
          >
            {saving ? '⏳ A guardar...' : '💾 Guardar'}
          </button>
          <button
            onClick={onClose}
            className="btn-glow px-4 py-2 rounded-lg text-[11px] font-mono border"
            style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
