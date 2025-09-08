export default function SensorData({ sensors = {} }) {
  const toDeg = (r) =>
    r !== undefined && r !== null ? ((r * 180) / Math.PI).toFixed(2) : null;

  const toFixed = (digits) => (v) => Number(v).toFixed(digits);

  const toDMS = (deg) => {
    const absolute = Math.abs(deg);
    const d = Math.floor(absolute);
    const mFloat = (absolute - d) * 60;
    const m = Math.floor(mFloat);
    const s = ((mFloat - m) * 60).toFixed(2);
    const sign = deg < 0 ? '-' : '';
    return `${sign}${d}° ${m}' ${s}"`;
  };

  const fmt = (v, unit = '', transform) => {
    if (v === undefined || v === null) return 'Unavaliable';
    const val = transform ? transform(v) : v;
    return `${val}${unit}`;
  };

  const fmtLatLon = (v) => {
    if (v === undefined || v === null) return 'Unavaliable';
    const dec = Number(v).toFixed(12);
    const extraSpace = v >= 0 ? ' ' : '';
    return `${toDMS(v)}${extraSpace} (${dec})`;
  };

  const fields = [
    ['Latitude', fmtLatLon(sensors.latitude)],
    ['Longitude', fmtLatLon(sensors.longitude)],
    ['Altitude (m)', fmt(sensors.altitude, '', toFixed(2))],
    ['Heading (deg)', fmt(sensors.heading, '', toDeg)],
    ['COG (deg)', fmt(sensors.cog, '', toDeg)],
    ['Roll (deg)', fmt(sensors.roll, '', toDeg)],
    ['Pitch (deg)', fmt(sensors.pitch, '', toDeg)],
    ['SOG (m/s)', fmt(sensors.true_speed, '', toFixed(3))],
  ];
  return (
    <div>
      <h3>Sensor Data</h3>
      <table>
        <tbody>
          {fields.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
