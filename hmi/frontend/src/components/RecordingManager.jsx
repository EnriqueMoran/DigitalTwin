import { useEffect, useMemo, useRef, useState } from 'react';

const API_BASE = (import.meta && import.meta.env && import.meta.env.VITE_BACKEND_HTTP) || 'http://localhost:8001';

function sanitizeName(name) {
  const base = (name || '').trim().replace(/\s+/g, '_').replace(/[^a-zA-Z0-9_-]/g, '_') || 'recording';
  return base.toLowerCase().endsWith('.json') ? base : base + '.json';
}

export default function RecordingManager() {
  const wrapRef = useRef(null);
  const [compact, setCompact] = useState(false);
  const [topics, setTopics] = useState([]);
  const [selected, setSelected] = useState([]);
  const [allFiles, setAllFiles] = useState([]);

  const [recName, setRecName] = useState('session');
  const [recStatus, setRecStatus] = useState({ active: false, paused: false, count: 0, file: null });

  const [repFile, setRepFile] = useState('');
  const [repSelected, setRepSelected] = useState([]);
  const [repStatus, setRepStatus] = useState({ active: false, paused: false, count: 0, file: null, index: 0, total: 0 });

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const repSelectedSet = useMemo(() => new Set(repSelected), [repSelected]);

  useEffect(() => {
    fetch(`${API_BASE}/topics`).then(r => r.json()).then(d => {
      const t = d.topics || [];
      setTopics(t);
      // Default select all topics for record and replay
      setSelected(t);
      setRepSelected(t);
    }).catch(() => {});
    const load = () => fetch(`${API_BASE}/recordings`).then(r => r.json()).then(d => setAllFiles(d.files || [])).catch(() => {});
    load();
    const id = setInterval(() => {
      fetch(`${API_BASE}/recording/status`).then(r => r.json()).then(setRecStatus).catch(() => {});
      fetch(`${API_BASE}/replay/status`).then(r => r.json()).then(setRepStatus).catch(() => {});
      load();
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Detect available width to render compact two-column layout (for bottom panels)
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect;
      setCompact(rect.width < 820);
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const startRecording = async () => {
    const body = { filename: sanitizeName(recName), topics: selected.length ? selected : undefined };
    await fetch(`${API_BASE}/recording/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  };
  const pauseRecording = async () => { await fetch(`${API_BASE}/recording/pause`, { method: 'POST' }); };
  const resumeRecording = async () => { await fetch(`${API_BASE}/recording/resume`, { method: 'POST' }); };
  const stopRecording = async () => { await fetch(`${API_BASE}/recording/stop`, { method: 'POST' }); };

  const startReplay = async () => {
    if (!repFile) return;
    const body = { filename: repFile, topics: repSelected.length ? repSelected : undefined };
    await fetch(`${API_BASE}/replay/start`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  };
  const pauseReplay = async () => { await fetch(`${API_BASE}/replay/pause`, { method: 'POST' }); };
  const resumeReplay = async () => { await fetch(`${API_BASE}/replay/resume`, { method: 'POST' }); };
  const stopReplay = async () => { await fetch(`${API_BASE}/replay/stop`, { method: 'POST' }); };

  const toggle = (t) => setSelected((s) => s.includes(t) ? s.filter(x => x !== t) : [...s, t]);
  const toggleRep = (t) => setRepSelected((s) => s.includes(t) ? s.filter(x => x !== t) : [...s, t]);

  // Equal-width sections; always stretch to panel height with small margin
  const sectionStyle = compact
    ? { flex: '1 1 0', minWidth: 0, border: '1px solid #ddd', padding: 8, borderRadius: 6, display: 'flex', flexDirection: 'column', height: 'calc(100% - 12px)', minHeight: 0 }
    : { flex: '1 1 0', minWidth: 0, border: '1px solid #ddd', padding: 12, borderRadius: 6, display: 'flex', flexDirection: 'column', height: 'calc(100% - 36px)', minHeight: 0 };
  const listStyle = { width: '100%', overflow: 'auto', border: '1px solid #eee', padding: 6, boxSizing: 'border-box' };

  const controlHeight = compact ? 28 : 30;
  const padY = compact ? 4 : 5;
  const nameInputStyle = { width: '100%', minWidth: 80, height: controlHeight, paddingTop: padY, paddingBottom: padY, paddingLeft: 6, paddingRight: 6, lineHeight: `${controlHeight - padY * 2}px`, boxSizing: 'border-box', textAlign: 'left' };
  const selectStyle = { width: '100%', height: controlHeight, padding: '2px 6px', boxSizing: 'border-box' };
  const rowStyle = { display: 'flex', gap: 4, alignItems: 'center', marginBottom: 8, minHeight: controlHeight };
  const labelStyle = { flex: '0 0 auto', textAlign: 'left', whiteSpace: 'nowrap' };
  const rowGridRecord = { display: 'grid', gridTemplateColumns: 'auto 1fr auto', columnGap: 8, alignItems: 'center', marginBottom: 8, minHeight: controlHeight };
  const rowGridReplay = { display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 8, alignItems: 'center', marginBottom: 8, minHeight: controlHeight };
  const headingStyle = { margin: '0 0 6px 0' };

  return (
    <div ref={wrapRef} style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start', height: '100%', minHeight: 0 }}>
      <section style={sectionStyle}>
        <h3 style={{ marginTop: 0 }}>Recording Manager</h3>
        <div style={rowGridRecord}>
          <label style={labelStyle}>File name:</label>
          <input style={nameInputStyle} value={recName} onChange={(e) => setRecName(e.target.value.replace(/\s+/g, '_'))} placeholder="recording" />
          <span style={{ whiteSpace: 'nowrap' }}>.json</span>
        </div>
        <div style={{ marginBottom: 8, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <b style={headingStyle}>Topics to record</b>
          <div style={{ margin: '6px 0' }}>
            <button onClick={() => setSelected(topics)}>Select All</button>
            <button onClick={() => setSelected([])} style={{ marginLeft: 6 }}>Clear</button>
          </div>
          <div style={{ ...listStyle, flex: 1, minHeight: 0 }}>
            {topics.map(t => (
              <label key={t} style={{ display: 'block' }}>
                <input type="checkbox" checked={selectedSet.has(t)} onChange={() => toggle(t)} /> {t}
              </label>
            ))}
          </div>
        </div>
        <div style={{ ...rowStyle, marginTop: 8, marginBottom: 0 }}>
          {!recStatus.active && <button onClick={startRecording}>Start</button>}
          {recStatus.active && !recStatus.paused && <button onClick={pauseRecording}>Pause</button>}
          {recStatus.active && recStatus.paused && <button onClick={resumeRecording}>Resume</button>}
          {recStatus.active && <button onClick={stopRecording}>Stop</button>}
          <span style={{ marginLeft: 'auto' }}>Count: {recStatus.count ?? 0}</span>
        </div>
      </section>

      <section style={sectionStyle}>
        <h3 style={{ marginTop: 0 }}>Replay</h3>
        <div style={rowGridReplay}>
          <label style={labelStyle}>Recording file:</label>
          <select style={selectStyle} value={repFile} onChange={(e) => setRepFile(e.target.value)}>
            <option value="">-- select file --</option>
            {allFiles.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div style={{ marginBottom: 8, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <b style={headingStyle}>Topics to replay</b>
          <div style={{ margin: '6px 0' }}>
            <button onClick={() => setRepSelected(topics)}>Select All</button>
            <button onClick={() => setRepSelected([])} style={{ marginLeft: 6 }}>Clear</button>
          </div>
          <div style={{ ...listStyle, flex: 1, minHeight: 0 }}>
            {topics.map(t => (
              <label key={t} style={{ display: 'block' }}>
                <input type="checkbox" checked={repSelectedSet.has(t)} onChange={() => toggleRep(t)} /> {t}
              </label>
            ))}
          </div>
        </div>
        <div style={{ ...rowStyle, marginTop: 8, marginBottom: 0 }}>
          {!repStatus.active && <button onClick={startReplay} disabled={!repFile}>Play</button>}
          {repStatus.active && !repStatus.paused && <button onClick={pauseReplay}>Pause</button>}
          {repStatus.active && repStatus.paused && <button onClick={resumeReplay}>Resume</button>}
          {repStatus.active && <button onClick={stopReplay}>Stop</button>}
          <span style={{ marginLeft: 'auto' }}>Played: {repStatus.count ?? 0} / {repStatus.total ?? 0}</span>
        </div>
      </section>
    </div>
  );
}
