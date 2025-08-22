export default function SystemStatus({ sensors = {} }) {
  const fields = [
    ['Connection state', sensors.connection_state],
    ['IMU temperature', sensors.imu_temperature],
    ['Latency', sensors.latency],
    ['Battery status', sensors.battery_status],
    ['GPS signal', sensors.gps_signal],
    ['Uptime', sensors.uptime],
  ];
  return (
    <div>
      <h3>System Status</h3>
      <table>
        <tbody>
          {fields.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value !== undefined && value !== null ? value : 'Null'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
