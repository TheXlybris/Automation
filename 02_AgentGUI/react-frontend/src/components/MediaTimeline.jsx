import { useState, useRef, useEffect } from 'react';
import './MediaTimeline.css';

/* ─── MEDIA TIMELINE v2.8 — Add Track Row + Existing Tracks ─── */

const ZOOM_LEVELS = [0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16];

const TYPE_CONFIG = {
  video: { label: 'VIDEO',  color: '#00d4ff', icon: '▶', accept: ['mp4','mov','avi','mkv','webm'] },
  audio: { label: 'AUDIO',  color: '#00ff41', icon: '♫', accept: ['mp3','wav','aac','flac','ogg','m4a'] },
  fx:    { label: 'FX',     color: '#ffb800', icon: '✦', accept: ['fx','json'] },
};

const VIDEO_EXTS = ['mp4','mov','avi','mkv','webm'];
const AUDIO_EXTS = ['mp3','wav','aac','flac','ogg','m4a'];

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  if (h > 0) return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')}`;
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(2,'0')}`;
}

function formatShortTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function snap(val, grid) { return Math.round(val / grid) * grid; }

function snapCeil(val, grid) { return Math.ceil(val / grid) * grid; }

function inferType(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  if (VIDEO_EXTS.includes(ext)) return 'video';
  if (AUDIO_EXTS.includes(ext)) return 'audio';
  return 'fx';
}

function inferDuration(fileData) {
  if (fileData && typeof fileData.duration === 'number') return fileData.duration;
  return 30;
}

let trackCounter = 0;

export default function MediaTimeline({ socket }) {
  const [zoomIndex, setZoomIndex] = useState(4);
  const [duration, setDuration] = useState(28800);
  const [playhead, setPlayhead] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [clips, setClips] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [selectedClip, setSelectedClip] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [selectedMediaSet, setSelectedMediaSet] = useState(new Set());
  const [selectedClipSet, setSelectedClipSet] = useState(new Set());
  const [clipboard, setClipboard] = useState(null); // { type: 'pool'|'timeline', items: [] }
  const [selectBox, setSelectBox] = useState(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [dragOverAddRow, setDragOverAddRow] = useState(false);
  const [dragOverTrackId, setDragOverTrackId] = useState(null);
  const [isDraggingOverPool, setIsDraggingOverPool] = useState(false);

  const timelineRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const playTimerRef = useRef(null);
  const audioRef = useRef(null);
  const lastClipRef = useRef(null);
  const videoRef = useRef(null);
  const lastVideoClipRef = useRef(null);
  const selectionPoolStartRef = useRef(null);
  const selectionTimelineStartRef = useRef(null);

  const zoom = ZOOM_LEVELS[zoomIndex];
  const pxPerSec = 10 * zoom;
  const gridSize = zoom >= 1 ? 1 : zoom >= 0.1 ? 10 : 60;
  const labelStep = zoom >= 1 ? 5 : zoom >= 0.5 ? 10 : zoom >= 0.1 ? 60 : 300;
  const tickStep = zoom >= 2 ? 1 : zoom >= 1 ? 1 : zoom >= 0.5 ? 5 : zoom >= 0.1 ? 10 : 60;

  const [scrollInfo, setScrollInfo] = useState({ left: 0, width: 1200 });

  const contentEnd = clips.length > 0 ? Math.max(...clips.map(c => c.start + c.length)) : 0;

  useEffect(() => { fetchMediaList(); }, []);

  const fetchMediaList = async () => {
    try {
      const res = await fetch(`${window.location.origin}/api/media/list`);
      const data = await res.json();
      setMediaFiles(data.files || []);
    } catch (e) { console.log('Media list fetch failed:', e); }
  };

  /* ═══ MULTI-TRACK PLAYBACK ═══ */
  const audioRefs = useRef({}); // { clipId: Audio }
  const activeClipsRef = useRef([]);

  useEffect(() => {
    if (!isPlaying) {
      clearInterval(playTimerRef.current);
      Object.values(audioRefs.current).forEach(a => a.pause());
      activeClipsRef.current = [];
      return;
    }
    playTimerRef.current = setInterval(() => {
      setPlayhead(p => {
        const next = p + 0.1;
        if (next >= contentEnd && contentEnd > 0) { setIsPlaying(false); return contentEnd; }
        if (next >= duration) { setIsPlaying(false); return duration; }
        return next;
      });
    }, 100);
    return () => clearInterval(playTimerRef.current);
  }, [isPlaying, contentEnd, duration]);

  useEffect(() => {
    const now = playhead;
    // Todos os clips que intersetam o playhead atual
    const activeClips = clips.filter(c => now >= c.start && now < c.start + c.length);
    const audioExts = AUDIO_EXTS;

    const prevIds = new Set(activeClipsRef.current.map(c => c.id));
    const currIds = new Set(activeClips.map(c => c.id));

    // Parar clips que sairam
    prevIds.forEach(id => {
      if (!currIds.has(id) && audioRefs.current[id]) {
        audioRefs.current[id].pause();
      }
    });

    // Liminar refs de clips que já nao existem
    Object.keys(audioRefs.current).forEach(id => {
      if (!clips.find(c => c.id === id)) {
        delete audioRefs.current[id];
      }
    });

    activeClipsRef.current = activeClips;

    // Iniciar/atualizar clips ativos
    activeClips.forEach(clip => {
      if (!audioExts.some(ext => clip.label.toLowerCase().endsWith(ext))) return;
      const media = mediaFiles.find(m => m.name === clip.label);
      if (!media) return;
      const url = `${window.location.origin}/api/media/file/${encodeURIComponent(media.name)}`;
      const offset = now - clip.start;

      let a = audioRefs.current[clip.id];
      if (!a) {
        a = new Audio();
        a.volume = 1.0;
        audioRefs.current[clip.id] = a;
      }

      if (a.src !== url) {
        a.src = url;
      }

      // Sincronizar tempo
      const syncThreshold = 0.3;
      if (Math.abs(a.currentTime - offset) > syncThreshold || a.paused) {
        a.currentTime = Math.max(0, offset);
      }

      if (isPlaying && a.paused) {
        a.play().catch(err => console.log('Multi-audio play blocked:', err));
      }
    });
  }, [playhead, isPlaying, clips, mediaFiles]);

  /* ═══ VIDEO PLAYBACK ═══ */
  useEffect(() => {
    const clip = clips.find(c => playhead >= c.start && playhead < c.start + c.length && VIDEO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext)));
    const isVideoClip = !!clip;
    if (!isVideoClip) {
      if (videoRef.current) { videoRef.current.pause(); videoRef.current.src = ''; }
      lastVideoClipRef.current = null;
      return;
    }
    const media = mediaFiles.find(m => m.name === clip.label);
    if (!media) return;
    const url = `${window.location.origin}/api/media/file/${encodeURIComponent(media.name)}`;
    if (!videoRef.current) return;
    const v = videoRef.current;
    const offset = playhead - clip.start;
    if (lastVideoClipRef.current !== clip.id) {
      lastVideoClipRef.current = clip.id;
      if (v.src !== url) { v.src = url; v.load(); }
      const onLoaded = () => {
        v.currentTime = Math.max(0, offset);
        if (isPlaying) v.play().catch(err => console.log('Video play blocked:', err));
        v.removeEventListener('loadedmetadata', onLoaded);
      };
      v.addEventListener('loadedmetadata', onLoaded);
      return;
    }
    // Same clip — sync scrub
    const targetTime = Math.max(0, offset);
    if (Math.abs(v.currentTime - targetTime) > 0.3) {
      v.currentTime = targetTime;
    }
    if (v.paused && isPlaying) {
      v.play().catch(err => console.log('Video resume blocked:', err));
    }
    if (!isPlaying && !v.paused) {
      v.pause();
    }
  }, [playhead, isPlaying, clips, mediaFiles]);

  const getClipAtPlayhead = () => clips.find(c => playhead >= c.start && playhead < c.start + c.length);

  useEffect(() => {
    const onKey = (e) => {
      if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault(); setIsPlaying(p => !p);
      }
      if (e.key === 'Delete') {
        if (selectedClipSet.size > 0) {
          selectedClipSet.forEach(id => deleteClip(id));
          setSelectedClipSet(new Set());
        } else if (selectedMediaSet.size > 0) {
          selectedMediaSet.forEach(name => deleteMediaFile(name));
          setSelectedMediaSet(new Set());
          setSelectedMedia(null);
        }
      }
      // ═══ COPY / PASTE ═══
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        if (selectedMediaSet.size > 0) {
          const items = mediaFiles.filter(m => selectedMediaSet.has(m.name));
          setClipboard({ type: 'pool', items: items.map(m => ({ ...m })) });
        } else if (selectedClipSet.size > 0) {
          const items = clips.filter(c => selectedClipSet.has(c.id)).map(c => ({ ...c, _offset: playhead }));
          setClipboard({ type: 'timeline', items });
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v' && clipboard) {
        e.preventDefault();
        if (clipboard.type === 'pool') {
          // Pool paste: not meaningful (pool items are files), ignore
        } else if (clipboard.type === 'timeline') {
          const pasted = clipboard.items.map(c => {
            const newId = 'c' + Date.now() + '_' + Math.random().toString(36).slice(2,5);
            const start = c._offset !== undefined ? c._offset : playhead;
            return { ...c, id: newId, start: snap(start, gridSize), _offset: undefined };
          });
          setClips(prev => [...prev, ...pasted]);
          setSelectedClipSet(new Set(pasted.map(c => c.id)));
          setSelectedMediaSet(new Set());
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        // Select all timeline clips or all pool items
        if (document.activeElement?.closest?.('.media-pool')) {
          setSelectedMediaSet(new Set(mediaFiles.map(m => m.name)));
          setSelectedClipSet(new Set());
        } else {
          setSelectedClipSet(new Set(clips.map(c => c.id)));
          setSelectedMediaSet(new Set());
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedClip, selectedMedia, selectedClipSet, selectedMediaSet, clips, mediaFiles, playhead, clipboard, gridSize]);

  useEffect(() => {
    const onWheel = (e) => {
      if (e.ctrlKey) {
        e.preventDefault();
        setZoomIndex(i => e.deltaY < 0 ? Math.min(i + 1, ZOOM_LEVELS.length - 1) : Math.max(i - 1, 0));
      }
    };
    window.addEventListener('wheel', onWheel, { passive: false });
    return () => window.removeEventListener('wheel', onWheel);
  }, []);

  /* ═══ TRACK MANAGEMENT ═══ */
  const createTrack = (type) => {
    const count = tracks.filter(t => t.type === type).length + 1;
    const id = `t${trackCounter++}`;
    const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.fx;
    const name = `${cfg.label} ${count}`;
    setTracks(prev => [...prev, { id, type, name, label: cfg.label, icon: cfg.icon, color: cfg.color }]);
    return id;
  };

  const deleteClip = (id) => {
    setClips(prev => {
      const next = prev.filter(c => c.id !== id);
      const usedTracks = new Set(next.map(c => c.track));
      setTracks(t => t.filter(track => usedTracks.has(track.id)));
      return next;
    });
    if (selectedClip === id) setSelectedClip(null);
  };

  const updateClip = (id, patch) => {
    setClips(prev => prev.map(c => c.id === id ? { ...c, ...patch } : c));
  };

  /* ═══ MEDIA POOL ═══ */
  const handlePoolDragOver = (e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; setIsDraggingOverPool(true); };
  const handlePoolDragLeave = (e) => { e.preventDefault(); setIsDraggingOverPool(false); };

  const handlePoolDrop = async (e) => {
    e.preventDefault(); e.stopPropagation();
    setIsDraggingOverPool(false);
    const files = e.dataTransfer.files;
    if (!files || !files.length) return;
    let uploaded = 0;
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch(`${window.location.origin}/api/media/upload`, { method: 'POST', body: formData });
        if (res.ok) uploaded++;
      } catch (err) { console.error('Upload failed:', err); }
    }
    if (uploaded > 0) fetchMediaList();
  };

  const deleteMediaFile = async (filename) => {
    try {
      await fetch(`${window.location.origin}/api/media/delete/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      setMediaFiles(prev => prev.filter(f => f.name !== filename));
      if (selectedMedia === filename) setSelectedMedia(null);
    } catch (e) { console.error('Delete failed:', e); }
  };

  /* ═══ DRAG FROM POOL ═══ */
  const handleMediaDragStart = (e, file) => {
    e.dataTransfer.effectAllowed = 'copy';
    const filesToDrag = selectedMediaSet.size > 0
      ? mediaFiles.filter(f => selectedMediaSet.has(f.name))
      : [file];
    e.dataTransfer.setData('text/plain', JSON.stringify(filesToDrag));
    const ghost = document.createElement('div');
    ghost.textContent = `${filesToDrag.length} ficheiro${filesToDrag.length > 1 ? 's' : ''}`;
    ghost.style.cssText = 'position:absolute;top:-1000px;padding:4px 8px;background:#0e1a22;border:1px solid #00d4ff;border-radius:4px;color:#00d4ff;font-size:10px;font-family:monospace;';
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 0, 0);
    setTimeout(() => document.body.removeChild(ghost), 0);
  };

  const findFreeSlot = (existingClips, desiredStart, length, shouldSnap = true) => {
    const trackClips = [...existingClips].sort((a, b) => a.start - b.start);
    let candidate = Math.max(0, desiredStart);
    let wasPushed = false;
    for (const c of trackClips) {
      if (candidate + length > c.start && candidate < c.start + c.length) {
        candidate = c.start + c.length;
        wasPushed = true;
      }
    }
    // Se foi empurrado para depois de um clip, nao fazer snap (colar exatamente)
    if (shouldSnap && !wasPushed) {
      return snap(candidate, gridSize);
    }
    return candidate;
  };
  const handleAddRowDragOver = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    setDragOverAddRow(true);
  };
  const handleAddRowDragLeave = () => setDragOverAddRow(false);
  const handleAddRowDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setDragOverAddRow(false);
    if (!timelineRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    let startSec = snap(Math.max(0, x / pxPerSec), gridSize);

    let payload = null;
    try { const text = e.dataTransfer.getData('text/plain'); if (text) payload = JSON.parse(text); } catch (_) {}

    if (!payload) return;
    const filesArray = Array.isArray(payload) ? payload : [payload];
    if (filesArray.length === 0) return;

    const firstType = inferType(filesArray[0].name);
    const trackId = createTrack(firstType);
    const newClips = [];
    let currentStart = startSec;

    filesArray.forEach((fileData) => {
      if (!fileData || !fileData.name) return;
      const type = inferType(fileData.name);
      // Se tipo diferente do primeiro, criar nova faixa; senao usar a mesma
      const targetTrackId = type === firstType ? trackId : createTrack(type);
      const len = inferDuration(fileData);
      // Verificar collision na faixa de destino
      const trackExisting = clips.filter(c => c.track === targetTrackId);
      const placeAt = findFreeSlot(trackExisting, currentStart, len, false);
      const id = 'c' + Date.now() + '_' + Math.random().toString(36).slice(2,5);
      const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.fx;
      newClips.push({ id, track: targetTrackId, start: placeAt, length: len, label: fileData.name, color: cfg.color });
      currentStart = placeAt + len;
    });

    if (newClips.length > 0) {
      setClips(prev => [...prev, ...newClips]);
      setSelectedClip(newClips[newClips.length - 1].id);
    }
  };

  /* ═══ EXISTING TRACK — drop here to ADD to existing track ═══ */
  const handleTrackDragOver = (e, trackId) => {
    e.preventDefault(); e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    setDragOverTrackId(trackId);
  };
  const handleTrackDragLeave = () => setDragOverTrackId(null);
  const handleTrackDrop = (e, trackId) => {
    e.preventDefault(); e.stopPropagation();
    setDragOverTrackId(null);
    if (!timelineRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    let startSec = snap(Math.max(0, x / pxPerSec), gridSize);

    let payload = null;
    try { const text = e.dataTransfer.getData('text/plain'); if (text) payload = JSON.parse(text); } catch (_) {}

    if (!payload) return;
    const filesArray = Array.isArray(payload) ? payload : [payload];
    if (filesArray.length === 0) return;

    const track = tracks.find(t => t.id === trackId);
    const newClips = [];
    let currentStart = startSec;

    filesArray.forEach((fileData) => {
      if (!fileData || !fileData.name) return;
      const type = inferType(fileData.name);
      let targetTrackId = trackId;
      if (track && track.type !== type) {
        targetTrackId = createTrack(type);
      }
      const len = inferDuration(fileData);
      const trackExisting = clips.filter(c => c.track === targetTrackId);
      const placeAt = findFreeSlot(trackExisting, currentStart, len, false);
      const id = 'c' + Date.now() + '_' + Math.random().toString(36).slice(2,5);
      const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.fx;
      newClips.push({ id, track: targetTrackId, start: placeAt, length: len, label: fileData.name, color: cfg.color });
      currentStart = placeAt + len;
    });

    if (newClips.length > 0) {
      setClips(prev => [...prev, ...newClips]);
      setSelectedClip(newClips[newClips.length - 1].id);
    }
  };

  /* ═══ CLIP DRAG/RESIZE ═══ */
  const handleClipMouseDown = (e, clip, mode) => {
    e.stopPropagation();
    if (!timelineRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const offsetX = e.clientX - rect.left - (clip.start * pxPerSec);
    setDragState({ clipId: clip.id, offsetX, mode });
    setSelectedClip(clip.id);
  };

  useEffect(() => {
    if (!dragState) return;
    const handleMove = (e) => {
      if (!timelineRef.current) return;
      const rect = timelineRef.current.getBoundingClientRect();
      const rawX = e.clientX - rect.left - dragState.offsetX;
      const clip = clips.find(c => c.id === dragState.clipId);
      if (!clip) return;
      if (dragState.mode === 'move') {
        const desiredStart = snap(Math.max(0, rawX / pxPerSec), gridSize);
        const others = clips.filter(c => c.track === clip.track && c.id !== clip.id);
        const freeStart = findFreeSlot(others, desiredStart, clip.length);
        updateClip(clip.id, { start: freeStart });
      } else if (dragState.mode === 'resize-r') {
        updateClip(clip.id, { length: snap(Math.max(clip.start + gridSize, rawX / pxPerSec), gridSize) - clip.start });
      } else if (dragState.mode === 'resize-l') {
        const newStart = snap(Math.max(0, Math.min(clip.start + clip.length - gridSize, rawX / pxPerSec)), gridSize);
        updateClip(clip.id, { start: newStart, length: clip.start + clip.length - newStart });
      }
    };
    const handleUp = () => setDragState(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => { window.removeEventListener('mousemove', handleMove); window.removeEventListener('mouseup', handleUp); };
  }, [dragState, clips, pxPerSec, gridSize]);

  const handleRulerClick = (e) => {
    if (!timelineRef.current || dragState) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setPlayhead(snap(Math.max(0, x / pxPerSec), 0.1));
  };

  useEffect(() => {
    if (!scrollContainerRef.current) return;
    const el = scrollContainerRef.current;
    const onScroll = () => setScrollInfo({ left: el.scrollLeft, width: el.clientWidth });
    el.addEventListener('scroll', onScroll);
    setScrollInfo({ left: el.scrollLeft, width: el.clientWidth });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!scrollContainerRef.current || !isPlaying) return;
    const px = playhead * pxPerSec;
    const viewL = scrollContainerRef.current.scrollLeft;
    const viewW = scrollContainerRef.current.clientWidth;
    if (px < viewL || px > viewL + viewW - 50) {
      scrollContainerRef.current.scrollTo({ left: Math.max(0, px - viewW / 2), behavior: 'smooth' });
    }
  }, [playhead, pxPerSec, isPlaying]);

  const totalWidth = Math.max(duration * pxPerSec, 1200);

  /* ═══════ RENDER ═══════ */
  return (
    <div className="media-timeline-v2">
      {/* ═══ TOP ROW ═══ */}
      <div className="timeline-top-row">
        {/* Media Pool */}
        <div
          className="media-pool"
          onDragOver={handlePoolDragOver}
          onDragLeave={handlePoolDragLeave}
          onDrop={handlePoolDrop}
          style={isDraggingOverPool ? { borderColor: 'var(--matrix-green)', boxShadow: '0 0 20px rgba(0,255,65,0.15)' } : {}}
        >
          <div className="media-pool-header">
            <span className="text-[10px] font-mono font-bold tracking-wider text-[var(--cyber-blue)]">🗁 MEDIA POOL</span>
            <span className="text-[9px] font-mono text-[var(--text-muted)]">{mediaFiles.length} ficheiros</span>
          </div>
          <div className="media-pool-dropzone">
            {mediaFiles.length === 0 && (
              <div className="media-pool-empty" style={isDraggingOverPool ? { borderColor: 'var(--matrix-green)', background: 'rgba(0,255,65,0.03)' } : {}}>
                <div className="text-2xl mb-2">📁</div>
                <div className="text-xs font-mono text-[var(--text-dim)]">Arraste ficheiros para aqui</div>
                <div className="text-[10px] font-mono text-[var(--text-dim)] mt-1">MP4, MP3, WAV, MOV...</div>
              </div>
            )}
            <div className="media-pool-grid"
              onMouseDown={(e) => {
                if (e.button !== 0) return;
                if (e.target.closest('.media-pool-item')) return;
                const rect = e.currentTarget.getBoundingClientRect();
                selectionPoolStartRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
                setIsSelecting(true);
                setSelectBox(null);
                if (!e.ctrlKey && !e.metaKey) {
                  setSelectedMediaSet(new Set());
                  setSelectedClipSet(new Set());
                }
                e.stopPropagation();
              }}
              onMouseMove={(e) => {
                if (!isSelecting || !selectionPoolStartRef.current) return;
                const rect = e.currentTarget.getBoundingClientRect();
                const x2 = e.clientX - rect.left;
                const y2 = e.clientY - rect.top;
                const x1 = selectionPoolStartRef.current.x;
                const y1 = selectionPoolStartRef.current.y;
                setSelectBox({
                  left: Math.min(x1, x2),
                  top: Math.min(y1, y2),
                  width: Math.abs(x2 - x1),
                  height: Math.abs(y2 - y1),
                });
              }}
              onMouseUp={(e) => {
                if (!isSelecting) return;
                setIsSelecting(false);
                if (!selectBox) { setSelectBox(null); selectionPoolStartRef.current = null; return; }
                const rect = e.currentTarget.getBoundingClientRect();
                const items = e.currentTarget.querySelectorAll('.media-pool-item');
                const newSet = e.ctrlKey || e.metaKey ? new Set(selectedMediaSet) : new Set();
                items.forEach((item) => {
                  const r = item.getBoundingClientRect();
                  const ix = r.left - rect.left;
                  const iy = r.top - rect.top;
                  if (
                    ix < selectBox.left + selectBox.width && ix + r.width > selectBox.left &&
                    iy < selectBox.top + selectBox.height && iy + r.height > selectBox.top
                  ) {
                    const name = item.querySelector('.media-pool-name')?.textContent;
                    if (name) newSet.add(name);
                  }
                });
                setSelectedMediaSet(newSet);
                setSelectBox(null);
                selectionPoolStartRef.current = null;
              }}
            >
              {selectBox && (
                <div style={{
                  position: 'absolute',
                  left: selectBox.left,
                  top: selectBox.top,
                  width: selectBox.width,
                  height: selectBox.height,
                  border: '1px dashed var(--matrix-green)',
                  background: 'rgba(0,255,65,0.08)',
                  pointerEvents: 'none',
                  zIndex: 50,
                }} />
              )}
              {mediaFiles.map(file => {
                const type = inferType(file.name);
                const isSelected = selectedMediaSet.has(file.name);
                return (
                  <div key={file.name}
                    draggable
                    onDragStart={(e) => handleMediaDragStart(e, file)}
                    onClick={(ev) => {
                      if (ev.ctrlKey || ev.metaKey) {
                        setSelectedMediaSet(prev => {
                          const next = new Set(prev);
                          if (next.has(file.name)) next.delete(file.name); else next.add(file.name);
                          return next;
                        });
                        setSelectedClipSet(new Set());
                      } else {
                        setSelectedMediaSet(new Set([file.name]));
                        setSelectedClipSet(new Set());
                      }
                    }}
                    className={`media-pool-item ${isSelected ? 'media-pool-item-selected' : ''}`}
                  >
                    <div className="media-pool-thumb">
                      {type === 'video' ? (
                        <img
                          src={`${window.location.origin}/api/media/thumbnail/${encodeURIComponent(file.name)}`}
                          alt=""
                          onError={(e) => {
                            const p = e.target.parentElement;
                            e.target.style.display = 'none';
                            const s = document.createElement('span');
                            s.textContent = '▶';
                            p.appendChild(s);
                          }}
                        />
                      ) : type === 'audio' ? <span>♫</span> : <span>✦</span>}
                    </div>
                    <div className="media-pool-name">{file.name}</div>
                    <div className="media-pool-meta">{file.duration_human || file.size_human}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="media-preview">
          <div className="media-preview-header">
            <span className="text-[10px] font-mono font-bold tracking-wider text-[var(--text-secondary)]">▣ PREVIEW</span>
            <span className="text-[10px] font-mono text-[var(--matrix-green)]">{formatTime(playhead)} / {formatTime(duration)}</span>
          </div>
          <div className="media-preview-canvas" style={{ position: 'relative', display: 'flex', flexDirection: 'column' }}>
            {/* Vídeo sempre no DOM — useEffect controla src/play/tempo */}
            <video
              ref={videoRef}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                background: '#000',
                zIndex: 2,
                display: clips.some(c => playhead >= c.start && playhead < c.start + c.length && VIDEO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext))) ? 'block' : 'none'
              }}
              playsInline
            />
            {(() => {
              const now = playhead;
              const activeClips = clips.filter(c => now >= c.start && now < c.start + c.length);
              const videoClips = activeClips.filter(c => VIDEO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext)));
              const audioClips = activeClips.filter(c => AUDIO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext)));
              const fxClips = activeClips.filter(c => !VIDEO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext)) && !AUDIO_EXTS.some(ext => c.label.toLowerCase().endsWith(ext)));

              const mainPanel = (() => {
                if (videoClips.length > 0) return (
                  <div style={{ flex: '1 1 auto', minHeight: 0 }} /> // empurra mixer para o fundo
                );
                if (audioClips.length > 0) {
                  return (
                    <div className="media-preview-placeholder" style={{ flex: '1 1 auto' }}>
                      <div className="text-3xl mb-1" style={{ color: '#00ff41', animation: isPlaying ? 'pulse 1s infinite' : 'none' }}>♫</div>
                      <div className="text-[10px] font-mono text-[var(--text-dim)]">{audioClips.length} faixa{audioClips.length !== 1 ? 's' : ''} de áudio ativa{audioClips.length !== 1 ? 's' : ''}</div>
                      <div className="flex items-center gap-1 mt-1">
                        {Array.from({ length: 16 }).map((_, i) => (
                          <div key={i} style={{ width: 3, height: Math.random() * 20 + 3, background: '#00ff41', borderRadius: 1, opacity: isPlaying ? 0.7 : 0.2, transition: 'height 0.1s' }} />
                        ))}
                      </div>
                    </div>
                  );
                }
                return (
                  <div className="media-preview-placeholder" style={{ flex: '1 1 auto' }}>
                    <div className="text-4xl mb-3 opacity-20">🎬</div>
                    <div className="text-xs font-mono text-[var(--text-dim)]">Pré-visualização</div>
                    <div className="text-[10px] font-mono text-[var(--text-dim)] mt-1">{clips.length} clip{clips.length !== 1 ? 's' : ''} na timeline</div>
                  </div>
                );
              })();

              const mixerPanel = activeClips.length > 0 && (
                <div style={{
                  display: 'flex',
                  gap: '2px',
                  padding: '3px 4px',
                  background: 'rgba(0,0,0,0.5)',
                  borderTop: '1px solid rgba(255,255,255,0.06)',
                  minHeight: '28px',
                  maxHeight: '28px',
                  overflowX: 'auto',
                  overflowY: 'hidden',
                  alignItems: 'center',
                  fontSize: '8px',
                  fontFamily: "'JetBrains Mono', monospace",
                  zIndex: 3,
                }}>
                  {videoClips.map((c) => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '1px 4px', borderRadius: '3px', background: 'rgba(0,255,65,0.08)', whiteSpace: 'nowrap', color: '#00ff41' }}>
                      <span>🎬</span>
                      <span style={{ maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.label.slice(0, 12)}</span>
                    </div>
                  ))}
                  {audioClips.map((c) => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '1px 4px', borderRadius: '3px', background: 'rgba(0,212,255,0.08)', whiteSpace: 'nowrap', color: '#00d4ff' }}>
                      <span>♫</span>
                      <span style={{ maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.label.slice(0, 12)}</span>
                      {isPlaying && (
                        <div style={{ display: 'flex', gap: '1px', alignItems: 'flex-end' }}>
                          {[3,6,2,8,4,7,3,5].map((h, idx) => (
                            <div key={idx} style={{ width: 2, height: Math.random() > 0.3 ? h : 2, background: '#00d4ff', borderRadius: 1, transition: 'height 0.1s' }} />
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {fxClips.map((c) => (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '2px', padding: '1px 4px', borderRadius: '3px', background: 'rgba(255,165,0,0.08)', whiteSpace: 'nowrap', color: '#ffa500' }}>
                      <span>✦</span>
                      <span style={{ maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.label.slice(0, 12)}</span>
                    </div>
                  ))}
                </div>
              );

              return (
                <>
                  {mainPanel}
                  {mixerPanel}
                </>
              );
            })()}
          </div>
          <div className="media-preview-controls">
            <button onClick={() => setPlayhead(0)} className="preview-btn">⏮</button>
            <button onClick={() => setIsPlaying(!isPlaying)} className="preview-btn preview-btn-play">{isPlaying ? '⏸' : '▶'}</button>
            <button onClick={() => setPlayhead(Math.min(duration, contentEnd))} className="preview-btn">⏭</button>
            <div className="flex-1 mx-3">
              <input type="range" min={0} max={Math.max(contentEnd, 60)} step={0.1} value={playhead}
                onChange={(e) => setPlayhead(Number(e.target.value))} className="w-full accent-[var(--matrix-green)] h-1" />
            </div>
            <span className="text-[10px] font-mono text-[var(--text-muted)] w-24 text-right">{formatTime(playhead)}</span>
          </div>
        </div>

        {/* Properties placeholder */}
        <div className="media-properties-placeholder">
          <span className="text-[10px] font-mono text-[var(--text-dim)]">PROPRIEDADES</span>
          <span className="text-[9px] font-mono text-[var(--text-dim)] mt-1">(v2.8)</span>
        </div>
      </div>

      {/* ═══ BOTTOM: Timeline ═══ */}
      <div className="timeline-bottom">
        {/* Toolbar */}
        <div className="timeline-toolbar-compact">
          <div className="flex items-center gap-3">
            <button onClick={() => setIsPlaying(!isPlaying)} className="btn-glow px-2 py-1 rounded font-mono text-[10px]"
              style={{ background: isPlaying ? 'var(--alert-red)' : 'var(--matrix-green)', color: isPlaying ? '#fff' : 'var(--bg-primary)' }}>
              {isPlaying ? '⏸' : '▶'}
            </button>
            <span className="text-[10px] font-mono text-[var(--matrix-green)] w-28">{formatTime(playhead)}</span>
            <div className="flex items-center gap-1">
              <span className="text-[9px] font-mono text-[var(--text-muted)]">ZOOM</span>
              <input type="range" min={0} max={ZOOM_LEVELS.length - 1} step={1} value={zoomIndex}
                onChange={(e) => setZoomIndex(Number(e.target.value))} className="w-20 accent-[var(--matrix-green)]" />
              <span className="text-[9px] font-mono text-[var(--text-secondary)] w-10">{zoom}x</span>
            </div>
            <div className="flex items-center gap-1 ml-2">
              <span className="text-[9px] font-mono text-[var(--text-muted)]">DURAÇÃO</span>
              <input type="number" min={60} max={86400} step={60} value={Math.round(duration)}
                onChange={(e) => setDuration(Number(e.target.value))} className="agent-input text-[10px] w-16 text-center py-1" />
              <span className="text-[9px] font-mono text-[var(--text-muted)]">s</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono text-[var(--text-dim)]">{tracks.length} faixa{tracks.length !== 1 ? 's' : ''} | {clips.length} clip{clips.length !== 1 ? 's' : ''} | Conteúdo: {formatTime(contentEnd)}</span>
            <button onClick={() => { setClips([]); setTracks([]); trackCounter = 0; setSelectedClip(null); }} className="text-[9px] font-mono text-[var(--alert-red)] hover:underline ml-2">Limpar Timeline</button>
          </div>
        </div>

        {/* Timeline body: fixed headers + scrollable content */}
        <div className="timeline-body-v2">
          {/* Fixed headers column (left) */}
          <div className="timeline-headers-fixed">
            <div className="timeline-ruler-header" />
            <div className="timeline-header-row add-track-header-row">
              <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>+</span>
              <span className="text-[9px] font-mono tracking-wider" style={{ color: 'var(--text-muted)' }}>NOVA FAIXA</span>
            </div>
            {tracks.map(track => (
              <div key={track.id} className="timeline-header-row" style={{ borderLeftColor: track.color }}>
                <div className="flex items-center gap-1">
                  <span style={{ color: track.color, fontSize: 14 }}>{track.icon}</span>
                  <span className="text-[9px] font-mono tracking-wider" style={{ color: track.color }}>{track.name}</span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <button onClick={(e) => { e.stopPropagation(); createTrack(track.type); }}
                    className="text-[8px] font-mono px-1 rounded hover:opacity-80"
                    style={{ background: track.color + '20', color: track.color, border: `1px solid ${track.color}40` }}
                    title="Nova faixa deste tipo">+</button>
                  <button onClick={(e) => { e.stopPropagation(); setTracks(prev => prev.filter(t => t.id !== track.id)); setClips(prev => prev.filter(c => c.track !== track.id)); }}
                    className="text-[8px] font-mono px-1 rounded hover:opacity-80"
                    style={{ background: 'rgba(255,45,45,0.1)', color: '#ff2d2d', border: '1px solid rgba(255,45,45,0.3)' }}
                    title="Remover faixa">×</button>
                </div>
              </div>
            ))}
          </div>

          {/* Scrollable content (right) */}
          <div className="timeline-scrollable-v2" ref={scrollContainerRef}>

            {/* Ruler */}
            <div className="timeline-ruler" style={{ width: totalWidth }} onClick={handleRulerClick}>
              {(() => {
                const marginPx = 200;
                const startPx = Math.max(0, scrollInfo.left - marginPx);
                const endPx = scrollInfo.left + scrollInfo.width + marginPx;
                const startSec = Math.floor(startPx / pxPerSec / tickStep) * tickStep;
                const endSec = Math.ceil(endPx / pxPerSec / tickStep) * tickStep;
                const ticks = [];
                for (let sec = startSec; sec <= endSec; sec += tickStep) {
                  if (sec > duration) break;
                  const isLabel = sec % labelStep === 0;
                  const isMajor = sec % 60 === 0;
                  const isMid = sec % 10 === 0;
                  ticks.push(
                    <div key={sec} className="ruler-tick" style={{ left: sec * pxPerSec }}>
                      <div className="ruler-line" style={{
                        height: isLabel ? 14 : isMid ? 9 : isMajor ? 7 : 4,
                        background: isLabel ? 'var(--matrix-green)' : isMid ? 'var(--border-active)' : 'var(--border-subtle)',
                        opacity: isLabel ? 1 : 0.5,
                      }} />
                      {isLabel && <span className="ruler-label">{formatShortTime(sec)}</span>}
                    </div>
                  );
                }
                return ticks;
              })()}
            </div>

            {/* Lanes — headers are now in fixed column on the left */}
            <div ref={timelineRef} className="timeline-lanes-v2" style={{ width: totalWidth }}
              onMouseDown={(e) => {
                if (e.button !== 0) return;
                if (e.target.closest('.timeline-clip')) return;
                const rect = e.currentTarget.getBoundingClientRect();
                selectionTimelineStartRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
                setIsSelecting(true);
                setSelectBox(null);
                if (!e.ctrlKey && !e.metaKey) {
                  setSelectedClipSet(new Set());
                  setSelectedMediaSet(new Set());
                }
                e.stopPropagation();
              }}
              onMouseMove={(e) => {
                if (!isSelecting || !selectionTimelineStartRef.current) return;
                const rect = e.currentTarget.getBoundingClientRect();
                const x2 = e.clientX - rect.left;
                const y2 = e.clientY - rect.top;
                const x1 = selectionTimelineStartRef.current.x;
                const y1 = selectionTimelineStartRef.current.y;
                setSelectBox({
                  left: Math.min(x1, x2),
                  top: Math.min(y1, y2),
                  width: Math.abs(x2 - x1),
                  height: Math.abs(y2 - y1),
                });
              }}
              onMouseUp={(e) => {
                if (!isSelecting) return;
                setIsSelecting(false);
                if (!selectBox) { setSelectBox(null); selectionTimelineStartRef.current = null; return; }
                const rect = e.currentTarget.getBoundingClientRect();
                const clipsEl = e.currentTarget.querySelectorAll('.timeline-clip');
                const newSet = e.ctrlKey || e.metaKey ? new Set(selectedClipSet) : new Set();
                clipsEl.forEach((el) => {
                  const r = el.getBoundingClientRect();
                  const ix = r.left - rect.left;
                  const iy = r.top - rect.top;
                  if (
                    ix < selectBox.left + selectBox.width && ix + r.width > selectBox.left &&
                    iy < selectBox.top + selectBox.height && iy + r.height > selectBox.top
                  ) {
                    const clipId = el.getAttribute('data-clip-id');
                    if (clipId) newSet.add(clipId);
                  }
                });
                setSelectedClipSet(newSet);
                setSelectBox(null);
                selectionTimelineStartRef.current = null;
              }}
            >
              {selectBox && (
                <div style={{
                  position: 'absolute',
                  left: selectBox.left,
                  top: selectBox.top,
                  width: selectBox.width,
                  height: selectBox.height,
                  border: '1px dashed var(--matrix-green)',
                  background: 'rgba(0,255,65,0.08)',
                  pointerEvents: 'none',
                  zIndex: 50,
                }} />
              )}

              {/* ADD TRACK ROW — drop here to CREATE new track */}
              <div
                className={`timeline-lane-v2 add-track-row ${dragOverAddRow ? 'add-track-row-active' : ''}`}
                onDragOver={handleAddRowDragOver}
                onDragLeave={handleAddRowDragLeave}
                onDrop={handleAddRowDrop}
              >
                <div className="lane-content add-track-content">
                  <span className="text-[10px] font-mono text-[var(--text-dim)] px-2">
                    {dragOverAddRow ? 'Soltar para criar nova faixa' : 'Arraste aqui para criar nova faixa'}
                  </span>
                </div>
              </div>

              {/* EXISTING TRACKS */}
              {tracks.map(track => (
                <div
                  key={track.id}
                  className={`timeline-lane-v2 ${dragOverTrackId === track.id ? 'track-drag-over' : ''}`}
                  onDragOver={(e) => handleTrackDragOver(e, track.id)}
                  onDragLeave={handleTrackDragLeave}
                  onDrop={(e) => handleTrackDrop(e, track.id)}
                >
                  <div className="lane-content">
                    {(() => {
                      const marginPx = 200;
                      const startPx = Math.max(0, scrollInfo.left - marginPx);
                      const endPx = scrollInfo.left + scrollInfo.width + marginPx;
                      const startI = Math.floor(startPx / pxPerSec / gridSize);
                      const endI = Math.ceil(endPx / pxPerSec / gridSize);
                      const lines = [];
                      for (let i = startI; i <= endI; i++) {
                        const sec = i * gridSize;
                        if (sec > duration) break;
                        const majorInterval = gridSize > 0 ? Math.max(1, Math.round(60 / gridSize)) : 60;
                        lines.push(
                          <div key={i} className="track-grid-line"
                            style={{ left: i * gridSize * pxPerSec, opacity: i % majorInterval === 0 ? 0.12 : 0.04 }} />
                        );
                      }
                      return lines;
                    })()}
                    {clips.filter(c => c.track === track.id).map(clip => (
                      <div key={clip.id}
                        data-clip-id={clip.id}
                        className={`timeline-clip ${selectedClipSet.has(clip.id) ? 'clip-selected' : ''}`}
                        style={{ left: clip.start * pxPerSec, width: Math.max(6, clip.length * pxPerSec), background: clip.color + '1a', borderColor: clip.color + '80' }}
                        onClick={(ev) => {
                          if (ev.ctrlKey || ev.metaKey) {
                            setSelectedClipSet(prev => {
                              const next = new Set(prev);
                              if (next.has(clip.id)) next.delete(clip.id); else next.add(clip.id);
                              return next;
                            });
                            setSelectedMediaSet(new Set());
                            ev.stopPropagation();
                          } else {
                            setSelectedClipSet(new Set([clip.id]));
                            setSelectedMediaSet(new Set());
                          }
                        }}
                        onMouseDown={(e) => handleClipMouseDown(e, clip, 'move')}
                      >
                        <div className="clip-handle clip-handle-l" onMouseDown={(e) => handleClipMouseDown(e, clip, 'resize-l')} />
                        <div className="clip-label-wrapper">
                          <span className="clip-label" style={{ color: clip.color }}>{clip.label}</span>
                          <span className="clip-time">{formatTime(clip.length)}</span>
                        </div>
                        <div className="clip-handle clip-handle-r" onMouseDown={(e) => handleClipMouseDown(e, clip, 'resize-r')} />
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Playhead */}
              <div className="playhead" style={{ left: playhead * pxPerSec }}>
                <div className="playhead-triangle" />
                <div className="playhead-line" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
