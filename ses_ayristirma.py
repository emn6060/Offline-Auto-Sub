import subprocess
import os
import torch
from faster_whisper import WhisperModel

# FFmpeg yolu — sistemde birden fazla lokasyonu dene
def ffmpeg_yolunu_bul():
    olasiliklar = [
        r"C:\ffmpeg\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        "ffmpeg",  # PATH'te varsa doğrudan çalışır
    ]
    for yol in olasiliklar:
        try:
            subprocess.run(
                [yol, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return yol
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise FileNotFoundError(
        "FFmpeg bulunamadı!\n"
        "Lütfen https://ffmpeg.org/download.html adresinden indirip\n"
        "C:\\ffmpeg\\ffmpeg.exe konumuna yerleştirin."
    )


def sesi_ayristir(video_yolu, cikti_ses_yolu="gecici_ses.wav"):
    ffmpeg_yolu = ffmpeg_yolunu_bul()
    
    komut = [
        ffmpeg_yolu, "-y", "-i", video_yolu,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        cikti_ses_yolu
    ]
    
    sonuc = subprocess.run(
        komut,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE  # Hata mesajlarını yakala
    )
    
    if sonuc.returncode != 0:
        hata_detay = sonuc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"FFmpeg ses ayrıştırma başarısız!\n"
            f"Video: {video_yolu}\n"
            f"Detay: {hata_detay[-500:]}"  # Son 500 karakteri göster
        )
    
    return cikti_ses_yolu


def videodan_metin_cikar(orijinal_video, model_boyutu="medium", durum_kancasi=None):
    gecici_ses = "gecici_ses.wav"

    try:
        if durum_kancasi:
            durum_kancasi(20, "Ses Ayrıştırılıyor (FFmpeg)...")
            
        sesi_ayristir(orijinal_video, gecici_ses)
        
        if durum_kancasi:
            durum_kancasi(40, "Metne Dönüştürülüyor (Faster-Whisper)...")
        
        # Donanım tespiti
        cihaz = "cuda" if torch.cuda.is_available() else "cpu"
        hesaplama_tipi = "float16" if cihaz == "cuda" else "int8"
        
        print(f"Whisper cihaz: {cihaz}, hesaplama tipi: {hesaplama_tipi}")
        
        # Faster-Whisper modelini yükle
        model = WhisperModel(model_boyutu, device=cihaz, compute_type=hesaplama_tipi)
        
        # Sesi metne dök
        segmentler, bilgi = model.transcribe(gecici_ses, beam_size=5)
        
        uyumlu_segmentler = []
        tam_metin_parcalari = []
        
        # Faster-Whisper jeneratör döndürür — tek geçişte oku
        for segment in segmentler:
            uyumlu_segmentler.append({
                'baslangic': segment.start,
                'bitis': segment.end,
                'metin': segment.text.strip()
            })
            tam_metin_parcalari.append(segment.text.strip())
            
        return {
            "dil": bilgi.language,
            "tam_metin": " ".join(tam_metin_parcalari),
            "segmentler": uyumlu_segmentler
        }

    except Exception as hata:
        raise RuntimeError(f"Ses işleme hatası: {str(hata)}") from hata

    finally:
        # Her durumda geçici dosyayı temizle
        if os.path.exists(gecici_ses):
            try:
                os.remove(gecici_ses)
            except OSError:
                pass  # Dosya kilitliyse sessizce geç