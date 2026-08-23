import React from 'react';
import { Bot, CheckCircle2, AlertTriangle, Shield, ChevronRight } from 'lucide-react';

export default function AgentReasoningFeed({ decisions }) {
  const getBadgeClass = (decisionText) => {
    if (decisionText?.includes('SCALE_UP')) return 'badge-scale-up';
    if (decisionText?.includes('SCALE_DOWN')) return 'badge-scale-down';
    return 'badge-maintain';
  };

  return (
    <div className="glass-card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <Bot color="#8b5cf6" size={22} />
        <div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>AI Decision Reasoning Stream</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Llama-3.3 Agentic Chain-of-Thought & Audits</p>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.85rem', paddingRight: '0.2rem', maxHeight: '420px' }}>
        {decisions.length > 0 ? (
          decisions.map((item) => (
            <div
              key={item.decisionId}
              style={{
                background: 'rgba(30, 41, 59, 0.4)',
                border: '1px solid var(--border-color)',
                borderRadius: '12px',
                padding: '1rem',
                transition: 'transform 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                <span className={`badge ${getBadgeClass(item.decision)}`}>
                  {item.decision}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                  {new Date(item.decisionTime).toLocaleTimeString()}
                </span>
              </div>

              <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.45', marginBottom: '0.75rem' }}>
                {item.reasoning}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', background: 'rgba(15, 23, 42, 0.6)', padding: '0.4rem 0.6rem', borderRadius: '6px' }}>
                <span>Confidence: <strong style={{ color: '#38bdf8' }}>{Math.round((item.confidence || 0.85) * 100)}%</strong></span>
                <span>CPU Input: {item.inputSummary?.cpuUsage}%</span>
                <span>Pods: {item.inputSummary?.activePods}</span>
              </div>
            </div>
          ))
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '2rem' }}>
            No decision logs generated yet. Click "Trigger AI Loop" to evaluate.
          </div>
        )}
      </div>
    </div>
  );
}
