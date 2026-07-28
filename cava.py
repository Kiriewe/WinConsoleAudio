import os
import sys
import time
import math
import threading
import queue
import msvcrt
import numpy as np
import pyaudiowpatch as pyaudio

# Включаем поддержку UTF-8 и ANSI цветов / Enable UTF-8 and ANSI escape codes on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
os.system('')

# ANSI коды управления экраном / Console control sequences
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CURSOR_HOME = "\033[H"
CLEAR_SCREEN = "\033[2J"
COLOR_RESET = "\033[0m"

# Вертикальные блоки Unicode для субсимвольного разрешения / Unicode Block Elements for sub-character resolution
PARTIAL_BLOCKS = [' ', ' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']

# Глобальный флаг остановки потока захвата / Thread safety exit flag
stop_event = threading.Event()
audio_queue = queue.Queue()

def parse_bool(val):
    return val.lower() in ('true', 'yes', '1', 'on')

def load_config():
    """
    Парсит config.txt и загружает настройки.
    Parses config.txt and returns settings dict.
    """
    color_map = {
        'green': (0, 255, 0),
        'red': (255, 0, 0),
        'blue': (0, 0, 255),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'yellow': (255, 255, 0),
        'white': (255, 255, 255),
        'orange': (255, 127, 0),
        'purple': (128, 0, 128),
        'pink': (255, 192, 203),
    }
    
    # Значения по умолчанию / Default values
    cfg = {
        'color': (0, 255, 255),
        'gradient': True,
        'color_bottom': (0, 255, 102),
        'color_top': (255, 0, 127),
        'bars': 'auto',
        'fps': 60,
        'smoothing': 0.77,
        'low_cutoff': 50,
        'high_cutoff': 12000,
        'sensitivity': 'auto'
    }
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.txt")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        key = key.strip().lower()
                        val = val.strip()
                        
                        if key == 'color':
                            val_lower = val.lower()
                            is_hex = (val_lower.startswith('#') and len(val_lower) == 7 and 
                                      all(c in '0123456789abcdef' for c in val_lower[1:]))
                            if is_hex:
                                r = int(val_lower[1:3], 16)
                                g = int(val_lower[3:5], 16)
                                b = int(val_lower[5:7], 16)
                                cfg['color'] = (r, g, b)
                            elif val_lower in color_map:
                                cfg['color'] = color_map[val_lower]
                        elif key == 'gradient':
                            cfg['gradient'] = parse_bool(val)
                        elif key in ('color_bottom', 'color_top'):
                            val_lower = val.lower()
                            is_hex = (val_lower.startswith('#') and len(val_lower) == 7 and 
                                      all(c in '0123456789abcdef' for c in val_lower[1:]))
                            if is_hex:
                                r = int(val_lower[1:3], 16)
                                g = int(val_lower[3:5], 16)
                                b = int(val_lower[5:7], 16)
                                cfg[key] = (r, g, b)
                            elif val_lower in color_map:
                                cfg[key] = color_map[val_lower]
                        elif key == 'bars':
                            if val.lower() == 'auto':
                                cfg['bars'] = 'auto'
                            else:
                                try:
                                    cfg['bars'] = int(val)
                                except ValueError:
                                    pass
                        elif key == 'fps':
                            try:
                                cfg['fps'] = int(val)
                            except ValueError:
                                pass
                        elif key == 'smoothing':
                            try:
                                cfg['smoothing'] = float(val)
                            except ValueError:
                                pass
                        elif key == 'low_cutoff':
                            try:
                                cfg['low_cutoff'] = int(val)
                            except ValueError:
                                pass
                        elif key == 'high_cutoff':
                            try:
                                cfg['high_cutoff'] = int(val)
                            except ValueError:
                                pass
                        elif key == 'sensitivity':
                            if val.lower() == 'auto':
                                cfg['sensitivity'] = 'auto'
                            else:
                                try:
                                    cfg['sensitivity'] = float(val)
                                except ValueError:
                                    pass
        except Exception:
            pass
    return cfg

