import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import SystemResources from './components/SystemResources';
import OrchestratorChat from './components/OrchestratorChat';
import AgentPanel from './components/AgentPanel';
import TasksView from './components/TasksView';
import AgentHistory from './components/AgentHistory';

const NAV_ITEMS = [
  { key: 'agentes', label: 'AGENTES', icon: '\u269B', title: 'Agentes \u0026 Recursos' },
  { key: 'tarefas', label: 'TAREFAS', icon: '\u2611', title: 'Gestao de Tarefas' },
];

function App() {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState('agentes');
  const [agents, setAgents] = useState([]);
  const [restarting, setRestarting] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    const s = io('http://192.168.0.188:5020');

    s.on('connect', () => {
      console.log('Socket.IO connected');
      setConnected(true);
      setRestarting(false);
    });

    s.on('disconnect', () => {
      console.log('Socket.IO disconnected');
      setConnected(false);
    });

    s.on('agents_updated', (data) => {
      if (data.agents) setAgents(data.agents);
    });

    s.on('connected', (data) => {
      if (data.agents) setAgents(data.agents);
    });

    setSocket(s);
    return () => s.disconnect();
  }, []);

  const restartServer = async () => {
    if (restarting) return;
    setRestarting(true);
    try {
      await fetch('http://192.168.0.188:5020/api/restart', { method: 'POST' });
    } catch (e) {
      console.log('Restart request sent');
    }
    let attempts = 0;
    const poll = setInterval(() => {
      fetch('http://192.168.0.188:5020/health')
        .then(() => {
          clearInterval(poll);
          window.location.reload();
        })
        .catch(() => {
          attempts++;
          if (attempts > 20) {
            clearInterval(poll);
            setRestarting(false);
          }
        });
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] relative">
      <div className="matrix-bg" />
      <div className="scanline" />

      {/* Left Sidebar — Fixed, independent from content */}
      <aside
        className={`fixed left-0 top-0 h-screen z-20 flex flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-secondary)] transition-all duration-300 pointer-events-auto ${
          sidebarCollapsed ? 'w-14' : 'w-48'
        }`}
      >
        {/* Nav items */}
        <nav className="flex-1 py-2 flex flex-col gap-1 mt-12">
          {NAV_ITEMS.map(item => (
            <button
              key={item.key}
              onClick={() => setActiveTab(item.key)}
              title={item.title}
              className={`flex items-center gap-3 px-3 py-3 mx-1 rounded-lg transition-all duration-200 text-left ${
                activeTab === item.key
                  ? 'bg-[var(--bg-card)] text-[var(--matrix-green)] border border-[var(--border-active)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
              }`}
            >
              <span className="text-xl flex-shrink-0 w-6 text-center">{item.icon}</span>
              {!sidebarCollapsed && (
                <span className="text-[11px] font-mono font-bold tracking-wider whitespace-nowrap">
                  {item.label}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* Bottom: history toggle + status */}
        <div className="border-t border-[var(--border-subtle)] py-2 px-2">
          <AgentHistory socket={socket} compact={sidebarCollapsed} />
        </div>
      </aside>

      {/* Toggle button — outside sidebar, always clickable */}
      <button
        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        className="fixed left-0 top-0 z-50 py-3 flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors border-r border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]"
        style={{ width: sidebarCollapsed ? 56 : 192 }}
        title={sidebarCollapsed ? 'Expandir menu' : 'Colapsar menu'}
      >
        <span className="text-lg">☰</span>
        {!sidebarCollapsed && <span className="ml-2 text-[10px] font-mono tracking-wider">MENU</span>}
      </button>

      {/* Main Content — centered block, 250px margin each side */}
      <div 
        className="min-h-screen flex flex-col mx-auto"
        style={{ width: 'calc(100vw - 500px)', marginLeft: 'auto', marginRight: 'auto' }}
      >
        {/* Header */}
        <header className="relative z-10 border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]/90 backdrop-blur-sm">
          <div className="px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="pulse-dot bg-[var(--matrix-green)]" />
              <h1 className="text-2xl font-bold glitch-text tracking-wider" style={{ color: 'var(--matrix-green)' }}>
                AGENT<span style={{ color: 'var(--cyber-blue)' }}>GUI</span>
              </h1>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <button
                onClick={restartServer}
                disabled={restarting}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-[10px] tracking-wider border transition-all duration-300"
                style={{
                  borderColor: restarting ? 'var(--text-dim)' : 'var(--amber-warn)',
                  color: restarting ? 'var(--text-dim)' : 'var(--amber-warn)',
                  background: restarting ? 'var(--bg-secondary)' : 'rgba(255,184,0,0.08)',
                  opacity: restarting ? 0.6 : 1,
                  cursor: restarting ? 'not-allowed' : 'pointer',
                }}
                title="Restart Flask server"
              >
                <span className="text-sm">{'\u21bb'}</span>
                {restarting ? 'REINICIANDO...' : 'RESTART'}
              </button>

              <span className="flex items-center gap-2 text-[var(--text-secondary)]">
                <span
                  className="w-2 h-2 rounded-full animate-pulse"
                  style={{ background: connected ? 'var(--matrix-green)' : 'var(--alert-red)' }}
                />
                {connected ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>
          </div>
        </header>

        {/* Page Content — comfortable width, not edge-to-edge */}
        <main className="relative z-10 flex-1 overflow-auto">
          <div className="py-6">
            {activeTab === 'agentes' && (
              <div>
                <section className="mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-[var(--matrix-green)] animate-pulse" />
                    <h2 className="text-xs font-mono font-bold tracking-wider text-[var(--matrix-green)] uppercase">
                      System Resources
                    </h2>
                  </div>
                  <SystemResources socket={socket} />
                </section>

                <section className="mb-6">
                  <OrchestratorChat socket={socket} />
                </section>

                <section className="mb-6">
                  <AgentPanel socket={socket} />
                </section>
              </div>
            )}

            {activeTab === 'tarefas' && (
              <TasksView socket={socket} agents={agents} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;