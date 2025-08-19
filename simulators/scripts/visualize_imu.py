# Real-time 3D visualization of the MPU9250 simulator driving a simple boat model.

import math
import time
import itertools
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from simulators.imu_sim.lib.imu_sim import MPU9250

# ---------------------------
# Rotations (degrees helpers)
# ---------------------------

def Rx(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[1, 0, 0],
                     [0, c,-s],
                     [0, s, c]], float)

def Ry(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[ c, 0, s],
                     [ 0, 1, 0],
                     [-s, 0, c]], float)

def Rz(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[c,-s, 0],
                     [s, c, 0],
                     [0, 0, 1]], float)

def euler_R_world_to_sensor(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """Compose rotation world->sensor as R = Rx(roll) @ Ry(pitch) @ Rz(yaw)."""
    return Rx(roll_deg) @ Ry(pitch_deg) @ Rz(yaw_deg)

# ---------------------------
# Simple boat mesh
# ---------------------------

def make_boat_mesh(length=1.0, beam=0.18, height=0.12, deck_height_ratio=0.6):
    """Build a simple low-poly boat mesh."""
    L = float(length)
    B = float(beam)
    H = float(height)
    z0 = -H * 0.5
    z1 = +H * 0.5
    xF, xB = +0.5*L, -0.5*L

    verts = np.array([
        [xF,     0.0, z0],        # 0 bow bottom center
        [xF,  +0.02, z1*0.2],     # 1 bow top small right
        [xF,  -0.02, z1*0.2],     # 2 bow top small left
        [xB,  +B/2,  z0],         # 3 stern bottom right
        [xB,  -B/2,  z0],         # 4 stern bottom left
        [xB,  +B/2,  z1*0.4],     # 5 stern top right
        [xB,  -B/2,  z1*0.4],     # 6 stern top left
    ], float)

    faces = [
        [0,3,4],
        [1,5,3,0],
        [2,0,4,6],
        [1,2,6,5],
    ]

    groups = [
        (verts, faces, dict(facecolor="#d44", edgecolor="k", alpha=0.9)),   # hull only!
        # Deck and mast removed
    ]
    return groups

def transform_vertices(R: np.ndarray, V: np.ndarray) -> np.ndarray:
    """Apply rotation (3x3) to a (N,3) vertex array."""
    return (R @ V.T).T

# ---------------------------
# Example motion provider
# ---------------------------

def make_wave_motion():
    """Simulates roll, pitch, and yaw oscillations like a boat in waves."""
    YAW_AMP, YAW_HZ   = 25.0, 0.10
    PITCH_AMP, PITCH_HZ = 8.0, 0.05
    ROLL_AMP, ROLL_HZ = 6.0, 0.35

    def provider(t: float):
        yaw   = YAW_AMP   * math.sin(2*math.pi*YAW_HZ*t)
        pitch = PITCH_AMP * math.sin(2*math.pi*PITCH_HZ*t + 1.0)
        roll  = ROLL_AMP  * math.sin(2*math.pi*ROLL_HZ*t + 2.0)

        yaw_rate   = 2*math.pi*YAW_HZ   * YAW_AMP   * math.cos(2*math.pi*YAW_HZ*t)
        pitch_rate = 2*math.pi*PITCH_HZ * PITCH_AMP * math.cos(2*math.pi*PITCH_HZ*t + 1.0)
        roll_rate  = 2*math.pi*ROLL_HZ  * ROLL_AMP  * math.cos(2*math.pi*ROLL_HZ*t + 2.0)

        R_ws = euler_R_world_to_sensor(roll, pitch, yaw)
        a_lin_world = np.zeros(3)
        omega_world = np.array([roll_rate, pitch_rate, yaw_rate], float)
        return a_lin_world, omega_world, R_ws

    return provider

# ---------------------------
# Live visualizer
# ---------------------------

def run_visualizer(config_path: str,
                   boat_length: float = 1.2,
                   seconds: float = 30.0,
                   lpf_accel_hz: float = 100.0,
                   lpf_gyro_hz: float = 98.0,
                   motion_provider=None):
    if motion_provider is None:
        motion_provider = make_wave_motion()

    imu = MPU9250(config_path)
    imu.read_config()
    imu.init_all_sims(accel_seed=1, gyro_seed=1, mag_seed=1,
                      accel_lpf_cut_hz=lpf_accel_hz, gyro_lpf_cut_hz=lpf_gyro_hz)

    groups = make_boat_mesh(length=boat_length, beam=0.22*boat_length, height=0.12*boat_length)

    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_box_aspect((1, 0.4, 0.25))

    poly_lists = []
    for V, faces, style in groups:
        polys = [[V[i] for i in face] for face in faces]
        coll = Poly3DCollection(polys, **style)
        ax.add_collection3d(coll)
        poly_lists.append((coll, V, faces, style))

    triad_len = boat_length * 0.4
    ax.plot([0, triad_len],[0,0],[0,0], lw=3, color="tab:red", label="X fwd")
    ax.plot([0,0],[0, triad_len],[0,0], lw=3, color="tab:green", label="Y right")
    ax.plot([0,0],[0,0],[0, triad_len], lw=3, color="tab:blue", label="Z up")

    rng = boat_length * 0.8
    ax.set_xlim(-rng, rng); ax.set_ylim(-0.5*rng, 0.5*rng); ax.set_zlim(-0.3*rng, 0.6*rng)
    ax.set_title("IMU-driven Boat — orientation from motion provider")
    ax.legend(loc="upper left")

    t0 = time.time()

    def update(_frame):
        t = time.time() - t0
        if t > seconds:
            plt.close(fig)
            return []

        a_lin_world, omega_world_dps, R_ws = motion_provider(t)
        imu.sample_accel(a_lin_world, R_ws)
        imu.sample_gyro(omega_world_dps, R_ws)
        imu.sample_mag(R_ws)

        artists = []
        for coll, V0, faces, style in poly_lists:
            V = transform_vertices(R_ws, V0)
            polys = [[V[i] for i in face] for face in faces]
            coll.set_verts(polys)
            artists.append(coll)
        return artists

    anim = FuncAnimation(fig, update,
                         frames=itertools.count(),
                         interval=30,
                         blit=False,
                         cache_frame_data=False)
    plt.show()
    return anim

# ---------------------------
# Main
# ---------------------------

if __name__ == "__main__":
    CONFIG_PATH = "./simulators/imu_sim/config.ini"
    run_visualizer(CONFIG_PATH, boat_length=1.2, seconds=30.0)
