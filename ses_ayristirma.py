import subprocess
import os
import torch
from faster_whisper import WhisperModel

# Model boyutları (MB cinsinden yaklaşık değerler)
WHISPER_BOYUTLARI = {
    "tiny": 40,
    "base": 75,
    "small": 250,
    "medium": 1500,
    "large-v3": 3000
}

def whisper_modeli_kontrol_et(model_boyutu="medium"):
    """
    Model klasörde var mı diye bakar. 
    Yoksa indirilmesi gereken yaklaşık boyutu (MB) döndürür.
    Varsa 0 döndürür.
    """
    arama_dizini = os.path.join(os.getcwd(), "models", "whisper")
    
    # Klasör varsa içinde model boyutunu içeren bir alt klasör arıyoruz
    if os.path.exists(arama_dizini):
        for dosya in os.listdir(arama_dizini):
            if model_boyutu in dosya.lower():
                hedef_klasor = os.path.join(arama_dizini, dosya)
                # Klasörün içi boş mu diye kontrol et
                if os.path.isdir(hedef_klasor) and len(os.listdir(hedef_klasor)) > 2:
                    return 0 # Model zaten var, indirilecek veri yok
                    
    return WHISPER_BOYUTLARI.get(model_boyutu, 1500)

def whisper_modeli_indir(model_boyutu="medium"):
    """Sadece modeli indirir, UI tarafındaki kurulum ekranı için kullanılır."""
    model_dizini = os.path.join(os.getcwd(), "models", "whisper")
    os.makedirs(model_dizini, exist_ok=True)
    
    # WhisperModel'i CPU'da çalıştırarak sadece indirme işlemini tetikleriz
    WhisperModel(model_boyutu, device="cpu", compute_type="int8", download_root=model_dizini)
    return True

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
        # Modellerin her zaman kaydedileceği/okunacağı yerel dizin
        model_dizini = os.path.join(os.getcwd(), "models", "whisper")
        os.makedirs(model_dizini, exist_ok=True)
        
        # Faster-Whisper modelini yerel dizinden yükle (download_root parametresi ile)
        model = WhisperModel(
            model_boyutu, 
            device=cihaz, 
            compute_type=hesaplama_tipi,
            download_root=model_dizini
        )
        
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