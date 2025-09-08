import { useEffect, useState } from 'react';

const STORAGE_KEY = 'simManagerState';

export const defaultState = {
  routeName: '',
  gpsLat: '0.0000000000000',
  gpsLon: '0.0000000000000',
  gpsHdg: '0',
  gpsSpd: '0',
  gpsActive: false,
  gpsMode: null, // 'ROUTE' | 'VECTOR' | null
  routeNextLat: -1,
  routeNextLon: -1,
  wave: 'calm',
  imuActive: false,
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') return parsed;
  } catch (_) {
    // ignore
  }
  return null;
}

const _loaded = loadState() || {};
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
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_) {
    // ignore quota or serialization errors
  }
  emit();
}

export function resetSimState() {
  state = { ...defaultState };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (_) {
    // ignore
  }
  emit();
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Cross-tab sync via storage events
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY) {
      try {
        const next = e.newValue ? JSON.parse(e.newValue) : defaultState;
        state = { ...defaultState, ...(next || {}) };
        emit();
      } catch (_) {
        // ignore
      }
    }
  });
}

export function useSimStore(selector = (s) => s) {
  const [snapshot, setSnapshot] = useState(() => selector(state));
  useEffect(() => {
    const listener = () => setSnapshot(selector(state));
    return subscribe(listener);
  }, [selector]);
  return snapshot;
}
