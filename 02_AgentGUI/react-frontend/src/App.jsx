import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import SystemResources from './components/SystemResources';
import OrchestratorChat from './components/OrchestratorChat';
import AgentPanel from './components/AgentPanel';
import ModelRecommendations from './components/ModelRecommendations';
import TasksView from './components/TasksView';
import AgentHistory from './components/AgentHistory';
import MediaTimeline from './components/MediaTimeline';
import CommandCenter from './components/CommandCenter';

import CascadeWaterInpaint from './components/CascadeWaterInpaint';
import ImageAnimator from './components/ImageAnimator';
import ImageGenerator from './components/ImageGenerator';
import MusicGenerator from './components/MusicGenerator';

const NAV_ITEMS = [
  { key: 'agentes', label: 'AGENTES', icon: '🤖', title: 'Agentes & Recursos' },
  { key: 'comando', label: 'COMANDO', icon: '📡', title: 'Command Center — Live Terminal Feed' },
  { key: 'tarefas', label: 'TAREFAS', icon: '📋', title: 'Gestao de Tarefas' },
  { key: 'produzir', label: 'PRODUZIR', icon: '🎨', title: 'Image + Video + Music' },
  { key: 'media',   label: 'MEDIA',   icon: '🎬', title: 'Timeline Video/Musica' },
];

// Module-level component — stable reference prevents re-mount flicker
const SectionHeader = ({ title, emoji, colorVar, collapsed, onToggle, children }) => (
  <div className="rounded-xl border overflow-hidden" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between px-4 py-3 transition-colors hover:bg-[var(--bg-hover)]"
      style={{ background: 'transparent' }}
    >
      <div className="flex items-center gap-2">
        <span className="text-base">{emoji}</span>
        <h2 className="text-sm font-bold font-mono tracking-wider" style={{ color: `var(${colorVar})` }}>
          {title}
        </h2>
      </div>
      <span className="text-lg" style={{ color: 'var(--text-muted)' }}>
        {collapsed ? '+' : '-'}
      </span>
    </button>
    {!collapsed && (
      <div className="px-4 pb-4">{children}</div>
    )}
  </div>
);

