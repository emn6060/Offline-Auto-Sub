# Iron Script
AI-Powered Automatic Subtitle Transcription, Translation & Hardsubbing Tool
*(Yapay Zeka Destekli Otomatik Altyazı Çeviri ve Gömme Aracı)*

---

## 🇹🇷 TÜRKÇE DOKÜMANTASYON

IronScript; video dosyalarındaki konuşmaları yapay zeka ile analiz eden, metne dönüştüren, istenilen dile çeviren ve bu altyazıları donanım hızlandırması kullanarak videoya kalıcı olarak (hardsub) gömen profesyonel bir masaüstü uygulamasıdır.

### Ekran Görüntüleri

**Uygulama Arayüzü**
![IronScript Arayüzü](ui_screenshot.png)

**Örnek Çıktılar (Korece ve Türkçe)**
<p align="center">
  <img src="sample_korean.png" width="48%" alt="Korece Altyazılı Çıktı">
  &nbsp;
  <img src="sample_turkish.png" width="48%" alt="Türkçe Altyazılı Çıktı">
</p>

### Özellikler

* **Yüksek Hassasiyetli Ses Tanıma (STT):** `faster-whisper` (medium model) kullanarak videoları yüksek doğrulukla metne döker.
* **Gelişmiş Çeviri Motoru:** Meta'nın `NLLB-200-distilled-600M` modelini kullanarak 12+ dilde yüksek kaliteli çeviri sağlar.
* **Donanım Hızlandırmalı Render (NVENC):** C++ ile yazılmış `hardsubbing.dll` ve FFmpeg aracılığıyla NVIDIA GPU (CUDA) üzerinden hızlı altyazı gömme işlemi yapar.
* **Canlı Stil Önizleme:** Font tipi, boyutu ve konumunu (alt/orta) video karesi üzerinde anlık olarak önizleme imkanı sunar.
* **Çevrimdışı Çalışma:** Gerekli modeller (Whisper ve NLLB) ilk kurulumda indirildikten sonra tamamen internet bağımsız çalışabilir.

### Gereksinimler

* **İşletim Sistemi:** Windows (Kütüphane `.dll` yapısı nedeniyle).
* **Donanım:** NVIDIA Ekran Kartı (CUDA ve NVENC desteği için).
* **Yazılım:**
    * Python 3.8+
    * **FFmpeg:** `C:\ffmpeg\ffmpeg.exe` konumunda yüklü olmalıdır.

### Kurulum ve Çalıştırma

1.  **Bağımlılıkları Yükleyin:**
    ```bash
    pip install torch faster-whisper transformers sentencepiece PyQt6 opencv-python huggingface_hub
    ```
2.  **FFmpeg'i Hazırlayın:**
    * [FFmpeg](https://ffmpeg.org/download.html) indirip `C:\ffmpeg\` klasörüne çıkartın.
3.  **Uygulamayı Başlatın:**
    ```bash
    python ui.py
    ```

---

## 🇬🇧 ENGLISH DOCUMENTATION

IronScript is an advanced desktop application designed to transcribe, translate, and hardcode subtitles into video files using AI models and hardware-accelerated rendering.

### Screenshots

**Application Interface**
![IronScript UI](ui_screenshot.png)

**Sample Outputs (Korean and Turkish)**
<p align="center">
  <img src="sample_korean.png" width="48%" alt="Korean Subtitled Output">
  &nbsp;
  <img src="sample_turkish.png" width="48%" alt="Turkish Subtitled Output">
</p>

### Features

* **High-Precision Speech-to-Text (STT):** Transcribes audio with high accuracy using the `faster-whisper` (medium) engine.
* **Advanced AI Translation:** Provides high-quality translations across 12+ languages using Meta's `NLLB-200-distilled-600M` model.
* **Hardware Accelerated Rendering (NVENC):** Fast subtitle embedding via NVIDIA GPU (CUDA) using a custom C++ `hardsubbing.dll` and FFmpeg.
* **Live Style Preview:** Allows real-time preview of font type, size, and position (bottom/middle) on the video frame.
* **Offline Capability:** Operates entirely offline after the initial download of AI models.

### Requirements

* **Operating System:** Windows (optimized for `.dll` integration).
* **Hardware:** NVIDIA GPU (Required for CUDA and NVENC acceleration).
* **Software:**
    * Python 3.8+
    * **FFmpeg:** Must be located at `C:\ffmpeg\ffmpeg.exe`.

### Setup and Launch

1.  **Install Dependencies:**
    ```bash
    pip install torch faster-whisper transformers sentencepiece PyQt6 opencv-python huggingface_hub
    ```
2.  **Prepare FFmpeg:**
    * Download [FFmpeg](https://ffmpeg.org/download.html) and extract it to `C:\ffmpeg\`.
3.  **Run the App:**
    ```bash
    python ui.py
    ```
