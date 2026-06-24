import { useState } from 'react';
import { api } from '../services/api';

const STATUS_COLORS = {
  running:   'bg-amber-500',
  completed: 'bg-emerald-500',
  error:     'bg-red-500',
  queued:    'bg-slate-500',
  cancelled: 'bg-slate-600',
};

const STATUS_LABELS = {
  running:   'A correr',
  completed: 'Concluído',
  error:     'Erro',
  queued:    'Em fila',
  cancelled: 'Cancelado',
};

function AgentCard({ agent, onDelete }) {
  const [showOutput, setShowOutput] = useState(false);
  const [output, setOutput] = useState('');
  const [outputLoading, setOutputLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchOutput = async () => {
    if (!showOutput) {
      setOutputLoading(true);
      try {
        const data = await api.getOutput(agent.id);
        setOutput(data.output || '(sem output)');
      } catch (err) {
        setOutput(`Erro: ${err.message}`);
      } finally {
        setOutputLoading(false);
      }
    }
    setShowOutput(!showOutput);
  };

  const handleKill = async () => {
    if (!confirm(`Matar agente ${agent.id}?`)) return;
    try {
      await api.kill(agent.id);
      if (onDelete) onDelete();
    } catch (err) {
      console.error('Erro ao matar:', err);
    }
  };

  const handleDelete = async () => {
    if (agent.status === 'running') {
      if (!confirm(`O agente ${agent.id} ainda está a correr. Matar e apagar?`)) return;
      try {
        await api.kill(agent.id);
      } catch (err) {
        console.error('Erro ao matar:', err);
      }
    } else {
      if (!confirm(`Apagar agente ${agent.id}?`)) return;
    }
    setDeleting(true);
    try {
      await api.deleteAgent(agent.id);
      if (onDelete) onDelete();
    } catch (err) {
      console.error('Erro ao apagar:', err);
    } finally {
      setDeleting(false);
    }
  };

  const statusColor = STATUS_COLORS[agent.status] || 'bg-slate-500';
  const statusLabel = STATUS_LABELS[agent.status] || agent.status;

  const progress = agent.progress ?? 0;
  const isRunning = agent.status === 'running';

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-5 shadow-lg hover:border-slate-600 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${statusColor} ${isRunning ? 'animate-pulse' : ''}`}></div>
          <span className="font-semibold text-sm truncate max-w-[140px]" title={agent.id}>{agent.id}</span>
        </div>
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-slate-700 text-slate-300">
          {agent.profile}
        </span>
      </div>

      {/* Status Badge */}
      <div className={`inline-block px-3 py-1 rounded-full text-xs font-medium mb-4 ${statusColor} bg-opacity-20 text-${statusColor.replace('bg-', '')}-400`}>
        {statusLabel}
      </div>

      {/* Goal */}
      <p className="text-sm text-slate-400 mb-4 line-clamp-2">{agent.goal || '(sem descrição)'}</p>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>Progresso</span>
          <span>{progress}%</span>
        </div>
        <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : statusColor} transition-all duration-500`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Message */}
      <p className="text-xs text-slate-500 mb-4 truncate">{agent.message || ''}</p>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={fetchOutput}
          className="flex-1 px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm font-medium transition-colors"
        >
          {showOutput ? 'Fechar' : 'Ver Output'}
        </button>
        <button
          onClick={handleKill}
          disabled={!isRunning}
          className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            isRunning
              ? 'bg-red-900 hover:bg-red-800 text-red-200'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
          }`}
        >
          Matar
        </button>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            deleting
              ? 'bg-slate-700 text-slate-500 cursor-wait'
              : 'bg-slate-700 hover:bg-red-900 hover:text-red-200 text-slate-400'
          }`}
          title="Apagar"
        >
          {deleting ? '...' : '🗑'}
        </button>
      </div>

      {/* Output Modal */}
      {showOutput && (
        <div className="mt-4 bg-black rounded-lg p-3 max-h-48 overflow-auto">
          <pre className="text-xs font-mono text-green-400 whitespace-pre-wrap">
            {outputLoading ? 'A carregar...' : output}
          </pre>
        </div>
      )}
    </div>
  );
}

export default AgentCard;
