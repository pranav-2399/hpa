import React from 'react';
import { Cpu, RefreshCw, Zap, ShieldCheck } from 'lucide-react';

export default function Header({ onTriggerLoop, isTriggering, lastUpdated }) {
  return (
    <header className="glass-card" style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', width: '48px', height: '48px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px rgba(99, 102, 241, 0.5)' }}>
          <Cpu color="#ffffff" size={26} />
        </div>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #ffffff, #cbd5e1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            KubeMind AI — Horizontal Pod Autoscaler
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
            <span>Deployment Target: <strong style={{ color: '#e2e8f0' }}>hpa-load-target</strong></span>
            <span>•</span>
            <span className="badge badge-live">Live Monitoring</span>
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {lastUpdated && (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Updated: {lastUpdated.toLocaleTimeString()}
          </span>
        )}
        
        <button
          onClick={onTriggerLoop}
          disabled={isTriggering}
          style={{
            background: isTriggering ? 'var(--bg-card-hover)' : 'linear-gradient(135deg, #6366f1, #4f46e5)',
            color: '#ffffff',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            borderRadius: '10px',
            padding: '0.65rem 1.2rem',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: isTriggering ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            boxShadow: '0 4px 14px 0 rgba(99, 102, 241, 0.39)',
            transition: 'all 0.2s ease'
          }}
        >
          <RefreshCw className={isTriggering ? 'spin' : ''} size={16} />
          {isTriggering ? 'Evaluating Agent...' : 'Trigger AI Loop'}
        </button>
      </div>
    </header>
  );
}
