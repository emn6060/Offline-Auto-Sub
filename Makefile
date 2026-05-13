# IronScript Makefile
# Bu Makefile, projenin kurulumu, derlenmesi ve calistirilmasi islemlerini kolaylastirmak icin hazirlanmistir.

# Degiskenler
PYTHON = python
PIP = pip
CXX = g++
CXXFLAGS = -shared -o
TARGET_DLL = hardsubbing.dll
SOURCE_CPP = hardsubbing.cpp

.PHONY: all install compile run clean help

# Varsayilan hedef
all: install compile run

# 1. Python Bagimliliklarini Yukle (CUDA Uyumlu)
install:
	@echo "NVIDIA GPU hizlandirmasi icin CUDA destekli PyTorch yukleniyor..."
	$(PIP) install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
	@echo "Diger bagimliliklar yukleniyor..."
	$(PIP) install -r requirements.txt
	@echo "Tum bagimliliklar basariyla yuklendi."

# 2. C++ Modulunu (DLL) Derle
# Not: Sisteminizde g++ (MinGW veya benzeri) kurulu olmalidir.
compile:
	@echo "C++ hardsubbing modulu derleniyor..."
	$(CXX) $(CXXFLAGS) $(TARGET_DLL) $(SOURCE_CPP)
	@echo "Derleme tamamlandi: $(TARGET_DLL)"

# 3. Uygulamayi Calistir
run:
	@echo "IronScript baslatiliyor..."
	$(PYTHON) ui.py

# 4. Gecici Dosyalari ve Derlenen Kitapligi Temizle
# (Windows Cmd/Powershell uyumlu temizlik komutu)
clean:
	@echo "Temizlik yapiliyor..."
	@if exist $(TARGET_DLL) del $(TARGET_DLL)
	@if exist gecici_ses.wav del gecici_ses.wav
	@if exist gecici_altyazi.srt del gecici_altyazi.srt
	@echo "Temizlik tamamlandi."

# Yardim Menusu
help:
	@echo "Kullanim:"
	@echo "  make install  - CUDA uyumlu PyTorch ve diger paketleri yukler."
	@echo "  make compile  - C++ (hardsubbing.cpp) DLL dosyasini derler."
	@echo "  make run      - Uygulamayi (ui.py) baslatir."
	@echo "  make clean    - Derlenen DLL'i ve gecici wav/srt dosyalarini siler."
	@echo "  make all      - Yukle, derle ve calistir komutlarini sirayla yapar."