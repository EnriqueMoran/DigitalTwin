import { useEffect, useState } from 'react';

export const defaultState = {
  routeName: '',
  gpsLat: '0.0000000000000',
  gpsLon: '0.0000000000000',
  gpsHdg: '0',
  gpsSpd: '5',
  gpsActive: false,
  gpsMode: null, // 'ROUTE' | 'VECTOR' | null
  routeNextLat: -1,
  routeNextLon: -1,
  wave: 'calm',
  imuActive: false,
};

const _loaded = {};
if (_loaded && _loaded.wave === 'none') {
  _loaded.wave = 'calm';
}
let state = { ...defaultState, ..._loaded };
const listeners = new Set();

function emit() {
  for (const l of Array.from(listeners)) {
    try { l(); } catch (_) { /* noop */ }
  }
}

export function getSimState() {
  return state;
}

export function setSimState(patch) {
  state = { ...state, ...patch };
  emit();
}

export function resetSimState() {
  state = { ...defaultState };
  emit();
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// No cross-tab localStorage sync; state is kept in-memory per tab.

export function useSimStore(selector = (s) => s) {
  const [snapshot, setSnapshot] = useState(() => selector(state));
  useEffect(() => {
    const listener = () => setSnapshot(selector(state));
    return subscribe(listener);
  }, [selector]);
  return snapshot;
}
