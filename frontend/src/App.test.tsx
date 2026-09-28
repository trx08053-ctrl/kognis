import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("показывает пользователей и добавляет нового", async () => {
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(reply(200, [{ id: 1, name: "Ann" }]))
    .mockResolvedValueOnce(reply(201, { id: 2, name: "Bob" }));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  expect(await screen.findByText("Ann")).toBeTruthy();

  fireEvent.change(screen.getByLabelText("Имя пользователя"), { target: { value: "Bob" } });
  fireEvent.click(screen.getByTestId("register"));
  expect(await screen.findByText("Bob")).toBeTruthy();
  expect(fetchMock).toHaveBeenLastCalledWith(
    "/api/users",
    expect.objectContaining({ method: "POST" }),
  );
});

test("показывает ошибку сервера", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(reply(200, []))
      .mockResolvedValueOnce(reply(422, { detail: "имя не может быть пустым" })),
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Имя пользователя"), { target: { value: "  " } });
  fireEvent.click(await screen.findByTestId("register"));
  expect((await screen.findByRole("alert")).textContent).toContain("пуст");
});
