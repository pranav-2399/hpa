export const COST_PER_POD_HOUR = 0.05;

export function buildCostSeries(samples) {
  let cumulativeCost = 0;
  let previousSample;

  return samples.map((sample) => {
    const activePods = Number(sample.activePods || 0);
    const instantaneousCost = activePods * COST_PER_POD_HOUR;
    if (previousSample) {
      const elapsedHours = Math.max(0, (new Date(sample.timestamp) - new Date(previousSample.timestamp)) / 3_600_000);
      const previousRate = Number(previousSample.activePods || 0) * COST_PER_POD_HOUR;
      cumulativeCost += ((previousRate + instantaneousCost) / 2) * elapsedHours;
    }
    previousSample = sample;
    return { ...sample, instantaneousCost, cumulativeCost };
  });
}

export function estimateCumulativeCost(samples) {
  const series = buildCostSeries(samples);
  return series.length ? series[series.length - 1].cumulativeCost : 0;
}
