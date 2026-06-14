import { useEffect, useRef, useState } from 'react';
import { motion, useInView, useSpring, useMotionValue } from 'framer-motion';
import { Github, Database, Layers } from 'lucide-react';

interface StatsBarProps {
  githubCount: number;
  hfCount: number;
  totalCount: number;
}

function AnimatedNumber({ value, inView }: { value: number; inView: boolean }) {
  const motionVal = useMotionValue(0);
  const springVal = useSpring(motionVal, { damping: 30, stiffness: 100 });
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (inView) {
      motionVal.set(value);
    }
  }, [inView, value, motionVal]);

  useEffect(() => {
    const unsubscribe = springVal.on('change', (v) => {
      setDisplay(Math.round(v));
    });
    return unsubscribe;
  }, [springVal]);

  return <span>{display.toLocaleString()}</span>;
}

function StatCard({
  icon,
  label,
  value,
  delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  delay: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay }}
      className="relative overflow-hidden rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#111118] p-6 text-center"
    >
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-[#00d084]/50" />
      <div className="mb-3 flex justify-center text-[#00d084]">{icon}</div>
      <div className="text-3xl font-semibold text-[#e8e8ec] sm:text-4xl" style={{ fontFamily: "'Geist', sans-serif" }}>
        <AnimatedNumber value={value} inView={inView} />
      </div>
      <div
        className="mt-1 text-[11px] uppercase tracking-[0.08em] text-[#6b6b78]"
        style={{ fontFamily: "'Geist Mono', monospace" }}
      >
        {label}
      </div>
    </motion.div>
  );
}

export function StatsBar({ githubCount, hfCount, totalCount }: StatsBarProps) {
  return (
    <section className="px-6 pb-8">
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard icon={<Github className="h-5 w-5" />} label="GitHub Repos" value={githubCount} delay={0} />
        <StatCard icon={<Database className="h-5 w-5" />} label="Hugging Face Models" value={hfCount} delay={0.1} />
        <StatCard icon={<Layers className="h-5 w-5" />} label="Total Models" value={totalCount} delay={0.2} />
      </div>
    </section>
  );
}
