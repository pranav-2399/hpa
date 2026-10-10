import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Clock3, Cpu, DollarSign, HardDrive, Layers3, Timer, X } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchMetricsHistoryRange } from '../services/api';
import { buildCostSeries } from '../utils/cost';

const MAX_POINTS = 5000;
const presets = [
  { label: '15 min', ms: 15 * 60 * 1000 },
  { label: '1 hour', ms: 60 * 60 * 1000 },
  { label: '6 hours', ms: 6 * 60 * 60 * 1000 },
  { label: '24 hours', ms: 24 * 60 * 60 * 1000 },
  { label: '7 days', ms: 7 * 24 * 60 * 60 * 1000 }
];
const metricCards = [
  { key: 'cpuUsage', title: 'CPU utilization', subtitle: 'Average of running pods · % of CPU request', color: '#a99cff', unit: '%', Icon: Cpu },
  { key: 'memoryUsage', title: 'Memory utilization', subtitle: 'Prometheus process memory · normalized', color: '#ed8bd7', unit: '%', Icon: HardDrive },
  { key: 'requestRate', title: 'Request rate', subtitle: 'Incoming HTTP requests', color: '#5ce1e6', unit: ' req/s', Icon: Activity },
  { key: 'responseTime', title: 'Response time', subtitle: 'Mean request latency', color: '#ffc875', unit: ' ms', Icon: Timer },
  { key: 'activePods', title: 'Pod count', subtitle: 'Deployment replica count', color: '#59e2b1', unit: ' pods', Icon: Layers3 },
  { key: 'instantaneousCost', title: 'Instantaneous cost rate', subtitle: 'Active pods × $0.05 per pod-hour', color: '#ffc875', unit: ' $/hr', Icon: DollarSign },
  { key: 'cumulativeCost', title: 'Cumulative estimated cost', subtitle: 'Estimated spend integrated across this window', color: '#65e5b5', unit: ' $', Icon: DollarSign }
];

