import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MetricCards from './components/MetricCards';
import MetricsChart from './components/MetricsChart';
import AgentReasoningFeed from './components/AgentReasoningFeed';
import PodVisualizer from './components/PodVisualizer';
import ScalingTimeline from './components/ScalingTimeline';
import Reveal from './components/Reveal';
import PodMetricChart from './components/PodMetricChart';
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
  const [podMetricHistory, setPodMetricHistory] = useState([]);
  const [selectedPodMetric, setSelectedPodMetric] = useState(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const loadData = async () => {
    const status = await fetchClusterStatus();
    if (status) {
      setClusterData(status);
      if (Array.isArray(status.pods)) {
        setPodMetricHistory((previous) => [
          ...previous,
          {
            timestamp: Date.now(),
            pods: Object.fromEntries(status.pods.map((pod) => [pod.podName, {
              cpuUsage: Number(pod.cpuUsage ?? 0),
              memoryUsage: Number(pod.memoryUsage ?? 0),
              requestRate: pod.requestRate == null ? null : Number(pod.requestRate)
            }]))
          }
        ].slice(-60));
      }
    }

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

      <Reveal><MetricCards clusterData={clusterData} selectedMetric={selectedPodMetric} onSelectMetric={setSelectedPodMetric} /></Reveal>

      {selectedPodMetric && (
        <Reveal key={selectedPodMetric} delay={40}>
          <PodMetricChart
            metric={selectedPodMetric}
            pods={clusterData?.pods || []}
            history={podMetricHistory}
            onClose={() => setSelectedPodMetric(null)}
          />
        </Reveal>
      )}

      <Reveal delay={80}><MetricsChart history={metricsHistory} /></Reveal>

      <div className="dashboard-grid">
        <Reveal delay={40}><AgentReasoningFeed decisions={decisions} /></Reveal>
        <Reveal delay={120}><PodVisualizer pods={clusterData?.pods} /></Reveal>
      </div>

      <Reveal delay={80}><ScalingTimeline actions={actions} /></Reveal>
    </div>
  );
}