class CavaEngine:
    """
    DSP движок CAVA: Hann-окно, БПФ (FFT), логарифмическое распределение, EQ-фильтр и сглаживание.
    Core CAVA DSP engine emulated in Python.
    """
    def __init__(self, num_bars, sample_rate, low_cutoff, high_cutoff, smoothing, sensitivity):
        self.num_bars = num_bars
        self.sample_rate = sample_rate
        self.low_cutoff = low_cutoff
        self.high_cutoff = high_cutoff
        self.smoothing = smoothing
        self.sensitivity_cfg = sensitivity
        
        self.fft_size = 2048
        self.buffer = np.zeros(self.fft_size, dtype=np.float32)
        
        # Расчет логарифмических границ частот / Compute logarithmic cutoff frequencies
        freq_const = np.log10(low_cutoff / high_cutoff) / (1.0 / (num_bars + 1) - 1.0)
        
        self.cutoffs = []
        for n in range(num_bars + 1):
            coeff = -freq_const + ((n + 1) / (num_bars + 1)) * freq_const
            freq = high_cutoff * (10 ** coeff)
            self.cutoffs.append(freq)
            
        # Индексы БПФ бинов / Mapping frequencies to FFT bins
        bin_indices = []
        for freq in self.cutoffs:
            idx = int(freq * self.fft_size / sample_rate)
            idx = max(1, min(self.fft_size // 2, idx))
            bin_indices.append(idx)
            
        # Границы фильтров для каждой полосы / Set lower & upper bounds for each bar
        self.lower_bins = []
        self.upper_bins = []
        for n in range(num_bars):
            l_bin = bin_indices[n]
            u_bin = bin_indices[n+1] - 1
            if u_bin < l_bin:
                u_bin = l_bin
            self.lower_bins.append(l_bin)
            self.upper_bins.append(u_bin)
            
        # Разделяем перекрывающиеся бины басов / Push bins up to guarantee at least 1 bin per bar
        for n in range(1, num_bars):
            if self.lower_bins[n] <= self.lower_bins[n - 1]:
                self.lower_bins[n] = self.lower_bins[n - 1] + 1
                self.upper_bins[n - 1] = self.lower_bins[n] - 1
                if self.upper_bins[n] < self.lower_bins[n]:
                    self.upper_bins[n] = self.lower_bins[n]
                    
        # Вычисление эквалайзера (EQ) для компенсации высоких частот / Compute EQ multipliers
        self.eq = []
        for n in range(num_bars):
            band_width = self.upper_bins[n] - self.lower_bins[n] + 1
            # Усиление пропорционально частоте / Frequency-based amplitude compensation
            val = (self.cutoffs[n + 1] ** 0.85) / band_width
            self.eq.append(val)
        self.eq = np.array(self.eq, dtype=np.float32)
        
        # Общая нормализация амплитуды / Apply general amplitude scaling
        self.eq *= 4.0 / np.log2(self.fft_size)
        
        # Состояние гравитации и интегратора CAVA / CAVA gravity & integration state
        self.prev_out = np.zeros(num_bars, dtype=np.float32)
        self.peak = np.zeros(num_bars, dtype=np.float32)
        self.fall = np.zeros(num_bars, dtype=np.float32)
        self.mem = np.zeros(num_bars, dtype=np.float32)
        
        # Чувствительность / Sensitivity state
        self.sens = 1.0
        self.sens_init = True
        self.framerate = 60.0
        
    def add_samples(self, new_samples):
        num_new = len(new_samples)
        if num_new >= self.fft_size:
            self.buffer[:] = new_samples[-self.fft_size:]
        else:
            self.buffer = np.roll(self.buffer, -num_new)
            self.buffer[-num_new:] = new_samples
            
    def execute(self):
        # Применяем Hann окно и делаем БПФ / Apply window function and compute FFT
        windowed = self.buffer * np.hanning(self.fft_size)
        fft_out = np.abs(np.fft.rfft(windowed))
        
        # Группируем спектр по полосам / Extract bar amplitudes
        bar_values = np.zeros(self.num_bars, dtype=np.float32)
        for n in range(self.num_bars):
            l_bin = self.lower_bins[n]
            u_bin = self.upper_bins[n]
            band_sum = np.sum(fft_out[l_bin : u_bin + 1])
            bar_values[n] = band_sum * self.eq[n]
            
        # Применяем чувствительность / Apply sensitivity gain
        if self.sensitivity_cfg == 'auto':
            bar_values *= self.sens
        else:
            bar_values *= self.sensitivity_cfg
            
        # Фильтры CAVA (гравитация и сглаживание) / CAVA gravity and decay smoothing
        framerate_mod = 60.0 / self.framerate
        gravity_mod = (framerate_mod ** 2.5) * 2.0 / self.smoothing
        integral_mod = framerate_mod ** 0.1
        
        overshoot = False
        silence = np.sum(bar_values) < 0.001
        
        for n in range(self.num_bars):
            val = bar_values[n]
            
            # Спад полос (гравитация) / Gravity falloff
            if val < self.prev_out[n] and self.smoothing > 0.1:
                val = self.peak[n] * (1.0 - (self.fall[n] * self.fall[n] * gravity_mod))
                val = max(0.0, val)
                self.fall[n] += 0.028
            else:
                self.peak[n] = val
                self.fall[n] = 0.0
            self.prev_out[n] = val
            
            # Интегратор сглаживания / Integral filter
            val = self.mem[n] * self.smoothing / integral_mod + val
            self.mem[n] = val
            
            bar_values[n] = val
            
            if self.sensitivity_cfg == 'auto' and val > 1.0:
                overshoot = True
                
        # Автоподстройка чувствительности (autosens) / Dynamic sensitivity adjustment
        if self.sensitivity_cfg == 'auto':
            bar_values = np.clip(bar_values, 0.0, 1.0)
            
            if overshoot:
                self.sens *= (1.0 - 0.02 * framerate_mod)
                self.sens_init = False
            else:
                if not silence:
                    self.sens *= (1.0 + 0.001 * framerate_mod)
                    if self.sens_init:
                        self.sens *= (1.0 + 0.1 * framerate_mod)
                        
        return bar_values

def audio_capture_worker(p, device_info):
    """
    Фоновый поток захвата системного звука через WASAPI Loopback.
    Background audio capture thread using WASAPI loopback.
    """
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=device_info["maxInputChannels"],
            rate=int(device_info["defaultSampleRate"]),
            input=True,
            input_device_index=device_info["index"],
            frames_per_buffer=1024
        )
    except Exception as e:
        print(f"Error opening audio device loopback: {e}")
        return
        
    num_channels = device_info["maxInputChannels"]
    
    while not stop_event.is_set():
        try:
            # Чтение звукового буфера (блокирующее) / Read audio chunk
            data = stream.read(512, exception_on_overflow=False)
            if not data:
                continue
                
            # Нормализация в диапазон [-1.0, 1.0] / Convert int16 bytes to normalized float32
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Суммируем стерео в моно / Convert stereo/multi-channel to mono
            if num_channels >= 2:
                samples_mono = np.mean(samples.reshape(-1, num_channels), axis=1)
            else:
                samples_mono = samples
                
            audio_queue.put(samples_mono)
        except Exception:
            time.sleep(0.01)
            
    stream.close()

def main():
    # Инициализация PyAudio и поиск устройства WASAPI Loopback
    # Init PyAudio and look for default speakers loopback device
    p = pyaudio.PyAudio()
    
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except OSError:
        print("Error: WASAPI host API is not available on this Windows system.")
        p.terminate()
        sys.exit(1)
        
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    
    loopback_device = None
    if default_speakers.get("isLoopbackDevice", False):
        loopback_device = default_speakers
    else:
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                loopback_device = loopback
                break
        if loopback_device is None:
            # Fallback to the first available loopback device
            for loopback in p.get_loopback_device_info_generator():
                loopback_device = loopback
                break
                
    if loopback_device is None:
        print("Error: No audio loopback device found. Playback recording unavailable.")
        p.terminate()
        sys.exit(1)
        
    # Считываем конфигурацию / Load settings
    cfg = load_config()
    sample_rate = int(loopback_device["defaultSampleRate"])
    
    # Запускаем рабочий поток захвата звука / Start background audio capture thread
    capture_thread = threading.Thread(target=audio_capture_worker, args=(p, loopback_device))
    capture_thread.daemon = True
    capture_thread.start()
    
    # Подготовка консоли / Setup console screen
    sys.stdout.write(CLEAR_SCREEN)
    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()
    
    prev_width, prev_height = 0, 0
    engine = None
    
    # Время ожидания кадра / Frame target sleep time
    target_sleep = 1.0 / cfg['fps']
    
    try:
        while True:
            # Выход по кнопкам ESC, Q или Ctrl+C
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\x1b', b'q', b'Q', b'\x03'):
                    break
                    
            # Проверяем размеры терминала / Get current terminal size
            try:
                width, height = os.get_terminal_size()
            except Exception:
                width, height = 80, 25
                
            viz_height = height - 1
            if viz_height < 3:
                sys.stdout.write(CURSOR_HOME + "Terminal too small / Окно слишком мало")
                sys.stdout.flush()
                time.sleep(0.1)
                continue
                
            # Расчет полос в зависимости от ширины экрана / Calculate number of bars based on screen width
            if cfg['bars'] == 'auto':
                num_bars = (width + 1) // 2
                num_bars = max(10, min(120, num_bars))
            else:
                num_bars = cfg['bars']
                
            # Пересоздаем движок при ресайзе / Reinitialize DSP engine if sizes or counts change
            if engine is None or engine.num_bars != num_bars:
                engine = CavaEngine(num_bars, sample_rate, cfg['low_cutoff'], cfg['high_cutoff'], cfg['smoothing'], cfg['sensitivity'])
                
            # Очистка экрана при изменении разрешения / Screen clear on resize
            if width != prev_width or height != prev_height:
                sys.stdout.write(CLEAR_SCREEN)
                sys.stdout.flush()
                prev_width = width
                prev_height = height
                
            # Считываем накопленные сэмплы из очереди / Pull fresh samples from capture thread
            new_samples_list = []
            while not audio_queue.empty():
                try:
                    new_samples_list.append(audio_queue.get_nowait())
                except queue.Empty:
                    break
                    
            if len(new_samples_list) > 0:
                new_samples = np.concatenate(new_samples_list)
                engine.add_samples(new_samples)
                
            # Рассчитываем кадр спектра / Process DSP steps
            engine.framerate = cfg['fps']
            bar_values = engine.execute()
            
            # Строим 2D-сетку отображения / Build visualizer grid matrix
            grid = [[' ' for _ in range(num_bars)] for _ in range(viz_height)]
            for col in range(num_bars):
                v = bar_values[col]
                # Высота полосы в юнитах (каждый символ высотой 8 юнитов)
                h_units = v * viz_height * 8
                full_blocks = int(h_units) // 8
                rem = int(h_units) % 8
                
                for y in range(viz_height):
                    if y < full_blocks:
                        grid[y][col] = '█'
                    elif y == full_blocks and rem > 0:
                        grid[y][col] = PARTIAL_BLOCKS[rem]
                    else:
                        grid[y][col] = ' '
                        
            # Формируем строки кадра с раскраской / Render lines with coloring
            frame_lines = []
            for y in range(viz_height - 1, -1, -1):
                row_chars = []
                for col in range(num_bars):
                    row_chars.append(grid[y][col])
                    if col < num_bars - 1:
                        row_chars.append(' ')
                row_str = "".join(row_chars)
                
                # Расчет цвета (градиент или сплошной) / Apply gradient or single solid color
                if cfg['gradient']:
                    factor = y / max(1, viz_height - 1)
                    r = int(cfg['color_bottom'][0] + (cfg['color_top'][0] - cfg['color_bottom'][0]) * factor)
                    g = int(cfg['color_bottom'][1] + (cfg['color_top'][1] - cfg['color_bottom'][1]) * factor)
                    b = int(cfg['color_bottom'][2] + (cfg['color_top'][2] - cfg['color_bottom'][2]) * factor)
                    color_esc = f"\033[38;2;{r};{g};{b}m"
                else:
                    color_esc = f"\033[38;2;{cfg['color'][0]};{cfg['color'][1]};{cfg['color'][2]}m"
                    
                frame_lines.append(color_esc + row_str + COLOR_RESET)
                
            frame = "\n".join(frame_lines)
            sys.stdout.write(CURSOR_HOME + frame)
            sys.stdout.flush()
            
            time.sleep(target_sleep)
            
    except KeyboardInterrupt:
        pass
    finally:
        # Корректное завершение потоков и сброс консоли / Restore terminal states
        stop_event.set()
        capture_thread.join(timeout=1.0)
        sys.stdout.write(CLEAR_SCREEN)
        sys.stdout.write(CURSOR_HOME)
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()
        p.terminate()

if __name__ == '__main__':
    main()
