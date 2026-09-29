// Появление блоков при прокрутке и счётчики. Без IntersectionObserver или при
// prefers-reduced-motion всё показывается сразу, без анимации.
import { type ReactNode, useEffect, useRef, useState } from "react";

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export function useInView<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(
    () => typeof IntersectionObserver === "undefined" || reducedMotion(),
  );
  useEffect(() => {
    const node = ref.current;
    if (visible || !node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible]);
  return [ref, visible];
}

export function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: 0 | 1 | 2 | 3;
}) {
  const [ref, visible] = useInView<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={`reveal reveal-d${delay} ${visible ? "is-visible" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

export function CountUp({ value, suffix }: { value: number; suffix: string }) {
  const [ref, visible] = useInView<HTMLSpanElement>();
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!visible) return;
    if (reducedMotion()) {
      setShown(value);
      return;
    }
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 1200);
      setShown(Math.round(value * (1 - (1 - t) ** 3)));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [visible, value]);
  return (
    <span ref={ref}>
      <span className="sr-only">
        {value}
        {suffix}
      </span>
      <span aria-hidden="true">
        {shown}
        {suffix}
      </span>
    </span>
  );
}
