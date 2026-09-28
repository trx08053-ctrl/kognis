#!/usr/bin/env python3
"""UI-замечания кликом по элементу: прокси перед приложением + оверлей для комментариев.

    ui_feedback.py <task-id> [--target http://localhost:5173] [--port 7777] [--host 0.0.0.0]

Откройте приложение через прокси (http://<хост>:7777). Alt + клик по элементу
(или кнопка «💬» внизу справа) → комментарий. Замечание пишется в tasks/<task-id>/ui-feedback.md:
страница, CSS-селектор, текст, размер и позиция, ключевые стили, фрагмент HTML, комментарий.
Агент исправляет, меняет статус `open` → `done` и дописывает «Сделано: …»;
метки на странице: оранжевая — открыто, зелёная — сделано.
Только для разработки: прокси слушает сеть и пишет только в tasks/<task-id>/. Файл защищён.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import re
import socket
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 64 * 1024
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "content-length", "content-encoding", "host", "accept-encoding",
}  # fmt: skip
ENTRY = re.compile(r"^## UI-(\d+) · (\w+) · (\S+)\n(.*?)(?=^## UI-|\Z)", re.M | re.S)
STYLE_KEYS = (
    "font-size", "font-weight", "color", "background-color", "width", "height",
    "padding", "margin", "border-radius", "display", "gap",
)  # fmt: skip

OVERLAY = Path(__file__).resolve().parent / "ui_overlay.js"


def feedback_file(task_id: str) -> Path:
    return ROOT / "tasks" / task_id / "ui-feedback.md"


def entries(task_id: str) -> list[dict[str, str]]:
    path = feedback_file(task_id)
    text = path.read_text() if path.exists() else ""
    result: list[dict[str, str]] = []
    for n, status, page, body in ENTRY.findall(text):
        sel = re.search(r"^- \*\*Элемент:\*\* `([^`]+)`", body, re.M)
        comment = re.search(r"^- \*\*Комментарий:\*\* (.+)$", body, re.M)
        result.append({
            "n": n, "status": status, "path": page,
            "selector": sel.group(1) if sel else "", "comment": comment.group(1) if comment else "",
        })  # fmt: skip
    return result


def one_line(value: object, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()[:limit].replace("`", "'")


def append(task_id: str, data: dict[str, Any]) -> int:
    path = feedback_file(task_id)
    if not path.exists():
        path.write_text(
            f"# UI-замечания задачи {task_id}\n\n"
            "Статусы: `open` → `done`. Агент исправляет, проверяет на странице,\n"
            "меняет статус в заголовке и дописывает «- **Сделано:** …».\n"
            "Файл пишет `just ui-feedback`.\n\n"
        )
    n = len(entries(task_id)) + 1
    rect = [int(x) for x in cast("list[Any]", data.get("rect", [0, 0, 0, 0]))[:4]]
    vp = [int(x) for x in cast("list[Any]", data.get("viewport", [0, 0]))[:2]]
    styles = cast("dict[str, Any]", data.get("styles") or {})
    style_text = "; ".join(
        f"{k}: {one_line(styles.get(k, ''), 40)}" for k in STYLE_KEYS if k in styles
    )
    page = one_line(data.get("path", "/"), 200).replace(" ", "%20") or "/"
    block = (
        f"## UI-{n} · open · {page}\n"
        f"- **Элемент:** `{one_line(data.get('selector'), 300)}`"
        f" — «{one_line(data.get('text'), 80)}»\n"
        f"- **Размер и позиция:** {rect[0]}×{rect[1]} в ({rect[2]}, {rect[3]});"
        f" окно {vp[0]}×{vp[1]}\n"
        f"- **Стили:** {style_text}\n"
        f"- **HTML:** `{one_line(data.get('html'), 300)}`\n"
        f"- **Комментарий:** {one_line(data.get('comment'), 1000)}\n"
        f"- **Время:** {datetime.now(UTC).isoformat(timespec='seconds')}\n\n"
    )
    with path.open("a") as fh:
        fh.write(block)
    return n


class Handler(BaseHTTPRequestHandler):
    task_id = ""
    target = urlsplit("http://localhost:5173")

    def log_message(self, format: str, *args: object) -> None:
        """Тихий режим: запросы не печатаются."""

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/__ui/overlay.js":
            js = OVERLAY.read_text().replace("%STYLES%", json.dumps(STYLE_KEYS))
            return self.send(200, js.encode(), "application/javascript; charset=utf-8")
        if self.path.startswith("/__ui/feedback"):
            body = json.dumps(entries(self.task_id), ensure_ascii=False).encode()
            return self.send(200, body, "application/json; charset=utf-8")
        return self.proxy()

    def do_POST(self) -> None:
        if self.path.startswith("/__ui/feedback"):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.send(413, b"too large", "text/plain")
            try:
                data = json.loads(self.rfile.read(length))
                if (
                    not isinstance(data, dict)
                    or not str(cast("dict[str, Any]", data).get("comment", "")).strip()
                ):
                    raise ValueError("comment required")
                n = append(self.task_id, cast("dict[str, Any]", data))
            except (ValueError, TypeError) as err:
                return self.send(400, str(err).encode(), "text/plain; charset=utf-8")
            print(f"UI-{n} записано в {feedback_file(self.task_id).relative_to(ROOT)}", flush=True)
            return self.send(201, json.dumps({"n": n}).encode(), "application/json")
        return self.proxy()

    def do_PUT(self) -> None:
        self.proxy()

    def do_DELETE(self) -> None:
        self.proxy()

    def proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        conn_cls = (
            http.client.HTTPSConnection
            if self.target.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_cls(self.target.netloc, timeout=60)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError as err:
            return self.send(
                502, f"приложение недоступно: {err}".encode(), "text/plain; charset=utf-8"
            )
        finally:
            conn.close()
        ctype = resp.getheader("Content-Type", "")
        if "text/html" in ctype:
            html = data.decode("utf-8", errors="replace")
            script = '<script src="/__ui/overlay.js" defer></script>'
            html = (
                html.replace("</body>", script + "</body>") if "</body>" in html else html + script
            )
            data = html.encode()
        self.send_response(resp.status)
        for key, value in resp.getheaders():
            if key.lower() not in HOP_BY_HOP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # адрес из документационного диапазона: пакет не уходит
            return str(s.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--target", default="http://localhost:5173", help="адрес приложения")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--host", default="0.0.0.0", help="0.0.0.0 — доступ из локальной сети")  # noqa: S104  justified: harness-ui dev proxy for LAN browser
    args = parser.parse_args()
    if not re.fullmatch(r"[\w.-]+", args.task_id) or not (ROOT / "tasks" / args.task_id).is_dir():
        sys.exit(f"нет задачи tasks/{args.task_id}/ (создайте: just task-new)")
    Handler.task_id = args.task_id
    Handler.target = urlsplit(args.target)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"UI-замечания для {args.task_id}: откройте http://{lan_ip()}:{args.port}/ "
        f"(прокси к {args.target}).\nAlt + клик по элементу или кнопка «💬 UI» внизу справа. "
        f"Файл: tasks/{args.task_id}/ui-feedback.md. Остановить: Ctrl+C.",
        flush=True,
    )
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
