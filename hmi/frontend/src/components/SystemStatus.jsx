import React from 'react';

function clamp(x, lo, hi) {
  return Math.max(lo, Math.min(hi, x));
}

function score_fix(quality, gsa_mode) {
  if (quality === 0 || gsa_mode === 1) return 0;
  if (quality === 4) return 100;
  if (quality === 5) return 90;
  if (quality === 2) return 80;
  if (quality === 6) return 30;
  if (quality === 1) {
    if (gsa_mode === 2) return 55;
    if (gsa_mode === 3) return 65;
    return 60;
  }
  return 60;
}

function score_hdop(hdop) {
  if (hdop == null) return 50;
  if (hdop >= 99) return 0;
  if (hdop <= 0.8) return 100;
  if (hdop <= 1.5) return 90;
  if (hdop <= 2.5) return 75;
  if (hdop <= 5.0) return 50;
  if (hdop <= 10.0) return 25;
  return 0;
}

function score_snr(avg_snr) {
  if (avg_snr == null) return 50;
  return clamp(((avg_snr - 25.0) / 20.0) * 100.0, 0, 100);
}

function score_sat_used(sats_used, ceiling = 12) {
  if (sats_used == null) return 50;
  return clamp((sats_used / ceiling) * 100.0, 0, 100);
}

function score_efficiency(sats_used, sats_in_view) {
  if (!sats_used || !sats_in_view || sats_in_view <= 0) return 50;
  return clamp((sats_used / sats_in_view) * 100.0, 0, 100);
}

function gps_quality_percent(quality, gsa_mode, hdop, avg_snr, sats_used, sats_in_view) {
  const fix = score_fix(quality, gsa_mode);
  if (fix === 0) return 0.0;
  const hd = score_hdop(hdop);
  const sn = score_snr(avg_snr);
  const su = score_sat_used(sats_used);
  const ef = score_efficiency(sats_used, sats_in_view);
  const total = 0.35 * fix + 0.25 * hd + 0.2 * sn + 0.15 * su + 0.05 * ef;
  let capped = total;
  if ((sats_used || 0) === 0 || (sats_in_view || 0) === 0 || (hdop || 99) >= 99) capped = Math.min(total, 20.0);
  return Number(capped.toFixed(1));
}

function formatHHMMSS(s) {
  if (s == null) return 'Unavaliable';
  const sec = Number(s);
  const h = String(Math.floor(sec / 3600)).padStart(2, '0');
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
  const ss = String(sec % 60).padStart(2, '0');
  return `${h}:${m}:${ss}`;
}

export default function SystemStatus({ sensors = {} }) {
  const fmt = (v, unit = '', transform) => {
    if (v === undefined || v === null) return 'Unavaliable';
    const val = transform ? transform(v) : v;
    return `${val}${unit}`;
  };
  const toFixed = (d) => (v) => Number(v).toFixed(d);
  // Connection display: do not show last message time here; the banner already shows it
  const connectionDisplay = sensors.connection_state ?? 'Unavaliable';

  const quality = gps_quality_percent(
    sensors.gps_fix_quality,
    sensors.gsa_mode,
    sensors.hdop,
    sensors.avg_snr,
    sensors.sats_used,
    sensors.sats_in_view
  );

  const fixText = (() => {
    const q = sensors.gps_fix_quality;
    const m = sensors.gsa_mode;
    if (q === 0 || m === 1) return 'NO FIX';
    if (q === 4) return 'RTK FIX';
    if (q === 5) return 'RTK FLOAT';
    if (q === 2) return 'DGPS';
    if (m === 2) return '2D';
    if (m === 3) return '3D';
    return 'Unavaliable';
  })();

  const precisionText = (() => {
    const h = sensors.hdop;
    if (h == null) return 'Unavaliable';
    if (h < 1) return 'Excellent';
    if (h < 2) return 'Very good';
    if (h < 5) return 'Acceptable';
    if (h < 10) return 'Poor';
    if (h <= 20) return 'Unusable';
    return 'Invalid';
  })();

  const general = {
    title: 'General',
    rows: [
      ['Connection State', connectionDisplay],
      ['Mode', fmt(sensors.mode)],
      ['Latency (s)', fmt(sensors.latency, '', toFixed(3))],
      ['Uptime (HH:MM:SS)', fmt(sensors.uptime, '', formatHHMMSS)],
    ],
  };

  const sensorsSection = {
    title: 'Sensors',
    rows: [
      ['IMU', fmt(sensors.imu_state)],
      ['GPS', fmt(sensors.gps_state)],
    ],
  };

  const battery = {
    title: 'Battery',
    rows: [
      ['Main battery (%)', 'Unavailable'],
      ['Engine battery (%)', 'Unavailable'],
    ],
  };

  const gps = {
    title: 'GPS',
    rows: [
      ['Estimated Quality (%)', fmt(quality, '%')],
      ['Fix', fixText],
      [
        'Satellites Used/Available',
        sensors.sats_used != null || sensors.sats_in_view != null
          ? `${sensors.sats_used || 0}/${sensors.sats_in_view || 0}`
          : 'Unavaliable',
      ],
      ['Precision', precisionText],
    ],
  };

  const Section = ({ title, rows }) => (
    <div className="status-section">
      <h4>{title}</h4>
      <table>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="system-status">
      <h3>System Status</h3>
      <div className="status-grid">
        {/* Row 1: left General, right Battery */}
        <Section title={general.title} rows={general.rows} />
        <Section title={battery.title} rows={battery.rows} />
        {/* Row 2: left Sensors, right GPS (aligned by grid rows) */}
        <Section title={sensorsSection.title} rows={sensorsSection.rows} />
        <Section title={gps.title} rows={gps.rows} />
      </div>
    </div>
  );
}
