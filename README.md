# 📊 WinConsoleAudio (CAVA for Windows)

**WinConsoleAudio** — это высокопроизводительный консольный аудио-визуализатор для Windows, вдохновленный популярной Linux-утилитой [CAVA](https://github.com/karlstav/cava). Программа захватывает системный звук (WASAPI Loopback) напрямую из динамиков/наушников и строит динамический спектр частот в реальном времени с поддержкой субсимвольного разрешения, плавной гравитации и цветовых градиентов.

**WinConsoleAudio** is a high-performance terminal audio visualizer for Windows, heavily inspired by the popular Linux utility [CAVA](https://github.com/karlstav/cava). It captures system loopback audio (WASAPI Loopback) directly from speakers/headphones and renders a real-time dynamic frequency spectrum featuring sub-character resolution, smooth gravity decay, and vertical color gradients.

---

## ✨ Особенности / Features

*   **Захват звука без драйверов / Driverless Loopback**: Использует интерфейсы WASAPI Loopback, записывая системные звуки без установки виртуальных кабелей или Stereo Mix.
*   **Двухпоточная архитектура / Multi-threaded Engine**:
    *   Поток захвата (захватывает сэмплы непрерывно без пропусков).
    *   Поток визуализации (работает на стабильных 60 FPS, обеспечивая плавное затухание полос при паузе в музыке).
*   **Математика CAVA / CAVA-accurate DSP**: Логарифмическое распределение частотных полос, Hann-окно, быстрое преобразование Фурье (FFT), компенсационный EQ-фильтр высоких частот и автонастройка чувствительности (autosens).
*   **Плавные градиенты / Smooth Gradients**: Поддерживает вертикальный градиент с настраиваемыми HEX-цветами (цвета перетекают снизу вверх).
*   **Адаптивность / Fully Responsive**: Автоматически подстраивает количество полос под ширину и высоту окна терминала при изменении размеров.

---

## 🚀 Быстрый старт / Quick Start

1.  Убедитесь, что у вас установлены библиотеки Python:
    Ensure you have the required Python libraries installed:
    ```bash
    pip install pyaudiowpatch numpy
    ```
2.  Запустите визуализатор через файл **`run.bat`** (или выполните команду `python cava.py` в консоли).
    Run the visualizer via **`run.bat`** (or execute `python cava.py` in your terminal).
3.  Для выхода нажмите клавишу **`ESC`**, **`Q`** или **`Ctrl+C`**.
    To quit, press **`ESC`**, **`Q`**, or **`Ctrl+C`**.

---

## 🛠️ Настройка / Configuration (`config.txt`)

Вы можете настраивать визуализатор в файле `config.txt`:
You can configure the visualizer in the `config.txt` file:

*   `color`: Базовый цвет полос (при выключенном градиенте).
*   `gradient`: Включение/выключение вертикального градиента (`true` / `false`).
*   `color_bottom` / `color_top`: HEX-коды цветов для нижней (басы) и верхней (высокие) точек градиента.
*   `bars`: Количество полос (`auto` для автоподгонки под окно или число, например `30`, `40`).
*   `fps`: Максимальная кадровая частота (`30`, `60`, `75`, `90` кадров в секунду).
*   `smoothing`: Коэффициент сглаживания фильтра (от `0.1` — быстрый/резкий, до `1.0` — плавный/медленный). Рекомендуется `0.77`.
*   `low_cutoff` / `high_cutoff`: Диапазон воспроизводимых частот в Герцах (по умолчанию `50` — `12000`).
*   `sensitivity`: Множитель громкости: `auto` (автоподстройка) или фиксированное число (например, `1.5`, `2.0`).

---

## 📄 Лицензия / License

Этот проект распространяется под свободной лицензией **MIT License**. Подробнее см. в файле `LICENSE`.
This project is licensed under the **MIT License** - see the `LICENSE` file for details.
