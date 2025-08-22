export default function Widgets({ sensors = {} }) {
  const heading = sensors.heading ?? 'Null';
  const cog = sensors.cog ?? 'Null';
  const roll = sensors.roll ?? 'Null';
  const pitch = sensors.pitch ?? 'Null';
  const estSpeed = sensors.estimated_speed ?? 'Null';
  const trueSpeed = sensors.true_speed ?? 'Null';

  return (
    <div>
      <h3>Widgets</h3>
      <div>Compass: heading {heading}, COG {cog}</div>
      <div>Attitude: roll {roll}, pitch {pitch}</div>
      <div>Speed: estimated {estSpeed}, true {trueSpeed}</div>
    </div>
  );
}
