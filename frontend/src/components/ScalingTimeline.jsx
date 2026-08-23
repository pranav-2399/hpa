import React from 'react';
import { History, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

export default function ScalingTimeline({ actions }) {
  return (
    <div className="glass-card" style={{ marginTop: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <History color="#06b6d4" size={22} />
        <div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Kubernetes Scaling Action History</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Audit log of executed deployment patch events</p>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '220px', overflowY: 'auto' }}>
        {actions.length > 0 ? (
          actions.map((act) => (
            <div
              key={act.actionId}
              style={{
                display: 'flex',
                justify: 'space-between',
                alignItems: 'center',
                background: 'rgba(30, 41, 59, 0.3)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '0.65rem 1rem',
                fontSize: '0.85rem'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                {act.actionType === 'SCALE_UP' ? (
                  <ArrowUpRight color="#10b981" size={18} />
                ) : act.actionType === 'SCALE_DOWN' ? (
                  <ArrowDownRight color="#ef4444" size={18} />
                ) : (
                  <Minus color="#6366f1" size={18} />
                )}
                <div>
                  <strong style={{ color: '#f8fafc' }}>{act.actionType}</strong>: {act.previousReplicaCount} → {act.newReplicaCount} pods
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{act.reason}</div>
                </div>
              </div>

              <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', marginBottom: '0.2rem' }}>
                  {act.status}
                </span>
                <div>{new Date(act.executedAt).toLocaleTimeString()} ({act.executionDuration}s)</div>
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '1rem' }}>
            No scaling actions executed yet. Cluster is operating at steady state.
          </div>
        )}
      </div>
    </div>
  );
}
