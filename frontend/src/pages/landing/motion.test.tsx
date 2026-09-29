import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { CountUp, Reveal } from "./motion";

type Callback = (entries: { isIntersecting: boolean }[]) => void;

function stubObserver() {
  const callbacks: Callback[] = [];
  const disconnect = vi.fn();
  class FakeObserver {
    constructor(cb: Callback) {
      callbacks.push(cb);
    }
    observe() {}
    disconnect = disconnect;
  }
  vi.stubGlobal("IntersectionObserver", FakeObserver);
  return { callbacks, disconnect };
}

function stubReducedMotion(reduced: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduced && query.includes("reduce"),
    addEventListener() {},
    removeEventListener() {},
  }));
}

function intersect(callbacks: Callback[], isIntersecting: boolean) {
  act(() => {
    for (const cb of callbacks) cb([{ isIntersecting }]);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("блок появляется, когда попадает в экран", () => {
  stubReducedMotion(false);
  const { callbacks, disconnect } = stubObserver();
  render(
    <Reveal delay={2}>
      <p>текст</p>
    </Reveal>,
  );
  const box = screen.getByText("текст").parentElement;
  expect(box?.className).toContain("reveal-d2");
  expect(box?.className).not.toContain("is-visible");
  intersect(callbacks, false);
  expect(box?.className).not.toContain("is-visible");
  intersect(callbacks, true);
  expect(box?.className).toContain("is-visible");
  expect(disconnect).toHaveBeenCalled();
});

test("счётчик досчитывает до значения анимацией", () => {
  stubReducedMotion(false);
  const { callbacks } = stubObserver();
  let now = 0;
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(performance, "now").mockImplementation(() => now);
  const { container } = render(<CountUp value={256} suffix=" бит" />);
  const shown = () => container.querySelector("[aria-hidden]")?.textContent;
  expect(shown()).toBe("0 бит");
  intersect(callbacks, true);
  now = 600;
  act(() => frames.shift()?.(now));
  expect(Number.parseInt(shown() ?? "", 10)).toBeGreaterThan(0);
  now = 1300;
  act(() => frames.shift()?.(now));
  expect(shown()).toBe("256 бит");
  expect(screen.getByText("256 бит", { selector: ".sr-only" })).toBeTruthy();
});

test("при prefers-reduced-motion счётчик сразу показывает значение", () => {
  stubReducedMotion(true);
  const { container } = render(<CountUp value={5} suffix="" />);
  expect(container.querySelector("[aria-hidden]")?.textContent).toBe("5");
});
