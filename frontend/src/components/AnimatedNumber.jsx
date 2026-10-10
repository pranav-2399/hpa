import React, { useEffect, useRef, useState } from 'react';

export default function AnimatedNumber({ value, decimals = 0 }) {
  const target = Number(value) || 0;
  const [display, setDisplay] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    const from = current.current;
    const distance = target - from;
    if (!distance) return undefined;

    const duration = Math.min(1100, Math.max(420, Math.abs(distance) * 14));
    let frame;
    let start;
    const step = (time) => {
      if (start === undefined) start = time;
      const progress = Math.min((time - start) / duration, 1);
      const eased = 1 - (1 - progress) ** 4;
      const next = from + distance * eased;
      current.current = next;
      setDisplay(next);
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return <>{display.toFixed(decimals)}</>;
}
