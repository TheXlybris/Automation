import { useState } from 'react';
import AgentCard from './AgentCard';

export default function TasksView({ agents }) {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? agents : agents.filter(a => a.status === filter);

  const counts = {
    all: agents.length,
    running: agents.filter(a => a.status === 'running').length,
    completed: agents.filter(a => a.status === 'completed').length,
    error: agents.filter(a => a.status === 'error').length,
  };

  const FILTERS = [
    { key: 'all',       label: 'TODOS',       color: 'var(--text-primary)' },
    { key: 'running',   label: 'A CORRER',    color: 'var(--matrix-green)' },
    { key: 'completed', label: 'CONCLUIDOS',  color: 'var(--cyber-blue)' },
    { key: 'error',     label: 'ERROS',       color: 'var(--alert-red)' },
  ];

  return (
    <div className="tasks-view">
      <div className="tasks-header">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--cyber-blue)] animate-pulse" />
          <h2 className="text-xs font-mono font-bold tracking-wider text-[var(--cyber-blue)] uppercase">
            Gestao de Tarefas
          </h2>
        </div>
      </div>

      {/* Filter buttons */}
      <div className="flex gap-3 mb-6">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-4 py-2 rounded-lg font-mono text-xs tracking-wider transition-all duration-300 border ${
              filter === f.key
                ? 'border-[var(--border-active)] bg-[var(--bg-card)]'
                : 'border-transparent bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
            }`}
            style={filter === f.key ? { color: f.color, boxShadow: `0 0 20px ${f.color}20` } : {}}
          >
            {f.label} ({counts[f.key]})
          </button>
        ))}
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filtered.length === 0 ? (
          <div className="col-span-full text-center py-20 text-[var(--text-dim)] font-mono text-sm">
            <div className="mb-4 text-4xl opacity-20">⌘</div>
            Nenhum agente ativo neste filtro.
          </div>
        ) : (
          filtered.map(agent => (
            <AgentCard key={agent.id} agent={agent} />
          ))
        )}
      </div>
    </div>
  );
}
