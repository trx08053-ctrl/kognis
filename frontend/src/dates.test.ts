import { expect, test } from "vitest";
import { shiftDay, timeZoneNames } from "./dates";

test("shiftDay сдвигает календарную дату через границы месяца и года", () => {
  expect(shiftDay("2026-09-02", -6)).toBe("2026-08-27");
  expect(shiftDay("2026-01-03", -5)).toBe("2025-12-29");
  expect(shiftDay("2026-02-27", 2)).toBe("2026-03-01");
});

test("timeZoneNames всегда содержит текущий пояс пользователя", () => {
  expect(timeZoneNames("Asia/Vladivostok")).toContain("Asia/Vladivostok");
  expect(timeZoneNames("Custom/Zone")).toContain("Custom/Zone");
});