function App() {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState('agentes');
  const [agents, setAgents] = useState([]);
  const [restarting, setRestarting] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Colapsible sections in PRODUZIR tab
  const [collapsedSections, setCollapsedSections] = useState({
    imageGen: false,
    musicGen: false,
    imageAnim: false,
    cascadeWater: false,
  });

  useEffect(() => {
    const s = io(window.location.origin);

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

    s.on('agents_list', (data) => {
      // Legacy event name — some server versions emit this
      const agents = Array.isArray(data) ? data : (data.agents || []);
      setAgents(agents);
    });

    s.on('connected', (data) => {
      if (data.agents) setAgents(data.agents);
    });

    s.on('task_dispatched', () => {
      // A new task was dispatched — fetch updated agents list immediately
      fetch(`${window.location.origin}/api/agents`)
        .then(r => r.json())
        .then(d => {
          const list = Array.isArray(d) ? d : (d.agents || []);
          setAgents(list);
        })
        .catch(err => console.error('Error fetching agents after dispatch:', err));
    });

    setSocket(s);
    return () => s.disconnect();
  }, []);

  const restartServer = async () => {
    if (restarting) return;
    setRestarting(true);
    try {
      await fetch(`${window.location.origin}/api/restart`, { method: 'POST' });
    } catch (e) {
      console.log('Restart request sent');
    }
    let attempts = 0;
    const poll = setInterval(() => {
      fetch(`${window.location.origin}/health`)
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

  const [generatedImage, setGeneratedImage] = useState(null);
  const [generatedMusic, setGeneratedMusic] = useState(null);

  const toggleSection = (key) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !prev[key] }));
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

      {/* Main Content — centered block */}
      <div
        className="min-h-screen flex flex-col mx-auto"
        style={{ width: 'calc(100vw - 500px)', marginLeft: 'auto', marginRight: 'auto' }}
      >
        {/* Header */}
        <header className="relative z-10 border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]/90 backdrop-blur-sm">
          <div className="px-6 py-2 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="pulse-dot bg-[var(--matrix-green)]" />
              <h1 className="text-sm font-bold glitch-text tracking-wider" style={{ color: 'var(--matrix-green)' }}>
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

        {/* Compact System Resources Bar */}
        <div
          style={{
            position: 'fixed',
            top: 40,
            left: sidebarCollapsed ? 56 : 192,
            right: 0,
            zIndex: 25,
          }}
        >
          <SystemResources socket={socket} compact={true} />
        </div>

        {/* Page Content — all tabs kept mounted (display:none) to preserve state across tab switches */}
        <main className="relative z-10 flex-1 overflow-auto" style={{ paddingTop: 54 }}>
          {/* AGENTES */}
          <div className="py-6 space-y-4" style={{ display: activeTab === 'agentes' ? 'block' : 'none' }}>
            <section className="mb-6">
              <OrchestratorChat socket={socket} />
            </section>
            <section className="mb-6">
              <AgentPanel socket={socket} />
            </section>
            <section className="mb-6">
              <ModelRecommendations socket={socket} />
            </section>
          </div>

          {/* COMANDO */}
          <div style={{ display: activeTab === 'comando' ? 'block' : 'none' }}>
            <CommandCenter socket={socket} />
          </div>

          {/* TAREFAS */}
          <div className="py-6 space-y-4" style={{ display: activeTab === 'tarefas' ? 'block' : 'none' }}>
            <TasksView socket={socket} agents={agents} />
          </div>

          {/* PRODUZIR */}
          <div className="py-6 space-y-4" style={{ display: activeTab === 'produzir' ? 'block' : 'none' }}>
            <SectionHeader
              title="IMAGE GENERATOR"
              emoji="🖼️"
              colorVar="--amber-warn"
              collapsed={collapsedSections.imageGen}
              onToggle={() => toggleSection('imageGen')}
            >
              <ImageGenerator onImageGenerated={(img) => {
                setGeneratedImage(img);
                console.log('Image generated:', img);
              }} />
            </SectionHeader>
            <SectionHeader
              title="MUSIC GENERATOR"
              emoji="🎵"
              colorVar="--cyber-blue"
              collapsed={collapsedSections.musicGen}
              onToggle={() => toggleSection('musicGen')}
            >
              <MusicGenerator onMusicGenerated={(music) => {
                setGeneratedMusic(music);
                console.log('Music generated:', music);
              }} />
            </SectionHeader>
            <SectionHeader
              title="IMAGE ANIMATOR — Efeitos Atmosfericos"
              emoji="✨"
              colorVar="--cyber-blue"
              collapsed={collapsedSections.imageAnim}
              onToggle={() => toggleSection('imageAnim')}
            >
              <ImageAnimator onVideoToPool={(fn) => {
                console.log('Animated video added to pool:', fn);
              }} socket={socket} />
            </SectionHeader>
            <SectionHeader
              title="INPAINT CASCATA — Efeito de Agua"
              emoji="💧"
              colorVar="--matrix-green"
              collapsed={collapsedSections.cascadeWater}
              onToggle={() => toggleSection('cascadeWater')}
            >
              <CascadeWaterInpaint onVideoToPool={(fn) => {
                console.log('Cascade video added to pool:', fn);
              }} />
            </SectionHeader>
          </div>

          {/* MEDIA */}
          <div style={{
            display: activeTab === 'media' ? 'block' : 'none',
            position: 'fixed',
            top: 96,
            left: sidebarCollapsed ? 56 : 192,
            right: 0,
            bottom: 0,
            padding: 12,
            overflow: 'hidden',
          }}>
            <MediaTimeline socket={socket} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
