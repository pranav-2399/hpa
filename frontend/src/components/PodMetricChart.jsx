import React from 'react';
import { Activity, Cpu, HardDrive, X } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';

const metricDetails = {
  cpu: { label: 'CPU utilization', key: 'cpuUsage', unit: '%', description: 'CPU used as a percentage of each pod’s CPU request', Icon: Cpu, color: '#a99cff' },
  memory: { label: 'Memory usage', key: 'memoryUsage', unit: ' MiB', Icon: HardDrive, color: '#ef9bdd' },
  rps: { label: 'Request rate', key: 'requestRate', unit: ' req/s', Icon: Activity, color: '#68e4e8' }
};

const colors = ['#9f91ff', '#5ce1e6', '#65e5b5', '#ff9fcb', '#ffc875', '#84b9ff', '#f18e82', '#c6a2ff'];

export default function PodMetricChart({ metric, pods, history, onClose }) {
  const detail = metricDetails[metric];
  const currentPods = (pods || []).filter((pod) => pod.status === 'Running' || !pod.status);
  const chartData = history.map((sample) => ({
    time: new Date(sample.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    ...Object.fromEntries(Object.entries(sample.pods).map(([name, values]) => [name, values[detail.key]]))
  }));
  const hasPerPodRates = metric !== 'rps' || currentPods.some((pod) => pod.requestRate != null);
  const Icon = detail.Icon;

  return (
    <section className="glass-card pod-metric-panel" aria-label={`Per-pod ${detail.label} graph`}>
      <div className="pod-metric-heading">
        <div className="pod-metric-title">
          <span className="metric-icon" style={{ '--tone': detail.color }}><Icon size={19} /></span>
          <div>
            <h2>Per-pod {detail.label}</h2>
            <p>{detail.description || 'Each line tracks one pod'} · samples collected every 5 seconds</p>
          </div>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close per-pod graph"><X size={18} /></button>
      </div>

      {!hasPerPodRates ? (
        <div className="pod-metric-empty">
          <strong>Per-pod request rate is not available yet</strong>
          <span>Prometheus must expose a <code>pod</code> label for the request metric. The current Service scrape does not identify which pod served each scrape.</span>
        </div>
      ) : currentPods.length === 0 ? (
        <div className="pod-metric-empty"><strong>No running pods found</strong><span>Per-pod metrics will appear when the workload pods are running.</span></div>
      ) : chartData.length < 2 ? (
        <div className="pod-metric-empty"><strong>Gathering pod samples</strong><span>The trend will appear after the next dashboard refresh.</span></div>
      ) : (
        <div className="pod-chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 18, left: -10, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 5" stroke="rgba(255,255,255,0.07)" />
              <XAxis dataKey="time" stroke="#77809c" fontSize={11} tickLine={false} axisLine={false} minTickGap={32} />
              <YAxis stroke="#77809c" fontSize={11} tickLine={false} axisLine={false} width={48} />
              <Tooltip
                formatter={(value, name) => [`${Number(value).toFixed(metric === 'memory' ? 1 : 2)}${detail.unit}`, name]}
                contentStyle={{ background: 'rgba(14, 18, 33, .96)', border: '1px solid rgba(190,200,255,.16)', borderRadius: 12, color: '#f4f6ff', fontSize: 12 }}
                labelStyle={{ color: '#aeb6d0', marginBottom: 5 }}
              />
              <Legend wrapperStyle={{ paddingTop: 10, fontSize: 11, color: '#aab2cc' }} />
              {currentPods.map((pod, index) => (
                <Line key={pod.podName} type="monotone" dataKey={pod.podName} name={pod.podName} stroke={colors[index % colors.length]} strokeWidth={2.4} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
