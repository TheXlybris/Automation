import { useState, useEffect } from 'react';

const WEEKDAYS = [
  { key: 0, label: 'Seg' },
  { key: 1, label: 'Ter' },
  { key: 2, label: 'Qua' },
  { key: 3, label: 'Qui' },
  { key: 4, label: 'Sex' },
  { key: 5, label: 'Sab' },
  { key: 6, label: 'Dom' },
];

const PROFILES = [
  { id: 'researcher', name: 'Researcher', color: '#00ff41' },
  { id: 'developer', name: 'Developer', color: '#00d4ff' },
  { id: 'multimedia', name: 'Multimedia', color: '#ff7b00' },
  { id: 'wiki', name: 'Wiki Curator', color: '#ffb800' },
];

export default function CronTasksView({ socket }) {
  const [tasks, setTasks] = useState([]);
  const [profile, setProfile] = useState('researcher');
  const [taskText, setTaskText] = useState('');
  const [hour, setHour] = useState(12);
  const [minute, setMinute] = useState(0);
  const [selectedDays, setSelectedDays] = useState([0, 1, 2, 3, 4]);
  const [repeatType, setRepeatType] = useState('times');
  const [repeatCount, setRepeatCount] = useState(5);
  const [justAdded, setJustAdded] = useState(null);

  useEffect(() => {
    if (!socket) return;
    socket.emit('list_cron_tasks');
    const onUpdate = (data) => {
      setTasks(data.tasks || []);
    };
    socket.on('cron_tasks_update', onUpdate);
    return () => socket.off('cron_tasks_update', onUpdate);
  }, [socket]);

  const toggleDay = (d) => {
    setSelectedDays(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d].sort()
    );
  };

  const addTask = () => {
    if (!taskText.trim() || !socket) return;
    socket.emit('add_cron_task', {
      profile, task: taskText,
      hour: parseInt(hour, 10),
      minute: parseInt(minute, 10),
      days: selectedDays,
      repeat_type: repeatType,
      repeat_count: parseInt(repeatCount, 10),
    });
    setTaskText('');
    setJustAdded('added');
    setTimeout(() => setJustAdded(null), 1500);
  };

  const removeTask = (id) => {
    if (!socket) return;
    socket.emit('remove_cron_task', { id });
  };

  const removeCompletedTasks = () => {
    if (!socket) return;
    const completed = tasks.filter(t => t.repeat_type === 'times' && (t.runs_done || 0) >= t.repeat_count);
    if (completed.length === 0) return;
    if (!confirm(`Apagar ${completed.length} tarefa(s) cron concluída(s)?`)) return;
    socket.emit('remove_completed_cron_tasks');
  };

  const completedCount = tasks.filter(t => t.repeat_type === 'times' && (t.runs_done || 0) >= t.repeat_count).length;

  const toggleTask = (id, enabled) => {
    if (!socket) return;
    socket.emit('toggle_cron_task', { id, enabled: !enabled });
  };

  const formatDays = (days) => {
    if (!days || days.length === 0) return 'Nenhum dia';
    if (days.length === 7) return 'Todos os dias';
    if (days.length === 5 && days.every((d, i) => d === i)) return 'Seg-Sex';
    return days.map(d => WEEKDAYS.find(w => w.key === d)?.label).join(', ');
  };

  const statusColor = (t) => {
    if (!t.enabled) return 'var(--text-muted)';
    if (t.repeat_type === 'times' && t.runs_done >= t.repeat_count) return 'var(--cyber-blue)';
    return 'var(--matrix-green)';
  };

  const statusLabel = (t) => {
    if (!t.enabled) return 'Desativada';
    if (t.repeat_type === 'times' && t.runs_done >= t.repeat_count) return 'Completa';
    return 'Ativa';
  };

  const profileName = (pid) => PROFILES.find(p => p.id === pid)?.name || pid;
  const profileColor = (pid) => PROFILES.find(p => p.id === pid)?.color || '#888';

  return (
    <div>
      {/* Form */}
      <div className="section-panel mb-8">
        <div className="section-panel-header">
          <div className="w-2 h-2 rounded-full bg-[var(--cyber-blue)] animate-pulse" />
          <h3 className="section-title" style={{ color: 'var(--cyber-blue)' }}>
            Nova Tarefa Cron
          </h3>
        </div>

        {/* Profile */}
        <div className="mb-5">
          <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Agent Profile</label>
          <div className="flex gap-3 flex-wrap">
            {PROFILES.map(p => (
              <button
                key={p.id}
                onClick={() => setProfile(p.id)}
                className={`badge-btn transition-all duration-200 ${
                  profile === p.id
                    ? 'border bg-[var(--bg-card)]'
                    : 'border border-transparent bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                }`}
                style={profile === p.id ? { 
                  color: p.color, 
                  borderColor: p.color + '40',
                  boxShadow: `0 0 12px ${p.color}20`,
                } : {}}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {/* Task text */}
        <div className="mb-5">
          <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Tarefa</label>
          <textarea
            className="input-glow w-full text-[12px]"
            rows={3}
            placeholder="Descreve a tarefa que o agente deve executar..."
            value={taskText}
            onChange={e => setTaskText(e.target.value)}
          />
        </div>

        {/* Time */}
        <div className="flex gap-6 mb-5">
          <div>
            <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Hora</label>
            <input
              type="number" min={0} max={23}
              value={hour}
              onChange={e => setHour(Math.max(0, Math.min(23, parseInt(e.target.value || 0, 10))))}
              className="input-glow w-20 text-center text-[12px]"
            />
          </div>
          <div>
            <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Minuto</label>
            <input
              type="number" min={0} max={59}
              value={minute}
              onChange={e => setMinute(Math.max(0, Math.min(59, parseInt(e.target.value || 0, 10))))}
              className="input-glow w-20 text-center text-[12px]"
            />
          </div>
        </div>

        {/* Days */}
        <div className="mb-5">
          <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Dias da Semana</label>
          <div className="flex gap-2 flex-wrap">
            {WEEKDAYS.map(d => (
              <button
                key={d.key}
                onClick={() => toggleDay(d.key)}
                className={`toggle-btn transition-all duration-200 ${
                  selectedDays.includes(d.key)
                    ? 'text-[var(--matrix-green)] bg-[var(--bg-card)] border'
                    : 'text-[var(--text-muted)] bg-[var(--bg-secondary)] border border-transparent hover:text-[var(--text-secondary)]'
                }`}
                style={selectedDays.includes(d.key) ? { 
                  borderColor: 'var(--matrix-green)',
                  boxShadow: '0 0 10px rgba(0,255,65,0.15)',
                } : {}}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        {/* Repeat */}
        <div className="mb-6">
          <label className="text-[10px] text-[var(--text-dim)] block mb-2 font-mono">Repeticao</label>
          <div className="flex gap-4 items-center flex-wrap">
            <label className="flex items-center gap-2 text-[11px] cursor-pointer">
              <input
                type="radio" name="repeat"
                checked={repeatType === 'times'}
                onChange={() => setRepeatType('times')}
              />
              <span className="text-[var(--text-secondary)]">X vezes</span>
            </label>
            {repeatType === 'times' && (
              <input
                type="number" min={1} max={9999}
                value={repeatCount}
                onChange={e => setRepeatCount(Math.max(1, parseInt(e.target.value || 1, 10)))}
                className="input-glow w-16 text-center text-[12px]"
              />
            )}
            <label className="flex items-center gap-2 text-[11px] cursor-pointer">
              <input
                type="radio" name="repeat"
                checked={repeatType === 'infinite'}
                onChange={() => setRepeatType('infinite')}
              />
              <span className="text-[var(--text-secondary)]">Ate eu parar</span>
            </label>
          </div>
        </div>

        <button
          onClick={addTask}
          disabled={!taskText.trim()}
          className="btn-glow px-6 py-3 rounded-lg font-mono text-[12px] font-bold tracking-wider uppercase transition-all duration-300"
          style={{ 
            opacity: !taskText.trim() ? 0.4 : 1,
            cursor: !taskText.trim() ? 'not-allowed' : 'pointer',
            background: 'var(--bg-card)',
            color: 'var(--matrix-green)',
            border: '1px solid rgba(0,255,65,0.3)',
            boxShadow: !taskText.trim() ? 'none' : '0 2px 12px rgba(0,255,65,0.15), 0 0 20px rgba(0,255,65,0.05)',
          }}
        >
          {justAdded === 'added' ? '✓ Adicionada!' : 'Adicionar Tarefa Cron'}
        </button>
      </div>

      {/* List */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[var(--cyber-blue)] animate-pulse" />
            <h3 className="section-title" style={{ color: 'var(--cyber-blue)' }}>
              Tarefas Agendadas ({tasks.length})
            </h3>
          </div>
          {completedCount > 0 && (
            <button
              onClick={removeCompletedTasks}
              className="px-4 py-2 rounded-lg font-mono text-xs tracking-wider transition-all duration-300 border"
              style={{
                borderColor: 'rgba(239,68,68,0.3)',
                background: 'rgba(239,68,68,0.06)',
                color: '#ef4444',
              }}
            >
              🗑 Apagar Concluídas ({completedCount})
            </button>
          )}
        </div>

        {tasks.length === 0 && (
          <div className="text-center py-16 text-[var(--text-dim)] font-mono text-sm">
            <div className="mb-4 text-5xl opacity-20">&#x23F0;</div>
            Nenhuma tarefa cron agendada.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tasks.map(t => (
            <div key={t.id} className="card-glow agent-card p-5" style={{ opacity: t.enabled ? 1 : 0.6 }}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ 
                      background: statusColor(t),
                      boxShadow: `0 0 8px ${statusColor(t)}80`,
                    }}
                  />
                  <span className="text-[11px] font-mono font-bold" style={{ color: profileColor(t.profile) }}>
                    {profileName(t.profile)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleTask(t.id, t.enabled)}
                    className="toggle-btn transition-all duration-200"
                    style={{
                      borderColor: t.enabled ? 'var(--matrix-green)' : 'var(--text-muted)',
                      color: t.enabled ? 'var(--matrix-green)' : 'var(--text-muted)',
                      background: t.enabled ? 'rgba(0,255,65,0.06)' : 'transparent',
                      border: '1px solid',
                    }}
                  >
                    {t.enabled ? 'ON' : 'OFF'}
                  </button>
                  <button
                    onClick={() => removeTask(t.id)}
                    className="w-6 h-6 flex items-center justify-center rounded-full text-[10px] text-red-400 hover:text-red-200 hover:bg-red-400/10 transition-all"
                    title="Remover"
                  >&#x2715;</button>
                </div>
              </div>

              <p className="text-[11px] text-[var(--text-secondary)] mb-3 leading-relaxed">
                {t.task}
              </p>

              <div className="flex gap-4 text-[10px] text-[var(--text-dim)] font-mono mb-2">
                <span>&#x23F0; {String(t.hour).padStart(2, '0')}:{String(t.minute).padStart(2, '0')}</span>
                <span>&#x1F4C5; {formatDays(t.days)}</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[var(--text-dim)]">
                  {t.repeat_type === 'times'
                    ? `${t.runs_done || 0}/${t.repeat_count} execucoes`
                    : `${t.runs_done || 0} execucoes (infinito)`}
                </span>
                <span className="text-[10px] font-mono" style={{ color: statusColor(t) }}>
                  {statusLabel(t)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}