const API_BASE = window.location.origin;  // Flask server na VM

async function request(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`HTTP ${res.status}: ${txt}`);
  }
  return res.json();
}

export const api = {
  listAgents: ()     => request('/api/agents'),
  launch:    (body)  => request('/api/agents/launch', { method: 'POST', body: JSON.stringify(body) }),
  getOutput: (id)    => request(`/api/agents/${id}/output`),
  kill:      (id)    => request(`/api/agents/${id}/kill`, { method: 'POST' }),
  getAgent:  (id)    => request(`/api/agents/${id}`),
  deleteAgent: (id)  => request(`/api/agents/${id}`, { method: 'DELETE' }),
  clearFinished: ()  => request('/api/agents/clear-finished', { method: 'POST' }),

  subscribe: (onMessage) => {
    const src = new EventSource(`${API_BASE}/api/stream`);
    src.onmessage = (evt) => {
      try { onMessage(JSON.parse(evt.data)); }
      catch (e) { console.error('SSE parse error', e); }
    };
    src.onerror = (err) => console.error('SSE error', err);
    return () => src.close();
  },
};
