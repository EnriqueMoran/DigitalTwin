import { useEffect, useRef, useState } from 'react';

function Compass({ heading = 0, cog = null, size = 150 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const s = canvas.width;
    ctx.clearRect(0, 0, s, s);

    // outer circle
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(s / 2, s / 2, s / 2 - 5, 0, 2 * Math.PI);
    ctx.stroke();

    // cardinal points
    ctx.fillStyle = '#fff';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', s / 2, 15);
    ctx.fillText('S', s / 2, s - 15);
    ctx.fillText('E', s - 15, s / 2);
    ctx.fillText('W', 15, s / 2);

    // heading needle
    ctx.save();
    ctx.translate(s / 2, s / 2);
    ctx.rotate(heading || 0);
    ctx.strokeStyle = 'red';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -s / 2 + 15);
    ctx.stroke();
    ctx.restore();

    if (cog !== null && cog !== undefined) {
      ctx.save();
      ctx.translate(s / 2, s / 2);
      ctx.rotate(cog);
      ctx.strokeStyle = 'orange';
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(0, -s / 2 + 15);
      ctx.stroke();
      ctx.restore();
    }
  }, [heading, cog, size]);

  return <canvas ref={canvasRef} width={size} height={size} className="widget-canvas" />;
}

function AttitudeIndicator({ roll = 0, pitch = 0, size = 150 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.rotate(-roll);
    const pitchPixels = (pitch / (Math.PI / 2)) * (h / 2);
    ctx.translate(0, pitchPixels);

    ctx.fillStyle = '#004c99';
    ctx.fillRect(-w, -h * 2, w * 2, h * 2); // sky
    ctx.fillStyle = '#663300';
    ctx.fillRect(-w, 0, w * 2, h * 2); // ground

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-w, 0);
    ctx.lineTo(w, 0);
    ctx.stroke(); // horizon

    ctx.restore();

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, w / 2 - 5, 0, 2 * Math.PI);
    ctx.stroke(); // outer circle

    ctx.beginPath(); // aircraft symbol
    ctx.moveTo(w / 2 - 20, h / 2);
    ctx.lineTo(w / 2 + 20, h / 2);
    ctx.moveTo(w / 2, h / 2);
    ctx.lineTo(w / 2, h / 2 + 30);
    ctx.stroke();
  }, [roll, pitch, size]);

  return <canvas ref={canvasRef} width={size} height={size} className="widget-canvas" />;
}

function Speedometer({ value = 0, max = 10, size = 150 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const radius = Math.min(w, h) / 2 - 5;
    ctx.clearRect(0, 0, w, h);

    ctx.save();
    ctx.translate(w / 2, h / 2);
    const start = Math.PI * 1.25; // 225 deg
    const total = Math.PI * 1.5; // 270 deg sweep

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, radius, start, start - total, true);
    ctx.stroke();

    for (let i = 0; i <= 5; i++) {
      const value = (max / 5) * i;
      const angle = start - (value / max) * total;
      const x1 = radius * Math.cos(angle);
      const y1 = radius * Math.sin(angle);
      const x2 = (radius - 10) * Math.cos(angle);
      const y2 = (radius - 10) * Math.sin(angle);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      // Show labels with exactly two decimals to avoid FP artifacts
      ctx.fillText(value.toFixed(2), (radius - 25) * Math.cos(angle), (radius - 25) * Math.sin(angle));
    }

    const angle = start - (value / max) * total;
    ctx.strokeStyle = 'lime';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo((radius - 15) * Math.cos(angle), (radius - 15) * Math.sin(angle));
    ctx.stroke();
    ctx.restore();
  }, [value, max, size]);

  return <canvas ref={canvasRef} width={size} height={size} className="widget-canvas" />;
}

export default function Widgets({ sensors = {} }) {
  const wrapRef = useRef(null);
  const [size, setSize] = useState(150);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      let newSize = 150;
      if (w < 3 * 150 + 32) newSize = 130;
      if (w < 3 * 130 + 32) newSize = 110;
      setSize(newSize);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const toDeg = (r) => (r * 180) / Math.PI;
  const fmt3 = (rad) => {
    let d = ((toDeg(rad ?? 0) % 360) + 360) % 360;
    d = Math.round(d) % 360;
    return String(d).padStart(3, '0');
  };
  return (
    <div ref={wrapRef}>
      <h3>Widgets</h3>
      <div className="widgets">
        <div className="widget">
          <h4>Heading</h4>
          <Compass heading={sensors.heading} cog={sensors.cog} size={size} />
          <div className="value value-kv">
            <span className="kv-key"><span className="legend-color heading"></span>HDG:</span>
            <span className="kv-value">{((toDeg(sensors.heading ?? 0) + 360) % 360).toFixed(0)}°</span>
            <span className="kv-key"><span className="legend-color cog"></span>COG:</span>
            <span className="kv-value">{((toDeg(sensors.cog ?? 0) + 360) % 360).toFixed(0)}°</span>
          </div>
        </div>
        <div className="widget">
          <h4>Attitude</h4>
          <AttitudeIndicator roll={sensors.roll} pitch={sensors.pitch} size={size} />
          <div className="value value-kv">
            <span className="kv-key">Roll:</span>
            <span className="kv-value">{toDeg(sensors.roll ?? 0).toFixed(2)}°</span>
            <span className="kv-key">Pitch:</span>
            <span className="kv-value">{toDeg(sensors.pitch ?? 0).toFixed(2)}°</span>
          </div>
        </div>
        <div className="widget">
          <h4>Speed</h4>
          <Speedometer value={sensors.true_speed} size={size} />
          <div className="value">{(sensors.true_speed ?? 0).toFixed(2)} m/s</div>
        </div>
      </div>
    </div>
  );
}
