import React from 'react';
import { Activity, Server, Cpu, HardDrive, DollarSign, ArrowUpRight } from 'lucide-react';
import AnimatedNumber from './AnimatedNumber';

const metricDefinitions = [
  { key: 'cpu', label: 'CPU utilization', suffix: '%', decimals: 1, Icon: Cpu, tone: 'violet', note: 'Average of running pods · vs CPU request', bar: true },
  { key: 'memory', label: 'Memory usage', suffix: '%', decimals: 1, Icon: HardDrive, tone: 'pink', note: 'Memory pressure', bar: true },
  { key: 'rps', label: 'Request rate', suffix: ' req/s', decimals: 1, Icon: Activity, tone: 'cyan', note: 'Prometheus · 2m rate' },
  { key: 'pods', label: 'Active replicas', suffix: '', decimals: 0, Icon: Server, tone: 'green', note: 'Min 1 · Max 10' },
  { key: 'cost', label: 'Instantaneous cost rate', prefix: '$', suffix: ' / hr', decimals: 2, Icon: DollarSign, tone: 'amber', note: 'Current replicas · $0.05 per pod-hour' },
  { key: 'cumulativeCost', label: 'Cumulative estimated cost', prefix: '$', suffix: '', decimals: 4, Icon: DollarSign, tone: 'green', note: 'Across retained metric history' }
];

export default function MetricCards({ clusterData, cumulativeCost, selectedMetric, onSelectMetric }) {
  const values = {
    cpu: Number(clusterData?.cpuUsage ?? 45),
    memory: Number(clusterData?.memoryUsage ?? 55),
    rps: Number(clusterData?.requestRate ?? 120),
    pods: Number(clusterData?.activePods ?? 2),
    cumulativeCost: Number(cumulativeCost ?? 0)
  };
  values.cost = values.pods * 0.05;

  return (
    <section className="metrics-grid" aria-label="Cluster metrics">
      {metricDefinitions.map(({ key, label, prefix = '', suffix, decimals, Icon, tone, note, bar }, index) => {
        const value = values[key];
        const critical = key === 'cpu' && value >= 75;
        const isSelectable = ['cpu', 'memory', 'rps'].includes(key);
        const cardClass = `metric-card glass-card tone-${critical ? 'red' : tone} ${selectedMetric === key ? 'is-selected' : ''}`;
        const cardContents = <>
          <div className="metric-topline">
            <span className="metric-label">{label}</span>
            <span className="metric-icon"><Icon size={19} strokeWidth={1.8} /></span>
          </div>
          <div className="metric-value" aria-live="polite">
            <span>{prefix}</span><AnimatedNumber value={value} decimals={decimals} /><span className="metric-suffix">{suffix}</span>
          </div>
          {bar ? (
            <div className="metric-progress" aria-label={`${label} ${value}%`}>
              <span style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
            </div>
          ) : <div className="metric-spacer" />}
          <div className="metric-foot"><span>{isSelectable ? 'Click to view per-pod trend' : note}</span><ArrowUpRight size={14} /></div>
        </>;

        return (
          <React.Fragment key={key}>
            {isSelectable ? (
              <button type="button" className={cardClass} style={{ '--card-index': index }} onClick={() => onSelectMetric(selectedMetric === key ? null : key)} aria-pressed={selectedMetric === key} aria-label={`Show per-pod ${label} chart`}>
                {cardContents}
              </button>
            ) : (
              <article className={cardClass} style={{ '--card-index': index }}>{cardContents}</article>
            )}
          </React.Fragment>
        );
      })}
    </section>
  );
}
