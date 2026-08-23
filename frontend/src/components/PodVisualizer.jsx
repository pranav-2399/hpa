import React from 'react';
import { Layers, CheckCircle2 } from 'lucide-react';

export default function PodVisualizer({ pods }) {
  const activePods = pods && pods.length > 0 ? pods : [
    { podName: 'hpa-load-target-7d68b9f-1', status: 'Running', cpuUsage: 45.0, memoryUsage: 55.0 },
    { podName: 'hpa-load-target-7d68b9f-2', status: 'Running', cpuUsage: 48.0, memoryUsage: 52.0 }
  ];

  return (
    <div className="glass-card" style={{ height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <Layers color="#10b981" size={22} />
        <div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Active Pod Replicas Visualizer</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Live Kubernetes pod container state</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.85rem' }}>
        {activePods.map((pod, idx) => (
          <div
            key={idx}
            style={{
              background: 'rgba(30, 41, 59, 0.4)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '10px',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.4rem'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <CheckCircle2 size={12} /> {pod.status}
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>#0{idx + 1}</span>
            </div>

            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc', wordBreak: 'break-all' }}>
              {pod.podName}
            </div>

            <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <div>CPU: <strong style={{ color: '#e2e8f0' }}>{pod.cpuUsage}%</strong></div>
              <div>Mem: <strong style={{ color: '#e2e8f0' }}>{pod.memoryUsage}%</strong></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
