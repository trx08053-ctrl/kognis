# Секреты

В git хранятся только зашифрованные файлы `*.enc.yaml` / `*.enc.env` (SOPS + age, правила в `.sops.yaml`).
Приватный ключ — `~/.config/sops/age/keys.txt`, он у человека. Агенту чтение и расшифровка запрещены.

```bash
sops secrets/app.enc.yaml                          # создать/редактировать (человек)
sops exec-env secrets/app.enc.env 'just run'        # запустить приложение с секретами
```

Утечка секрета → ротация ключа у провайдера, затем `sops updatekeys`, запись в `docs/RUNBOOK.md`.
