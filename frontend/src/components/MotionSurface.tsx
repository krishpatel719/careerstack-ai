import {
  motion,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion";
import { useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function BeamBackdrop() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const y = useSpring(scrollYProgress, { stiffness: 70, damping: 20 });
  const rotate = useTransform(y, [0, 1], [-8, 8]);
  const reduceMotion = useReducedMotion();
  if (reduceMotion) return null;
  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div className="absolute inset-0 premium-grid opacity-70" />
      <motion.div
        style={{ rotate }}
        className="absolute -left-24 top-[-15rem] h-[38rem] w-[38rem] rounded-full bg-accent/10 blur-3xl"
      />
      <motion.div
        style={{ rotate: useTransform(y, [0, 1], [6, -6]) }}
        className="absolute right-[-12rem] top-24 h-[32rem] w-[32rem] rounded-full bg-primary/10 blur-3xl"
      />
      <div className="absolute left-[16%] top-0 h-full w-px bg-gradient-to-b from-transparent via-accent/30 to-transparent" />
    </div>
  );
}

export function SpotlightCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  function handleMove(event: React.MouseEvent<HTMLDivElement>) {
    if (reduceMotion || !ref.current) return;
    const bounds = ref.current.getBoundingClientRect();
    ref.current.style.setProperty("--x", `${event.clientX - bounds.left}px`);
    ref.current.style.setProperty("--y", `${event.clientY - bounds.top}px`);
  }
  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-primary/10 bg-card/80 shadow-[0_20px_60px_-36px_hsl(164_24%_13%/0.45)] backdrop-blur transition duration-300 hover:-translate-y-1 hover:border-accent/40 hover:shadow-[0_28px_70px_-34px_hsl(164_32%_20%/0.5)]",
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background:
            "radial-gradient(360px circle at var(--x, 50%) var(--y, 50%), hsl(33 48% 49% / .11), transparent 68%)",
        }}
      />
      <div className="relative">{children}</div>
    </div>
  );
}

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
