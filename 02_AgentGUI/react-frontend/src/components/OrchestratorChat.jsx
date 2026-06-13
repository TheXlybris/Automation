import { useState, useRef, useEffect } from 'react';

export default function OrchestratorChat({ socket }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [mode, setMode] = useState('brainstorm');
  const [agentOnline, setAgentOnline] = useState(false);
  const timeoutRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!socket) return;

    const handleResponse = (data) => {
      setMessages(prev => [...prev, { role: 'assistant', text: data.text, mode: data.mode }]);
      setSending(false);
      setAgentOnline(true);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const handleTyping = () => {
      setMessages(prev => {
        if (prev.length > 0 && prev[prev.length - 1].role === 'typing') return prev;
        return [...prev, { role: 'typing', text: '' }];
      });
      setAgentOnline(true);
    };

    const handleStatus = (data) => {
      if (data && data.status) {
        setAgentOnline(data.status === 'online');
      }
    };

    const handleModeChange = (data) => {
      if (data && data.mode) {
        setMode(data.mode);
      }
    };

    socket.on('orchestrator_response', handleResponse);
    socket.on('orchestrator_typing', handleTyping);
    socket.on('orchestrator_status', handleStatus);
    socket.on('orchestrator_mode_change', handleModeChange);

    // Polling HTTP do estado do orquestrador (fallback para Socket.IO)
    const pollStatus = async () => {
      try {
        const res = await fetch('http://192.168.0.188:5020/api/orchestrator/status');
        if (res.ok) {
          const data = await res.json();
          if (data && data.status) {
            setAgentOnline(data.status === 'online');
            if (data.mode) setMode(data.mode);
          }
        }
      } catch (e) {
        // Silencioso — pode estar offline
      }
    };
    pollStatus();
    const pollInterval = setInterval(pollStatus, 5000);

    return () => {
      socket.off('orchestrator_response', handleResponse);
      socket.off('orchestrator_typing', handleTyping);
      socket.off('orchestrator_status', handleStatus);
      socket.off('orchestrator_mode_change', handleModeChange);
      clearInterval(pollInterval);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [socket]);

  const send = () => {
    const txt = input.trim();
    if (!txt || !socket) return;
    setMessages(prev => [...prev, { role: 'user', text: txt }]);
    setInput('');
    setSending(true);
    // Timeout: se ninguém responder em 30s (o agente pode demorar), remover "a processar"
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setSending(false);
      setMessages(prev => {
        const filtered = prev.filter(m => m.role !== 'typing');
        return [...filtered, { role: 'system', text: 'Orquestrador não respondeu (offline ou ocupado). A resposta aparecerá aqui quando disponível.' }];
      });
    }, 30000);
    socket.emit('orchestrator_message', { text: txt });
  };

  const toggleMode = () => {
    const newMode = mode === 'brainstorm' ? 'orchestrator' : 'brainstorm';
    setMode(newMode);
    socket?.emit('orchestrator_mode_change', { mode: newMode });
  };

  const requestSummary = () => {
    socket?.emit('orchestrator_summarize', {});
    setMessages(prev => [...prev, { role: 'system', text: '📋 A gerar resumo da conversa...' }]);
  };

  const modeLabel = mode === 'brainstorm' ? 'BRAINSTORM' : 'ORQUESTRADOR';
  const modeColor = mode === 'brainstorm' ? 'var(--cyber-blue)' : 'var(--matrix-green)';

  return (
    <div className="orchestrator-chat">
      <div className="orchestrator-header">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${agentOnline ? 'bg-[var(--matrix-green)] animate-pulse' : 'bg-[var(--text-muted)]'}`} />
          <h2 className="text-sm font-mono uppercase tracking-wider" style={{ color: 'var(--matrix-green)' }}>
            Orquestrador Hermes
          </h2>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border" style={{ borderColor: modeColor, color: modeColor }}>
            {modeLabel}
          </span>
          {!agentOnline && (
            <span className="text-[10px] font-mono text-[var(--alert-red)]">OFFLINE</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={requestSummary}
            disabled={messages.length < 3}
            className="text-[10px] font-mono px-2 py-1 rounded border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--text-primary)] transition-colors disabled:opacity-30"
            title="Gerar resumo da conversa"
          >
            📋 Resumo
          </button>
          <button
            onClick={toggleMode}
            className="text-[10px] font-mono px-2 py-1 rounded border transition-colors"
            style={{ borderColor: modeColor, color: modeColor }}
            title={`Mudar para modo ${mode === 'brainstorm' ? 'Orquestrador' : 'Brainstorm'}`}
          >
            🔄 {mode === 'brainstorm' ? '→ Orquestrador' : '→ Brainstorm'}
          </button>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">v2.3</span>
        </div>
      </div>

      <div className="orchestrator-messages">
        {messages.length === 0 && (
          <div className="text-xs text-[var(--text-muted)] font-mono py-8 text-center border border-dashed border-[var(--border-subtle)] rounded opacity-50">
            Chat vazio. Escreve abaixo para enviar uma mensagem ao orquestrador.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            {m.role === 'user' && (
              <div className="msg-avatar user-avatar">Eu</div>
            )}
            {m.role === 'assistant' && (
              <div className="msg-avatar assistant-avatar">H</div>
            )}
            {m.role === 'system' && (
              <div className="msg-avatar system-avatar">✦</div>
            )}
            {m.role === 'typing' && (
              <div className="msg-avatar assistant-avatar">H</div>
            )}
            <div className="msg-bubble">
              {m.role === 'typing' ? (
                <span className="typing-dots">
                  <span></span><span></span><span></span>
                </span>
              ) : (
                <>
                  <pre className="msg-text">{m.text}</pre>
                  {m.mode && (
                    <span className="text-[9px] font-mono opacity-40 mt-1 block" style={{ color: m.mode === 'orchestrator' ? 'var(--matrix-green)' : 'var(--cyber-blue)' }}>
                      [{m.mode.toUpperCase()}]
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="orchestrator-input-row">
        <textarea
          className="orchestrator-input"
          placeholder={`Modo ${modeLabel}: Escreve algo...`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={sending}
          rows={1}
          style={{ resize: 'vertical', minHeight: '36px', maxHeight: '200px' }}
        />
        <button
          onClick={send}
          disabled={sending || !input.trim()}
          className="orchestrator-send"
        >
          {sending ? '...' : '→'}
        </button>
      </div>
    </div>
  );
}