function toLocalInput(date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function makeRange(milliseconds) {
  const end = new Date();
  return { start: new Date(end.getTime() - milliseconds), end };
}

function formatTick(value) {
  const date = new Date(value);
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function HistoryChart({ metric, chartData }) {
  const { key, title, subtitle, color, unit, Icon } = metric;

  return (
    <section className="glass-card history-chart-card">
      <div className="history-chart-heading">
        <span className="history-icon" style={{ '--metric-color': color }}><Icon size={18} /></span>
        <div><h2>{title}</h2><p>{subtitle}</p></div>
      </div>
      <div className="history-chart-canvas">
        {chartData.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 16, left: -12, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="rgba(255,255,255,.07)" />
              <XAxis dataKey="time" stroke="#78819d" fontSize={10} tickLine={false} axisLine={false} minTickGap={35} />
              <YAxis stroke="#78819d" fontSize={10} tickLine={false} axisLine={false} width={45} allowDecimals={key !== 'activePods'} />
              <Tooltip
                labelFormatter={(_, payload) => payload?.[0]?.payload?.timestamp ? new Date(payload[0].payload.timestamp).toLocaleString() : ''}
                formatter={(value) => [`${Number(value).toFixed(key === 'activePods' ? 0 : key === 'cumulativeCost' ? 4 : 2)}${unit}`, title]}
                contentStyle={{ background: 'rgba(14,18,33,.96)', border: '1px solid rgba(190,200,255,.16)', borderRadius: 12, color: '#f4f6ff', fontSize: 12 }}
              />
              <Line type={key === 'activePods' ? 'stepAfter' : 'monotone'} dataKey={key} name={title} stroke={color} strokeWidth={2.4} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="history-empty-chart">No samples in this time window.</div>
        )}
      </div>
    </section>
  );
}

export default function MetricHistoryPage() {
  const initialRange = useMemo(() => makeRange(60 * 60 * 1000), []);
  const [startInput, setStartInput] = useState(() => toLocalInput(initialRange.start));
  const [endInput, setEndInput] = useState(() => toLocalInput(initialRange.end));
  const [appliedRange, setAppliedRange] = useState(initialRange);
  const [selectedPreset, setSelectedPreset] = useState('1 hour');
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const samples = await fetchMetricsHistoryRange(appliedRange.start.toISOString(), appliedRange.end.toISOString(), MAX_POINTS);
      if (cancelled) return;
      if (samples === null) {
        setError('Could not load metric history. Check that the API server is running.');
      } else {
        setHistory(samples);
        setError('');
      }
      setIsLoading(false);
    };

    setIsLoading(true);
    load();
    const interval = setInterval(load, 30_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [appliedRange]);

  const selectPreset = (preset) => {
    const range = makeRange(preset.ms);
    setSelectedPreset(preset.label);
    setStartInput(toLocalInput(range.start));
    setEndInput(toLocalInput(range.end));
    setAppliedRange(range);
  };

  const applyCustomRange = (event) => {
    event.preventDefault();
    const start = new Date(startInput);
    const end = new Date(endInput);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      setError('Choose a valid start and end time. The end must be after the start.');
      return;
    }
    setSelectedPreset('Custom');
    setAppliedRange({ start, end });
  };

  const chartData = useMemo(() => buildCostSeries(history).map((sample) => ({
    ...sample,
    time: formatTick(sample.timestamp)
  })), [history]);

  const summary = useMemo(() => {
    if (!history.length) return null;
    const averageCpu = history.reduce((total, item) => total + Number(item.cpuUsage || 0), 0) / history.length;
    const peakRps = Math.max(...history.map((item) => Number(item.requestRate || 0)));
    const peakPods = Math.max(...history.map((item) => Number(item.activePods || 0)));
    const cumulativeCost = chartData.at(-1)?.cumulativeCost || 0;
    const currentCostRate = chartData.at(-1)?.instantaneousCost || 0;
    return { averageCpu, peakRps, peakPods, cumulativeCost, currentCostRate, chartData };
  }, [history, chartData]);

  return (
    <main className="metric-history-page">
      <section className="glass-card history-toolbar">
        <div className="history-page-title">
          <div className="history-title-icon"><Activity size={20} /></div>
          <div><h2>Metric history</h2><p>Explore workload and replica trends across a time window.</p></div>
        </div>

        <div className="history-presets" role="group" aria-label="Quick time windows">
          {presets.map((preset) => (
            <button key={preset.label} type="button" className={`range-chip ${selectedPreset === preset.label ? 'active' : ''}`} onClick={() => selectPreset(preset)}>
              {preset.label}
            </button>
          ))}
        </div>

        <form className="history-range-form" onSubmit={applyCustomRange}>
          <label><span>From</span><input type="datetime-local" value={startInput} onChange={(event) => { setStartInput(event.target.value); setSelectedPreset('Custom'); }} /></label>
          <label><span>To</span><input type="datetime-local" value={endInput} onChange={(event) => { setEndInput(event.target.value); setSelectedPreset('Custom'); }} /></label>
          <button className="apply-range-button" type="submit"><Clock3 size={15} /> Apply range</button>
        </form>
      </section>

      <div className="history-result-line">
        <span>{isLoading ? 'Loading samples…' : `${history.length.toLocaleString()} samples`} · {selectedPreset === 'Custom' ? 'Custom window' : selectedPreset}</span>
        <span>{appliedRange.start.toLocaleString()} — {appliedRange.end.toLocaleString()}</span>
      </div>

      {error && <div className="history-alert"><X size={15} />{error}</div>}

      {summary && (
        <div className="history-summary-grid">
          <div className="history-summary-card"><span>Average CPU</span><strong>{summary.averageCpu.toFixed(1)}%</strong></div>
          <div className="history-summary-card"><span>Peak request rate</span><strong>{summary.peakRps.toFixed(1)} <small>req/s</small></strong></div>
          <div className="history-summary-card"><span>Peak pod count</span><strong>{summary.peakPods}</strong></div>
          <div className="history-summary-card"><span>Cumulative estimated cost</span><strong>${summary.cumulativeCost.toFixed(4)}</strong></div>
          <div className="history-summary-card"><span>Latest cost rate</span><strong>${summary.currentCostRate.toFixed(2)} <small>/ hr</small></strong></div>
        </div>
      )}

      <div className="history-charts-grid">
        {metricCards.map((metric) => <HistoryChart key={metric.key} metric={metric} chartData={chartData} />)}
      </div>
      <p className="history-footnote">Cumulative estimated cost integrates the hourly pod-cost rate between stored samples in the selected window. Cost uses the demo estimate of $0.05 per pod-hour. The API keeps at most {MAX_POINTS.toLocaleString()} evenly spaced samples per request.</p>
    </main>
  );
}
