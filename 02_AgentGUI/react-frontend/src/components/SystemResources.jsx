import { useState, useEffect } from 'react';

function SystemResources({ socket, compact = false }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!socket) return;
    socket.on('resources_update', (payload) => setData(payload));
    return () => socket.off('resources_update');
  }, [socket]);

  if (!data) {
    if (compact) return null;
    return (
      <div className="flex items-center justify-center h-16 text-[var(--text-dim)] text-xs font-mono">
        <span className="animate-pulse">Initializing resource monitor...</span>
      </div>
    );
  }

  const vm = data.vm || {};
  const win = data.windows;

  if (compact) {
    return (
      <div className="w-full border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]/80 backdrop-blur-sm"
           style={{ padding: '8px 16px' }}>
        <div className="flex items-center gap-6 overflow-x-auto" style={{ minHeight: 38 }}>
          {/* Windows Host */}
          {win ? (
            <>
              <MicroBar label="W-CPU" value={win.cpu?.percent || 0} color="#00d4ff" />
              <MicroBar label="W-RAM" value={win.ram?.percent || 0} color="#00ff41" />
              <MicroBar label="C:" value={win.disks?.c?.percent || 0} color="#ffb800" />
              <MicroBar label="D:" value={win.disks?.d?.percent || 0} color="#ff7b00" />
              {win.gpu && <MicroBar label="GPU" value={win.gpu.gpu_percent || 0} color="#b829dd" />}
            </>
          ) : (
            <span className="text-[10px] font-mono text-[var(--text-dim)] whitespace-nowrap">Waiting for Windows host...</span>
          )}

          {/* Divider */}
          <div className="w-px h-5 bg-[var(--border-subtle)] flex-shrink-0" />

          {/* VM */}
          <MicroBar label="V-CPU" value={vm.cpu?.percent || 0} color="#4a6a5a" />
          <MicroBar label="V-RAM" value={vm.ram?.percent || 0} color="#4a6a5a" />
          <MicroBar label="V-DISK" value={vm.disk?.percent || 0} color="#4a6a5a" />
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-6">
      {/* WINDOWS HOST */}
      <div className="resource-panel resource-panel-windows">
        <div className="resource-header">
          <div className="w-2 h-2 rounded-full bg-[var(--cyber-blue)] animate-pulse mr-2" />
          <span className="resource-title" style={{ color: 'var(--cyber-blue)' }}>
            WINDOWS HOST
          </span>
          <span className="resource-subtitle">
            {win ? (win.hostname || 'Active') : 'Waiting...'}
          </span>
        </div>

        {win ? (
          <div className="grid grid-cols-2 xl:grid-cols-5 gap-2">
            <MiniBar label="CPU" value={win.cpu?.percent || 0} sub={`${win.cpu?.cores || 0} cores`} color="#00d4ff" />
            <MiniBar label="RAM" value={win.ram?.percent || 0} sub={`${win.ram?.used_gb || 0}/${win.ram?.total_gb || 0} GB`} color="#00ff41" />
            <MiniBar label="DISK C:" value={win.disks?.c?.percent || 0} sub={`${win.disks?.c?.used_gb || 0}/${win.disks?.c?.total_gb || 0} GB`} color="#ffb800" />
            <MiniBar label="DISK D:" value={win.disks?.d?.percent || 0} sub={`${win.disks?.d?.used_gb || 0}/${win.disks?.d?.total_gb || 0} GB`} color="#ff7b00" />
            {win.gpu ? (
              <MiniBar label="GPU" value={win.gpu.gpu_percent || 0} sub={`${win.gpu.vram_used_mb || 0}/${win.gpu.vram_total_mb || 0} MB`} color="#b829dd" />
            ) : (
              <MiniBar label="GPU" value={0} sub="No NVIDIA" color="#555" />
            )}
          </div>
        ) : (
          <div className="text-xs text-[var(--text-muted)] font-mono py-3 px-2 border border-dashed border-[var(--border-subtle)] rounded">
            Waiting for Windows host monitor... Run start_agentgui.bat to activate.
          </div>
        )}
      </div>

      {/* DIVIDER for mobile (hidden on xl) */}
      <div className="xl:hidden h-px bg-gradient-to-r from-transparent via-[var(--border-subtle)] to-transparent my-1" />

      {/* VM */}
      <div className="resource-panel resource-panel-vm">
        <div className="resource-header">
          <div className="w-2 h-2 rounded-full bg-[var(--text-muted)] mr-2" />
          <span className="resource-title" style={{ color: 'var(--text-muted)' }}>
            VM UBUNTU
          </span>
          <span className="resource-subtitle">{vm.ram?.total_gb || '?'} GB RAM</span>
        </div>

        <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
          <MiniBar label="CPU" value={vm.cpu?.percent || 0} sub={`${vm.cpu?.cores || 0} cores`} color="#4a6a5a" />
          <MiniBar label="RAM" value={vm.ram?.percent || 0} sub={`${vm.ram?.used_gb || 0}/${vm.ram?.total_gb || 0} GB`} color="#4a6a5a" />
          <MiniBar label="DISK" value={vm.disk?.percent || 0} sub={`${vm.disk?.used_gb || 0}/${vm.disk?.total_gb || 0} GB`} color="#4a6a5a" />
        </div>
      </div>
    </div>
  );
}

function MicroBar({ label, value, color }) {
  const safeValue = Math.min(Math.max(Number(value) || 0, 0), 100);
  return (
    <div className="flex items-center gap-2 flex-shrink-0" title={`${label}: ${Math.round(safeValue)}%`}>
      <span className="text-[10px] font-mono font-bold whitespace-nowrap" style={{ color, width: 38, textAlign: 'right' }}>{label}</span>
      <div className="rounded-full overflow-hidden" style={{ width: 48, height: 5, background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
        <div
          className="h-full rounded-full"
          style={{
            width: `${safeValue}%`,
            backgroundColor: color,
            opacity: 0.9,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <span className="text-[9px] font-mono" style={{ color, minWidth: 24 }}>{Math.round(safeValue)}%</span>
    </div>
  );
}

function MiniBar({ label, value, sub, color }) {
  const safeValue = Math.min(Math.max(Number(value) || 0, 0), 100);
  const isMed = safeValue >= 50 && safeValue < 80;
  const isHigh = safeValue >= 80;

  let glowClass = '';
  if (isMed) glowClass = 'bar-glow-med';
  if (isHigh) glowClass = 'bar-glow-high';

  return (
    <div className="mini-card">
      <div className="flex items-center justify-between mb-1">
        <span className="mini-label" style={{ color }}>{label}</span>
        <span className="mini-value" style={{ color }}>{Math.round(safeValue)}%</span>
      </div>
      <div className="mini-track">
        <div
          className={`mini-fill ${glowClass}`}
          style={{
            width: `${safeValue}%`,
            backgroundColor: color,
            opacity: 0.85,
          }}
        />
      </div>
      <div className="mini-sub">{sub}</div>
    </div>
  );
}

export default SystemResources;
