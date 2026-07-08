(function () {
  const socket = io({
    transports: ['polling', 'websocket'],
    withCredentials: false,
  });
  let currentRunId = null;

  const els = {
    badge: document.getElementById('ws-badge'),
    repoSelect: document.getElementById('repo-path'),
    taskInput: document.getElementById('task-input'),
    useJcode: document.getElementById('use-jcode'),
    reason: document.getElementById('classification-reason'),
    btnDispatch: document.getElementById('btn-dispatch'),
    btnKill: document.getElementById('btn-kill'),
    dispatchStatus: document.getElementById('dispatch-status'),
    outputRunId: document.getElementById('output-run-id'),
    outputModel: document.getElementById('output-model'),
    outputStatus: document.getElementById('output-status'),
    liveOutput: document.getElementById('live-output'),
    historyTbody: document.getElementById('history-tbody'),
    btnRefreshHistory: document.getElementById('btn-refresh-history'),
  };

  socket.on('connect', () => {
    els.badge.classList.add('connected');
    els.badge.title = 'ligado';
    loadRepos();
    loadHistory();
  });

  socket.on('disconnect', () => {
    els.badge.classList.remove('connected');
    els.badge.title = 'desligado';
  });

  socket.on('connect_error', (err) => {
    console.error('Socket.IO error', err);
    els.dispatchStatus.textContent = 'Erro de ligação Socket.IO';
    els.dispatchStatus.className = 'status-msg error';
  });

  socket.on('jcode_stream', (msg) => {
    if (msg.run_id === currentRunId) {
      els.liveOutput.textContent += msg.chunk;
      els.liveOutput.scrollTop = els.liveOutput.scrollHeight;
    }
  });

  socket.on('jcode_status', (msg) => {
    if (msg.run_id === currentRunId) {
      updateStatus(msg.status, msg.returncode, msg.jcode_model);
    }
    loadHistory();
  });

  socket.on('task_dispatched', (d) => {
    currentRunId = d.jcode_run_id;
    els.dispatchStatus.textContent = `Lançado: ${d.id} | jcode=${d.use_jcode}`;
    els.dispatchStatus.className = 'status-msg success';
    els.reason.textContent = d.jcode_classification ? `(${d.jcode_classification.reason}, conf=${d.jcode_classification.confidence})` : '';
    if (currentRunId) {
      els.btnKill.disabled = false;
      els.liveOutput.textContent = '';
      updateStatus('running', null, d.model);
    }
  });

  socket.on('jcode_run_killed', (msg) => {
    if (msg.run_id === currentRunId) updateStatus('cancelled', -1);
    els.btnKill.disabled = true;
    loadHistory();
  });

  socket.on('error', (msg) => {
    els.dispatchStatus.textContent = `Erro: ${msg.message}`;
    els.dispatchStatus.className = 'status-msg error';
  });

  function updateStatus(status, returncode, model) {
    els.outputStatus.textContent = status ? `status: ${status}${returncode !== null && returncode !== undefined ? ` (exit ${returncode})` : ''}` : '';
    els.outputStatus.className = `status-${status}`;
    if (model) els.outputModel.textContent = `model: ${model}`;
    if (currentRunId) els.outputRunId.textContent = `run: ${currentRunId}`;
    if (status === 'completed' || status === 'error' || status === 'cancelled') {
      els.btnKill.disabled = true;
    }
  }

  async function loadRepos() {
    try {
      const r = await fetch('/api/jcode/repos');
      const data = await r.json();
      els.repoSelect.innerHTML = '';
      data.repos.forEach(repo => {
        const opt = document.createElement('option');
        opt.value = repo.path;
        opt.textContent = repo.path;
        els.repoSelect.appendChild(opt);
      });
    } catch (e) {
      console.error('loadRepos', e);
    }
  }

  async function loadHistory() {
    try {
      const r = await fetch('/api/jcode/runs/summary?limit=20');
      const runs = await r.json();
      els.historyTbody.innerHTML = '';
      if (!runs.length) {
        els.historyTbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sem runs.</td></tr>';
        return;
      }
      runs.forEach(run => {
        const tr = document.createElement('tr');
        const statusClass = `status-${run.status}`;
        tr.innerHTML = `
          <td>${run.run_id.replace(/_/g, '_<wbr>')}</td>
          <td class="${statusClass}">${run.status}</td>
          <td>${run.jcode_model || '-'}</td>
          <td>${run.duration_seconds !== null ? run.duration_seconds + 's' : '-'}</td>
          <td>${run.file_ops || 0}</td>
          <td title="${(run.preview || '').replace(/"/g, '&quot;')}">${(run.preview || '').slice(0, 40)}</td>
        `;
        els.historyTbody.appendChild(tr);
      });
    } catch (e) {
      console.error('loadHistory', e);
    }
  }

  function dispatch() {
    const repo = els.repoSelect.value;
    const task = els.taskInput.value.trim();
    const useJcode = els.useJcode.checked;
    if (!task) {
      els.dispatchStatus.textContent = 'Tarefa vazia';
      els.dispatchStatus.className = 'status-msg error';
      return;
    }
    els.dispatchStatus.textContent = 'A lançar...';
    els.dispatchStatus.className = 'status-msg';
    socket.emit('dispatch_task', {
      target_profile: 'developer',
      task,
      repo_path: repo,
      use_jcode: useJcode,
      tool_profile: 'minimal',
      timeout: 600,
    });
  }

  function killRun() {
    if (!currentRunId) return;
    socket.emit('kill_jcode_run', { run_id: currentRunId });
    els.btnKill.disabled = true;
  }

  els.btnDispatch.addEventListener('click', dispatch);
  els.btnKill.addEventListener('click', killRun);
  els.btnRefreshHistory.addEventListener('click', loadHistory);
})();
