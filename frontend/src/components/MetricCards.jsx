import React from 'react';
import { Activity, Server, Cpu, HardDrive, DollarSign } from 'lucide-react';

export default function MetricCards({ clusterData }) {
  const cpu = clusterData?.cpuUsage ?? 45.0;
  const memory = clusterData?.memoryUsage ?? 55.0;
  const rps = clusterData?.requestRate ?? 120.0;
  const pods = clusterData?.activePods ?? 2;
  const cost = (pods * 0.05).toFixed(2);

  const cardStyle = {
    flex: '1 1 200px',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    position: 'relative',
    overflow: 'hidden'
  };

  return (
    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
      {/* CPU Card */}
      <div className="glass-card" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>CPU Utilization</span>
          <Cpu color="#6366f1" size={20} />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, color: cpu >= 75 ? '#ef4444' : '#f8fafc' }}>
          {cpu}%
        </div>
        <div style={{ background: 'rgba(255,255,255,0.06)', height: '4px', borderRadius: '2px', overflow: 'hidden' }}>
          <div style={{ width: `${Math.min(100, cpu)}%`, background: cpu >= 75 ? '#ef4444' : 'linear-gradient(90deg, #6366f1, #8b5cf6)', height: '100%' }} />
        </div>
      </div>

      {/* Memory Card */}
      <div className="glass-card" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Memory Usage</span>
          <HardDrive color="#8b5cf6" size={20} />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700 }}>{memory}%</div>
        <div style={{ background: 'rgba(255,255,255,0.06)', height: '4px', borderRadius: '2px', overflow: 'hidden' }}>
          <div style={{ width: `${Math.min(100, memory)}%`, background: 'linear-gradient(90deg, #8b5cf6, #ec4899)', height: '100%' }} />
        </div>
      </div>

      {/* RPS Card */}
      <div className="glass-card" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Request Rate (RPS)</span>
          <Activity color="#06b6d4" size={20} />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#38bdf8' }}>{rps} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>req/s</span></div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Prometheus 2m rate</span>
      </div>

      {/* Active Pods Card */}
      <div className="glass-card" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Active Pod Replicas</span>
          <Server color="#10b981" size={20} />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#34d399' }}>{pods} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>pods</span></div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Min: 1 | Max: 10</span>
      </div>

      {/* Estimated Cost Card */}
      <div className="glass-card" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>Estimated Cost</span>
          <DollarSign color="#f59e0b" size={20} />
        </div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#fbbf24' }}>${cost} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>/hr</span></div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>$0.05 per pod / hr</span>
      </div>
    </div>
  );
}
