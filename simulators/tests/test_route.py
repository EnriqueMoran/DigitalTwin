import math
from simulators.route import ScenarioRoute


def test_heading_points_to_next_waypoint(tmp_path):
    # Create a simple scenario with two points heading east
    scenario_json = tmp_path / "scenario.json"
    scenario_json.write_text(
        '{"wave_state":"calm","points":[{"lat":0.0,"lon":0.0,"speed":1.0},'
        '{"lat":0.0,"lon":0.01,"speed":1.0}]}',
        encoding="utf-8",
    )

    route = ScenarioRoute(scenario_json)

    # halfway through the segment
    mid_t = route.total_time / 2.0
    lat, lon, _, heading = route.position(mid_t)

    # expected bearing from current position to next waypoint
    exp_heading = route._bearing(lat, lon, route.points[1].lat, route.points[1].lon)
    assert math.isclose(heading, exp_heading)
