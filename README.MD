<h1 align="center">Anonymous&Discord</h1>

<p align="center">Десктопное приложение на <code>PyQt6</code> для работы с Discord-аккаунтами, токенами, прокси и массовой отправкой сообщений.</p>

<p align="center">
  <a href="https://t.me/Ab3ST"><b>Написать мне</b></a> | 
  <a href="https://t.me/Ab3stPublic"><b>Telegram Канал</b></a>
</p>

<p align="center">
  <img src="assets/6367166.webp" alt="Anonymous&Discord" width="220" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/PyQt6-GUI-41b883" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Status-Active-success" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
</p>

---

## Возможности

| Module | Description |
| --- | --- |
| Checker | Проверка токенов на валидность |
| Checker | Поддержка прокси |
| Broadcast | Массовая отправка сообщений по аккаунтам |
| Broadcast | Работа с вложениями |
| UI | Управление аккаунтами и прокси |

---

## Скриншоты

<table>
  <tr>
    <td align="center">
      <img src="assets/Аккаунты.png" alt="Accounts" width="360" />
      <br />
      <sub>Accounts</sub>
    </td>
    <td align="center">
      <img src="assets/Действие.png" alt="Action" width="360" />
      <br />
      <sub>Action</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="assets/Настройки.png" alt="Settings" width="360" />
      <br />
      <sub>Settings</sub>
    </td>
    <td align="center">
      <div></div>
    </td>
  </tr>
</table>

---

## Технологический стек

* **Core / Async:** `Python 3.13`, `aiohttp`, `aiofiles`
* **Proxy Support:** `aiohttp-socks` (SOCKS4, SOCKS5, HTTP)
* **GUI Framework:** `PyQt6` (кастомные стили, кастомные виджеты)
* **Video / Graphics:** `PyAV`, `NumPy` (для рендера видео-фона)

---

## Структура проекта

```bash
DISCORD-AUTO/
│
├── main.py
│
├── src/
│   ├── core/
│   ├── ui/
│   └── workers/
│
├── assets/
├── data/
└── checks/
```

---

## Установка и запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Если при запуске возникают ошибки, связанные с `av`, установи FFmpeg в систему и добавь его в `PATH`.

---

## Примечания

- При первом запуске база данных создается автоматически.
- Все основные настройки сохраняются локально в `data/app.db`.

---

## Поддержка

Если у вас возникли проблемы с установкой или запуском, пишите в Telegram:

[![Telegram PM](https://img.shields.io/badge/Telegram-Написать%20мне-blue?logo=telegram&logoColor=white)](https://t.me/Ab3ST)
[![Telegram Channel](https://img.shields.io/badge/Telegram-Канал%20проекта-222222?logo=telegram&logoColor=white)](https://t.me/Ab3stPublic)
