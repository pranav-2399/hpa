import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MetricCards from './components/MetricCards';
import MetricsChart from './components/MetricsChart';
import AgentReasoningFeed from './components/AgentReasoningFeed';
import PodVisualizer from './components/PodVisualizer';
import ScalingTimeline from './components/ScalingTimeline';
import {
  fetchClusterStatus,
  fetchMetricsHistory,
  fetchAgentDecisions,
  fetchScalingActions,
  triggerControlLoop
} from './services/api';

export default function App() {
  const [clusterData, setClusterData] = useState(null);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [actions, setActions] = useState([]);
  const [isTriggering, setIsTriggering] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const loadData = async () => {
    const status = await fetchClusterStatus();
    if (status) setClusterData(status);

    const history = await fetchMetricsHistory(30);
    if (history) setMetricsHistory(history);

    const decs = await fetchAgentDecisions(20);
    if (decs) setDecisions(decs);

    const acts = await fetchScalingActions();
    if (acts) setActions(acts);

    setLastUpdated(new Date());
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTriggerLoop = async () => {
    setIsTriggering(true);
    await triggerControlLoop();
    await loadData();
    setIsTriggering(false);
  };

  return (
    <div className="dashboard-container">
      <Header
        onTriggerLoop={handleTriggerLoop}
        isTriggering={isTriggering}
        lastUpdated={lastUpdated}
      />

      <MetricCards clusterData={clusterData} />

      <MetricsChart history={metricsHistory} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '1.5rem' }}>
        <AgentReasoningFeed decisions={decisions} />
        <PodVisualizer pods={clusterData?.pods} />
      </div>

      <ScalingTimeline actions={actions} />
    </div>
  );
}
