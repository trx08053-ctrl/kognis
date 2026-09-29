#!/usr/bin/env python3
"""Веб-стек: разработка, скриншоты, браузеры для e2e, развёртывание в Docker.

    web.py dev [--port N]                  автоперезагрузка, миграции; настройки приложения —
                                           .deploy/dev.app.env; с frontend/ — пересборка интерфейса
    web.py shot [/путь] [--url U] [--name n]  скриншот → .evidence/screens/<n>.png
    web.py browsers                        установить Chromium для Playwright (e2e, скриншоты)
    web.py stage [--port 18000]            образ из HEAD → PostgreSQL + миграции + приложение
    web.py rollback [--env staging]        вернуть предыдущий образ (схема должна быть совместима!)
    web.py deploy --host ssh://user@server  то же на удалённом Docker (решение человека)
    web.py status | down [--env staging]
    web.py backup [--env E] [--host H]     дамп PostgreSQL → .deploy/backups/<env>-<время>.dump
    web.py restore FILE [--env E] [--host H]  восстановить дамп (app останавливается, затем /health)

Разворачивается только закоммиченный код (тег образа = короткий sha). Пароль БД окружения —
.deploy/<env>.env (создаётся, права 600, не в git). Секреты и настройки самого приложения
(ключи, режим) — .deploy/<env>.app.env: создаётся пустым, заполняет человек; попадает в контейнер
app. Файл защищён.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from http import HTTPStatus
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DEPLOY = ROOT / ".deploy"
COMPOSE = ROOT / "deploy" / "compose.yml"


def answers(key: str, default: str) -> str:
    text = (ROOT / ".copier-answers.yml").read_text()
    match = re.search(rf"^{key}:\s*['\"]?([^'\"\n]+)", text, re.M)
    return match.group(1).strip() if match else default


SLUG = answers("project_slug", ROOT.name)
PKG = answers("package_name", SLUG.replace("-", "_"))
PORT = answers("app_port", "8000")


def sh(*cmd: str, env: dict[str, str] | None = None, check: bool = True) -> str:
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        sys.exit(f"ошибка: {' '.join(cmd[:4])}…\n{(proc.stdout + proc.stderr).strip()[-2000:]}")
    return proc.stdout.strip()


def app_env(env: str) -> dict[str, str]:
    """Настройки приложения окружения из .deploy/<env>.app.env (KEY=value, # — комментарий)."""
    path = DEPLOY / f"{env}.app.env"
    pairs = [ln.split("=", 1) for ln in path.read_text().splitlines()] if path.exists() else []
    return {k.strip(): v.strip() for k, *rest in pairs for v in rest if k.strip() and k[0] != "#"}


def cmd_dev(a: argparse.Namespace) -> None:
    # ключи и режим приложения для разработки (.deploy/dev.app.env)
    os.environ.update(app_env("dev"))
    sh("uv", "run", "--locked", "alembic", "upgrade", "head")
    print(f"http://{local_ip()}:{a.port}  (Ctrl+C — остановить)", flush=True)
    everywhere = "0.0.0.0"  # noqa: S104  justified: harness-web dev-сервер для браузера в локальной сети
    cmd = ["uv", "run", "--locked", "uvicorn", f"{PKG}.web:create_app", "--factory",
           "--reload", "--host", everywhere, "--port", str(a.port)]  # fmt: skip
    if not FRONTEND.is_dir():
        subprocess.run(cmd, cwd=ROOT, check=False)
        return
    # один порт для всего: FastAPI отдаёт frontend/dist, vite пересобирает его при правках
    sh("pnpm", "--dir", "frontend", "build")
    watch = subprocess.Popen(["pnpm", "--dir", "frontend", "run", "watch"], cwd=ROOT)
    try:
        subprocess.run(cmd, cwd=ROOT, check=False)
    finally:
        watch.terminate()


def cmd_shot(a: argparse.Namespace) -> None:
    url = a.url or f"http://127.0.0.1:{PORT}{a.path}"
    name = a.name or (re.sub(r"[^\w-]+", "-", a.path.strip("/")) or "index")
    out = ROOT / ".evidence" / "screens" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    code = (
        "import sys\nfrom playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as p:\n"
        "    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1280, 'height': 800})\n"
        "    pg.goto(sys.argv[1]); pg.wait_for_load_state('networkidle')\n"
        "    pg.screenshot(path=sys.argv[2], full_page=True); b.close()\n"
    )
    sh("uv", "run", "--locked", "python", "-c", code, url, str(out))
    print(f"скриншот: {out.relative_to(ROOT)}  ({url})")


def cmd_browsers(_: argparse.Namespace) -> None:
    print(sh("uv", "run", "--locked", "playwright", "install", "chromium").splitlines()[-1:])


def env_file(env: str) -> Path:
    path = DEPLOY / f"{env}.env"
    if not path.exists():
        DEPLOY.mkdir(exist_ok=True)
        path.write_text(f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}\n")
        path.chmod(0o600)
    app_env = DEPLOY / f"{env}.app.env"
    if not app_env.exists():
        app_env.write_text("# секреты и настройки приложения для окружения (KEY=value), не в git\n")
        app_env.chmod(0o600)
    return path


def compose_base(
    env: str, tag: str, port: str, docker_host: str | None
) -> tuple[list[str], dict[str, str]]:
    """Команда docker compose окружения и её переменные (проект <slug>-<env>, пароль из .deploy)."""
    environ = {**os.environ, "IMAGE_TAG": tag, "APP_PORT": port, "DEPLOY_ENV": env}
    if docker_host:
        environ["DOCKER_HOST"] = docker_host
    cmd = ["docker", "compose", "-p", f"{SLUG}-{env}", "-f", str(COMPOSE),
           "--env-file", str(env_file(env))]  # fmt: skip
    return cmd, environ


def compose(env: str, tag: str, port: str, docker_host: str | None, *args: str) -> str:
    cmd, environ = compose_base(env, tag, port, docker_host)
    return sh(*cmd, *args, env=environ)


def history(env: str) -> list[str]:
    path = DEPLOY / f"{env}.history"
    return path.read_text().split() if path.exists() else []


def wait_health(port: str, docker_host: str | None) -> None:
    if docker_host:
        print("здоровье на удалённом хосте проверьте: curl https://<домен>/health")
        return
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == HTTPStatus.OK:
                    return
        except OSError:
            time.sleep(1)
    sys.exit(f"нет ответа /health за 60 с — `web.py status`; логи: docker logs {SLUG}-*-app-1")


def release(env: str, tag: str, port: str, docker_host: str | None) -> None:
    compose(env, tag, port, docker_host, "up", "-d", "--wait", "db")
    print("── миграции (alembic upgrade head)", flush=True)
    compose(env, tag, port, docker_host, "run", "--rm", "app", "alembic", "upgrade", "head")
    compose(env, tag, port, docker_host, "up", "-d", "app")
    wait_health(port, docker_host)


def scan_image(image: str, environ: dict[str, str]) -> None:
    """Trivy: HIGH/CRITICAL с доступным исправлением — стоп; исключения — .trivyignore (защищён)."""
    trivy = shutil.which("trivy")
    if trivy is None:
        sys.exit(
            "нет trivy — `mise install` (сканирование образа обязательно перед развёртыванием)"
        )
    print("── сканирование образа (trivy: HIGH/CRITICAL с исправлением)", flush=True)
    proc = subprocess.run(
        [trivy, "image", "--quiet", "--scanners", "vuln", "--severity", "HIGH,CRITICAL",
         "--ignore-unfixed", "--exit-code", "1", "--format", "table", image],
        cwd=ROOT, env=environ, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        sys.exit(
            f"{(proc.stdout + proc.stderr).strip()[-4000:]}\n\nв образе уязвимости с фиксом — "
            "обновите базовый образ/пакеты; осознанное исключение — .trivyignore (решение человека)"
        )


def cmd_stage(a: argparse.Namespace) -> None:
    if sh("git", "status", "--porcelain", "--untracked-files=no"):
        sys.exit("есть незакоммиченные изменения — разворачивается только закоммиченный код")
    tag = sh("git", "rev-parse", "--short", "HEAD")
    environ = {**os.environ, **({"DOCKER_HOST": a.host} if a.host else {})}
    print(f"── образ {SLUG}:{tag}", flush=True)
    sh("docker", "build", "-t", f"{SLUG}:{tag}", ".", env=environ)
    scan_image(f"{SLUG}:{tag}", environ)
    release(a.env, tag, a.port, a.host)
    hist = [t for t in history(a.env) if t != tag] + [tag]
    (DEPLOY / f"{a.env}.history").write_text("\n".join(hist[-10:]) + "\n")
    where = "удалённый хост" if a.host else f"http://{local_ip()}:{a.port}"
    print(f"OK: {a.env} = {SLUG}:{tag} → {where}")


def cmd_rollback(a: argparse.Namespace) -> None:
    hist = history(a.env)
    if len(hist) < 2:  # noqa: PLR2004  justified: harness-web need current and previous
        sys.exit("нет предыдущей версии для отката")
    prev = hist[-2]
    print(
        f"── откат {a.env}: {hist[-1]} → {prev} "
        "(миграции не откатываются: схема должна быть совместима)"
    )
    compose(a.env, prev, a.port, a.host, "up", "-d", "app")
    wait_health(a.port, a.host)
    (DEPLOY / f"{a.env}.history").write_text("\n".join([*hist[:-1]]) + "\n")
    print(f"OK: {a.env} = {SLUG}:{prev}")


def cmd_status(a: argparse.Namespace) -> None:
    hist = history(a.env)
    print(f"{a.env}: текущий {hist[-1] if hist else '—'}; история: {' '.join(hist[-5:]) or '—'}")
    print(compose(a.env, hist[-1] if hist else "none", a.port, a.host, "ps"))


def cmd_backup(a: argparse.Namespace) -> None:
    hist = history(a.env)
    tag = hist[-1] if hist else "none"
    out = DEPLOY / "backups" / f"{a.env}-{time.strftime('%Y%m%d-%H%M%S')}.dump"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd, environ = compose_base(a.env, tag, a.port, a.host)
    dump = [*cmd, "exec", "-T", "db", "pg_dump", "-U", "app", "-Fc", "app"]
    with out.open("wb") as fh:
        proc = subprocess.run(
            dump, cwd=ROOT, env=environ, stdout=fh, stderr=subprocess.PIPE, check=False
        )
    out.chmod(0o600)
    if proc.returncode != 0 or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        sys.exit(f"бэкап не удался: {proc.stderr.decode()[-800:]}")
    size = out.stat().st_size
    print(f"OK: бэкап {a.env} → {out.relative_to(ROOT)} ({size} байт; хранить как секрет)")


def cmd_restore(a: argparse.Namespace) -> None:
    dump = Path(a.file)
    if not dump.is_file():
        sys.exit(f"нет файла {dump}")
    hist = history(a.env)
    tag = hist[-1] if hist else "none"
    compose(a.env, tag, a.port, a.host, "stop", "app")
    cmd, environ = compose_base(a.env, tag, a.port, a.host)
    restore = [*cmd, "exec", "-T", "db", "pg_restore", "-U", "app", "-d", "app", "--clean",
               "--if-exists"]  # fmt: skip
    with dump.open("rb") as fh:
        proc = subprocess.run(
            restore, cwd=ROOT, env=environ, stdin=fh, capture_output=True, check=False
        )
    compose(a.env, tag, a.port, a.host, "up", "-d", "app")
    wait_health(a.port, a.host)
    if proc.returncode != 0:
        sys.exit(f"восстановление с ошибками: {proc.stderr.decode()[-800:]}")
    print(f"OK: {a.env} восстановлен из {dump.name}; проверьте вход и данные")


def cmd_down(a: argparse.Namespace) -> None:
    compose(a.env, "none", a.port, a.host, "down")
    print(f"{a.env}: остановлено (данные БД сохранены в томе)")


def local_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))
            return str(s.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dev")
    d.add_argument("--port", default=PORT)
    d.set_defaults(func=cmd_dev)
    s = sub.add_parser("shot")
    s.add_argument("path", nargs="?", default="/")
    s.add_argument("--url")
    s.add_argument("--name")
    s.set_defaults(func=cmd_shot)
    sub.add_parser("browsers").set_defaults(func=cmd_browsers)
    for name, func, env in (
        ("stage", cmd_stage, "staging"), ("deploy", cmd_stage, "production"),
        ("rollback", cmd_rollback, "staging"), ("status", cmd_status, "staging"),
        ("down", cmd_down, "staging"), ("backup", cmd_backup, "staging"),
        ("restore", cmd_restore, "staging"),
    ):  # fmt: skip
        x = sub.add_parser(name)
        x.add_argument("--env", default=env)
        x.add_argument("--port", default="18000")
        x.add_argument(
            "--host", required=name == "deploy", help="DOCKER_HOST, например ssh://deploy@srv"
        )
        if name == "restore":
            x.add_argument("file", help="файл дампа (.deploy/backups/…)")
        x.set_defaults(func=func)
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
