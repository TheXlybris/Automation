import { useState } from 'react';
import { api } from '../services/api';

const PROFILES = [
  { value: 'developer',  label: 'Developer',  color: 'bg-blue-600' },
  { value: 'multimedia', label: 'Multimedia', color: 'bg-purple-600' },
  { value: 'researcher', label: 'Researcher', color: 'bg-amber-600' },
];

function LaunchForm({ onLaunch }) {
  const [profile, setProfile] = useState('developer');
  const [goal, setGoal] = useState('');
  const [prompt, setPrompt] = useState('');
  const [context, setContext] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!goal.trim()) return;

    setSubmitting(true);
    try {
      await api.launch({
        profile,
        goal: goal.trim(),
        prompt: prompt.trim() || goal.trim(),
        context: context.trim(),
        timeout_seconds: 1200,
      });
      // Clear form
      setGoal('');
      setPrompt('');
      setContext('');
      onLaunch();
    } catch (err) {
      alert(`Erro ao lançar: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-slate-800 rounded-xl border border-slate-700 p-6">
      <h2 className="text-lg font-bold mb-4 text-emerald-400">Lançar Novo Agente</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        {PROFILES.map(p => (
          <button
            key={p.value}
            type="button"
            onClick={() => setProfile(p.value)}
            className={`px-4 py-3 rounded-lg font-medium text-sm transition-all ${
              profile === p.value
                ? `${p.color} text-white ring-2 ring-offset-2 ring-offset-slate-800 ring-${p.color.replace('bg-', '')}`
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-400 mb-2">Tarefa / Objetivo *</label>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={2}
          placeholder="Descreve o que o agente deve fazer..."
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
          required
        />
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-400 mb-2">Prompt completo (opcional)</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Se vazio, usa o goal como prompt..."
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
        />
      </div>

      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-400 mb-2">Contexto adicional (opcional)</label>
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          rows={2}
          placeholder="Caminhos de ficheiros, notas, links relevantes..."
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-slate-200 placeholder-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
        />
      </div>

      <button
        type="submit"
        disabled={submitting || !goal.trim()}
        className={`w-full px-6 py-3 rounded-lg font-bold transition-all ${
          submitting || !goal.trim()
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30'
        }`}
      >
        {submitting ? '🚀 A lançar...' : '🚀 Lançar Agente'}
      </button>
    </form>
  );
}

export default LaunchForm;
