export default function Widgets({ sensors = {} }) {
  const toDeg = (r) => (r !== undefined && r !== null ? (r * 180 / Math.PI).toFixed(1) : 'Null');
  const heading = sensors.heading !== undefined && sensors.heading !== null ? toDeg(sensors.heading) + '°' : 'Null';
  const cog = sensors.cog !== undefined && sensors.cog !== null ? toDeg(sensors.cog) + '°' : 'Null';
  const roll = sensors.roll !== undefined && sensors.roll !== null ? toDeg(sensors.roll) + '°' : 'Null';
  const pitch = sensors.pitch !== undefined && sensors.pitch !== null ? toDeg(sensors.pitch) + '°' : 'Null';
  const estSpeed =
    sensors.estimated_speed !== undefined && sensors.estimated_speed !== null
      ? String(sensors.estimated_speed)
      : 'Null';
  const trueSpeed =
    sensors.true_speed !== undefined && sensors.true_speed !== null
      ? String(sensors.true_speed)
      : 'Null';

  return (
    <div>
      <h3>Widgets</h3>
      <div>Compass: heading {heading}, COG {cog}</div>
      <div>Attitude: roll {roll}, pitch {pitch}</div>
      <div>Speed: estimated {estSpeed}, true {trueSpeed}</div>
    </div>
  );
}
