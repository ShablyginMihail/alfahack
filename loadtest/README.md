# Нагрузочный тест POST /process

Скрипт `load_process.py` повторяет поведение проверяющей системы: пары
«маскирование → демаскирование» по одному `payload_id`, keep-alive соединения,
разгон `--ramp` и плато `--steady`. Только стандартная библиотека Python 3.11.

```bash
python loadtest/load_process.py http://localhost:8000 \
  --conns 200 --procs 4 --ramp 20 --steady 60 --timeout 10 --json out.json
```

Итог — в stdout (окна 10 с и сводка по плато), с `--json` — в JSON-файл.