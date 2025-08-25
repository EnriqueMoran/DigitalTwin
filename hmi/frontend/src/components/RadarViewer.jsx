import { useMemo, useState } from 'react';

const VIEW_SIZE = 400;
const CENTER = VIEW_SIZE / 2;
const ICON_SIZE = 10;
const HEADING_LEN = 12;

export default function RadarViewer({ sensors }) {
  const tracks = sensors?.radar_tracks ?? [];
  const [range, setRange] = useState(10); // meters
  const [showInfo, setShowInfo] = useState(true);
  const [selected, setSelected] = useState(null);

  const visibleTracks = useMemo(() => {
    return tracks
      .map((t, index) => ({ ...t, index }))
      .filter((t) => Number(t.distance) <= range);
  }, [tracks, range]);

  const scale = CENTER / range;

  const handleBackgroundClick = () => setSelected(null);
  const handleSelect = (idx, e) => {
    e.stopPropagation();
    setSelected(idx);
  };

  const renderTrack = (t) => {
    const distance = Number(t.distance) || 0;
    const bearing = Number(t.bearing) || 0;
    const heading = Number(t.heading) || 0;
    const br = (bearing * Math.PI) / 180;
    const hr = (heading * Math.PI) / 180;
    const x = CENTER + Math.sin(br) * distance * scale;
    const y = CENTER - Math.cos(br) * distance * scale;
    const hx = Math.sin(hr) * HEADING_LEN;
    const hy = -Math.cos(hr) * HEADING_LEN;

    const corner = ICON_SIZE + 6;
    const cLen = 6;

    return (
      <g
        key={t.index}
        transform={`translate(${x},${y})`}
        onClick={(e) => handleSelect(t.index, e)}
        style={{ cursor: 'pointer' }}
      >
        {selected === t.index && (
          <g stroke="lime" strokeWidth={2}>
            <line x1={-corner} y1={-corner} x2={-corner + cLen} y2={-corner} />
            <line x1={-corner} y1={-corner} x2={-corner} y2={-corner + cLen} />
            <line x1={corner} y1={-corner} x2={corner - cLen} y2={-corner} />
            <line x1={corner} y1={-corner} x2={corner} y2={-corner + cLen} />
            <line x1={-corner} y1={corner} x2={-corner + cLen} y2={corner} />
            <line x1={-corner} y1={corner} x2={-corner} y2={corner - cLen} />
            <line x1={corner} y1={corner} x2={corner - cLen} y2={corner} />
            <line x1={corner} y1={corner} x2={corner} y2={corner - cLen} />
          </g>
        )}

        <rect
          x={-ICON_SIZE}
          y={-ICON_SIZE}
          width={ICON_SIZE * 2}
          height={ICON_SIZE * 2}
          transform="rotate(45)"
          stroke="yellow"
          fill="none"
        />
        <circle cx={0} cy={0} r={3} fill="yellow" />
        <line x1={0} y1={0} x2={hx} y2={hy} stroke="yellow" strokeWidth={2} />
        {showInfo && (
          <text
            x={0}
            y={ICON_SIZE + 12}
            fill="white"
            textAnchor="middle"
            fontSize="10"
          >
            {`DST:${distance.toFixed(0)}m BRG:${bearing.toFixed(0)}° HDG:${heading.toFixed(0)}°`}
          </text>
        )}
      </g>
    );
  };

  const selectedTrack =
    selected != null && tracks[selected] ? tracks[selected] : null;

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      <div
        style={{
          height: '100%',
          aspectRatio: '1 / 1',
          background: '#0b2d3c',
          flex: '0 0 auto',
        }}
        onClick={handleBackgroundClick}
      >
        <svg viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`} width="100%" height="100%">
          <line
            x1={0}
            y1={CENTER}
            x2={VIEW_SIZE}
            y2={CENTER}
            stroke="#2d4f61"
            strokeWidth={1}
          />
          <line
            x1={CENTER}
            y1={0}
            x2={CENTER}
            y2={VIEW_SIZE}
            stroke="#2d4f61"
            strokeWidth={1}
          />
          {[0.25, 0.5, 0.75].map((p) => {
            const d = (range * p).toFixed(2);
            const offset = CENTER * p;
            return (
              <g key={p}>
                <line
                  x1={CENTER + offset}
                  y1={CENTER - 4}
                  x2={CENTER + offset}
                  y2={CENTER + 4}
                  stroke="#2d4f61"
                />
                <text
                  x={CENTER + offset}
                  y={CENTER + 16}
                  fill="white"
                  fontSize="10"
                  textAnchor="middle"
                >
                  {d}
                </text>
                <line
                  x1={CENTER - 4}
                  y1={CENTER - offset}
                  x2={CENTER + 4}
                  y2={CENTER - offset}
                  stroke="#2d4f61"
                />
                <text
                  x={CENTER + 8}
                  y={CENTER - offset - 2}
                  fill="white"
                  fontSize="10"
                >
                  {d}
                </text>
                <line
                  x1={CENTER - offset}
                  y1={CENTER - 4}
                  x2={CENTER - offset}
                  y2={CENTER + 4}
                  stroke="#2d4f61"
                />
                <text
                  x={CENTER - offset}
                  y={CENTER + 16}
                  fill="white"
                  fontSize="10"
                  textAnchor="middle"
                >
                  {d}
                </text>
                <line
                  x1={CENTER - 4}
                  y1={CENTER + offset}
                  x2={CENTER + 4}
                  y2={CENTER + offset}
                  stroke="#2d4f61"
                />
                <text
                  x={CENTER + 8}
                  y={CENTER + offset + 10}
                  fill="white"
                  fontSize="10"
                >
                  {d}
                </text>
              </g>
            );
          })}
          {visibleTracks.map(renderTrack)}
        </svg>
      </div>
      <div
        style={{
          flex: 1,
          minWidth: 220,
          padding: 8,
          color: '#fff',
          background: '#444',
          overflow: 'auto',
        }}
      >
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column' }}>
            View range (m): {range}
            <input
              type="range"
              min="1"
              max="10"
              step="1"
              value={range}
              onChange={(e) => setRange(Number(e.target.value))}
            />
          </label>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <input
              type="checkbox"
              checked={showInfo}
              onChange={(e) => setShowInfo(e.target.checked)}
            />
            Show tracks info
          </label>
        </div>
        <div>
          <h4>Selected Track Info</h4>
          <form style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>Distance (m):</span>
              <input
                type="text"
                value={
                  selectedTrack
                    ? Number(selectedTrack.distance).toFixed(2)
                    : ''
                }
                readOnly
                style={{
                  background: 'transparent',
                  color: 'inherit',
                  border: 'none',
                }}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>Bearing (deg):</span>
              <input
                type="text"
                value={
                  selectedTrack
                    ? Number(selectedTrack.bearing).toFixed(2)
                    : ''
                }
                readOnly
                style={{
                  background: 'transparent',
                  color: 'inherit',
                  border: 'none',
                }}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>Heading (deg):</span>
              <input
                type="text"
                value={
                  selectedTrack
                    ? Number(selectedTrack.heading).toFixed(2)
                    : ''
                }
                readOnly
                style={{
                  background: 'transparent',
                  color: 'inherit',
                  border: 'none',
                }}
              />
            </label>
          </form>
        </div>
      </div>
    </div>
  );
}

