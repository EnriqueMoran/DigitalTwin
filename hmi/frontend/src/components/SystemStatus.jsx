export default function SystemStatus({ sensors = {} }) {
  const fmt = (v, unit = '', transform, decimals) => {
    if (v === undefined || v === null) return 'Null';
    let val = transform ? transform(v) : v;
    if (decimals !== undefined) val = parseFloat(Number(val).toFixed(decimals));
    return `${val}${unit}`;
  };
  const toPercent = (v) => (v <= 1 ? (v * 100).toFixed(0) : v.toFixed(0));
  const fields = [
    ['Connection state', sensors.connection_state ?? 'Null'],
    ['IMU temperature (deg)', fmt(sensors.imu_temperature)],
    ['Latency (s)', fmt(sensors.latency, '', null, 3)],
    ['Battery status (%)', fmt(sensors.battery_status, '%', toPercent)],
    ['GPS signal (fix)', fmt(sensors.gps_signal)],
    ['Uptime (s)', fmt(sensors.uptime)],
  ];
  return (
    <div>
      <h3>System Status</h3>
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
