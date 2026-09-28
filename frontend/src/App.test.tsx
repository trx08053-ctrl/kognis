import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("аноним видит форму входа и после входа — дневник с записями", async () => {
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(reply(401, { detail: "нужен вход" }))
    .mockResolvedValueOnce(reply(200, { id: 1, email: "ann@example.com" }))
    .mockResolvedValueOnce(
      reply(200, [
        {
          id: 7,
          date: "2026-09-01",
          text: "Тревожный день",
          tags: ["работа"],
          emotions: [],
          protection: "plain",
          crisis: false,
          help: null,
        },
      ]),
    );
  vi.stubGlobal("fetch", fetchMock);
  renderApp();

  fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "ann@example.com" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "correct horse" } });
  fireEvent.click(screen.getByTestId("auth-submit"));

  expect(await screen.findByText("Тревожный день")).toBeTruthy();
  expect(screen.getByTestId("whoami").textContent).toBe("ann@example.com");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({ method: "POST" }),
  );
});

test("показывает ошибку входа", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(reply(401, { detail: "нужен вход" }))
      .mockResolvedValueOnce(reply(401, { detail: "неверный email или пароль" })),
  );
  renderApp();
  fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "ann@example.com" } });
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "wrong wrong" } });
  fireEvent.click(screen.getByTestId("auth-submit"));
  expect((await screen.findByRole("alert")).textContent).toContain("неверный");
});

test("запись с кризисным сигналом показывает блок помощи с контактами", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(reply(200, { id: 1, email: "ann@example.com" }))
      .mockResolvedValueOnce(reply(200, []))
      .mockResolvedValueOnce(
        reply(201, {
          id: 2,
          date: "2026-09-29",
          text: "хочу умереть",
          tags: [],
          emotions: [],
          protection: "plain",
          crisis: true,
          help: {
            message: "Вы не одни",
            contacts: [{ name: "Экстренные службы", phone: "112", note: "круглосуточно" }],
          },
        }),
      )
      .mockResolvedValue(reply(200, [])),
  );
  renderApp();
  fireEvent.change(await screen.findByLabelText("Что произошло и что вы чувствуете"), {
    target: { value: "хочу умереть" },
  });
  fireEvent.click(screen.getByTestId("save-entry"));
  const block = await screen.findByTestId("help-block");
  expect(block.getAttribute("role")).toBe("alert");
  expect(block.textContent).toContain("Вы не одни");
  expect(screen.getByRole("link", { name: "112" }).getAttribute("href")).toBe("tel:112");
  expect(screen.getByTestId("disclaimer").textContent).toContain("не медицинская помощь");
});
