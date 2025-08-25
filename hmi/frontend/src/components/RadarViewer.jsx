import { useMemo, useState } from 'react';

const VIEW_SIZE = 400;
const CENTER = VIEW_SIZE / 2;
const ICON_SIZE = 10;
const HEADING_LEN = 12;

export default function RadarViewer({ sensors }) {
  const tracks = sensors?.radar_tracks ?? [];
  const [range, setRange] = useState(1000); // meters
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
        style={{ flex: 1, background: '#0b2d3c' }}
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
          {visibleTracks.map(renderTrack)}
        </svg>
      </div>
      <div style={{ width: 220, padding: 8, color: '#fff', background: '#444' }}>
        <div style={{ marginBottom: 12 }}>
          <label>
            View range (m): {range}
            <input
              type="range"
              min="100"
              max="5000"
              step="100"
              value={range}
              onChange={(e) => setRange(Number(e.target.value))}
            />
          </label>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>
            <input
              type="checkbox"
              checked={showInfo}
              onChange={(e) => setShowInfo(e.target.checked)}
            />
            Show tracks info
          </label>
        </div>
        {selectedTrack && (
          <div>
            <h4>Selected Track Info</h4>
            <div>Distance (m): {Number(selectedTrack.distance).toFixed(2)}</div>
            <div>Bearing (deg): {Number(selectedTrack.bearing).toFixed(2)}</div>
            <div>Heading (deg): {Number(selectedTrack.heading).toFixed(2)}</div>
            <button onClick={() => setSelected(null)}>Clear selected track</button>
          </div>
        )}
      </div>
    </div>
  );
}

