const BASE_URL = 'http://localhost:5001/api';

export async function fetchClusterStatus() {
  try {
    const res = await fetch(`${BASE_URL}/cluster/status`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    return json.data;
  } catch (err) {
    console.warn('API error fetching cluster status:', err);
    return null;
  }
}

export async function fetchMetricsHistory(limit = 30) {
  try {
    const res = await fetch(`${BASE_URL}/metrics/history?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    return json.data || [];
  } catch (err) {
    console.warn('API error fetching metrics history:', err);
    return [];
  }
}

export async function fetchAgentDecisions(limit = 20) {
  try {
    const res = await fetch(`${BASE_URL}/agent/decisions?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    return json.data || [];
  } catch (err) {
    console.warn('API error fetching decisions:', err);
    return [];
  }
}

export async function fetchScalingActions() {
  try {
    const res = await fetch(`${BASE_URL}/actions/history`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    return json.data || [];
  } catch (err) {
    console.warn('API error fetching actions:', err);
    return [];
  }
}

export async function triggerControlLoop() {
  try {
    const res = await fetch(`${BASE_URL}/agent/trigger`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    return json;
  } catch (err) {
    console.error('Trigger control loop error:', err);
    return { status: 'error', message: err.message };
  }
}
