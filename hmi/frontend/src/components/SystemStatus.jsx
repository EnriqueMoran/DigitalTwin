import React, { useEffect, useState } from 'react';

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
  // Deprecated: efficiency uses sats_in_view, which we now ignore in UI
  return 50;
}

function gps_quality_percent(quality, gsa_mode, hdop, avg_snr, sats_used, sats_in_view) {
  const fix = score_fix(quality, gsa_mode);
  if (fix === 0) return 0.0;
  const hd = score_hdop(hdop);
  const sn = score_snr(avg_snr);
  const su = score_sat_used(sats_used);
  // Drop efficiency weight; rebalance to emphasize fix/hdop
  const total = 0.45 * fix + 0.30 * hd + 0.15 * sn + 0.10 * su;
  let capped = total;
  if ((sats_used || 0) === 0 || (hdop || 99) >= 99) capped = Math.min(total, 20.0);
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
  const [nowTime, setNowTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNowTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const fmt = (v, unit = '', transform) => {
    if (v === undefined || v === null) return 'Unavaliable';
    const val = transform ? transform(v) : v;
    return `${val}${unit}`;
  };
  const toFixed = (d) => (v) => Number(v).toFixed(d);
  const fmtLocalTime = (ts) => {
    if (ts == null) return null;
    const date = new Date(Number(ts) * 1000);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleTimeString();
  };
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
  const hasQualityInputs =
    sensors.gps_fix_quality != null &&
    sensors.hdop != null &&
    sensors.sats_used != null;

  const fixText = (() => {
    const q = sensors.gps_fix_quality;
    const m = sensors.gsa_mode;
    if (q === 0 || m === 1) return 'NO FIX';
    if (q === 1) return 'GNSS';
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
      ['Uptime', fmt(sensors.uptime, '', formatHHMMSS)],
    ],
  };

  const sensorsSection = {
    title: 'Sensors',
    rows: [
      [
        'IMU',
        (() => {
          const base = sensors.imu_state;
          if (base === 'Unavailable') {
            const t = fmtLocalTime(sensors.last_imu_time);
            return t ? `Unavailable (${t})` : 'Unavailable';
          }
          return fmt(base);
        })(),
      ],
      [
        'GPS',
        (() => {
          const base = sensors.gps_state;
          if (base === 'Unavailable') {
            const t = fmtLocalTime(sensors.last_gps_time);
            return t ? `Unavailable (${t})` : 'Unavailable';
          }
          return fmt(base);
        })(),
      ],
    ],
  };

  const wifiQualityText = (() => {
    const given = sensors.wifi_quality || sensors.wifi_signal;
    if (typeof given === 'string') return given;
    const rssi = sensors.wifi_rssi;
    if (rssi == null) return 'Unavaliable';
    if (rssi >= -55) return 'Excellent';
    if (rssi >= -65) return 'High';
    if (rssi >= -72) return 'Medium';
    if (rssi >= -82) return 'Poor';
    return 'Unavaliable';
  })();

  const battery = {
    title: 'Others',
    rows: [
      ['Current time', nowTime.toLocaleTimeString()],
      ['Wifi Signal', wifiQualityText],
      ['Main Battery', 'Unavaliable'],
      ['Engine Battery', 'Unavaliable'],
    ],
  };

  const gps = {
    title: 'GPS',
    rows: [
      ['Estimated Quality', hasQualityInputs ? fmt(quality, '%') : 'Unavaliable'],
      ['Fix', fixText],
      [
        'Satellites Used',
        sensors.sats_used != null ? `${sensors.sats_used}` : 'Unavaliable',
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
