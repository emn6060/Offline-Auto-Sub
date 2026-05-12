import os
import torch
import datetime

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
except ImportError:
    raise ImportError(
        "Transformers yüklenemedi. Terminalde şu komutu çalıştırın:\n"
        "pip install transformers==4.44.0 sentencepiece safetensors"
    )

NLLB_MODEL_ADI = "facebook/nllb-200-distilled-600M"
NLLB_YEREL_KLASOR = "nllb-200-distilled-600M"
CEVIRI_MODEL_BOYUTU_MB = 1200 # NLLB boyutu yaklaşık 1.2 GB

# Whisper'ın döndürdüğü standart kısa kodları NLLB'nin formatına çeviren sözlük
NLLB_DIL_KODLARI = {
    "tr": "tur_Latn", "en": "eng_Latn", "de": "deu_Latn", "fr": "fra_Latn",
    "es": "spa_Latn", "it": "ita_Latn", "ru": "rus_Cyrl", "ar": "arb_Arab",
    "zh": "zho_Hans", "ja": "jpn_Jpan", "ko": "kor_Hang", "pt": "por_Latn"
}

def ceviri_modeli_kontrol_et(kaynak_dil=None, hedef_dil=None):
    """Artık dil parametrelerine gerek yok, tek bir model hepsini çeviriyor."""
    yerel_yol = os.path.join(os.getcwd(), "models", "translate", NLLB_YEREL_KLASOR)
    
    # Klasör var mı ve içi dolu mu?
    if os.path.exists(yerel_yol) and len(os.listdir(yerel_yol)) > 2:
        return 0 # Model mevcut
        
    return CEVIRI_MODEL_BOYUTU_MB

def ceviri_modelini_indir(kaynak_dil=None, hedef_dil=None):
    """Sadece tek bir NLLB modelini indirir."""
    from huggingface_hub import snapshot_download
    
    yerel_yol = os.path.join(os.getcwd(), "models", "translate", NLLB_YEREL_KLASOR)
    os.makedirs(yerel_yol, exist_ok=True)
    
    try:
        snapshot_download(repo_id=NLLB_MODEL_ADI, local_dir=yerel_yol)
        return True, "Başarılı"
    except Exception as e:
        return False, f"İndirme hatası: {str(e)}"

class CeviriVeSrtYoneticisi:
    def __init__(self, kaynak_dil="en", hedef_dil="tr"):
        # Gelen dilleri NLLB kodlarına çevir, bulamazsa İngilizce/Türkçe varsay
        self.kaynak_nllb = NLLB_DIL_KODLARI.get(kaynak_dil, "eng_Latn")
        self.hedef_nllb = NLLB_DIL_KODLARI.get(hedef_dil, "tur_Latn")

        yerel_yol = os.path.join(os.getcwd(), "models", "translate", NLLB_YEREL_KLASOR)
        
        # Çevrimdışı mod: Klasör varsa yereli kullan, yoksa internetten çek
        if os.path.exists(yerel_yol) and len(os.listdir(yerel_yol)) > 2:
            self.model_yolu = yerel_yol
            self.offline_mod = True
        else:
            self.model_yolu = NLLB_MODEL_ADI
            self.offline_mod = False

        print(f"[{self.kaynak_nllb} -> {self.hedef_nllb}] NLLB modeli yükleniyor: {self.model_yolu}")

        if torch.cuda.is_available(): self.cihaz = torch.device("cuda")
        elif torch.backends.mps.is_available(): self.cihaz = torch.device("mps")
        else: self.cihaz = torch.device("cpu")

        print("Donanım: " + str(self.cihaz))
        self._modeli_yukle()

    def _modeli_yukle(self):
        try:
            print(f"Çeviri modeli yükleniyor (Offline Mod: {self.offline_mod})...")
            # NLLB'de tokenizer'a kaynağın dilini belirtmemiz gerekiyor
            self.kelime_ayirici = AutoTokenizer.from_pretrained(
                self.model_yolu, 
                src_lang=self.kaynak_nllb,
                local_files_only=self.offline_mod
            )
            self.ceviri_modeli = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_yolu,
                local_files_only=self.offline_mod
            ).to(self.cihaz)
            print("Model başarıyla yüklendi.")
        except Exception as e:
            if self.offline_mod:
                print("Yerel yükleme başarısız, internet üzerinden deneniyor...")
                self.offline_mod = False
                self._modeli_yukle()
            else:
                raise Exception("Çeviri modeli yüklenemedi!\nDetay: " + str(e))

    def metinleri_toplu_cevir(self, metinler, yigin_boyutu=16, ilerleme_kancasi=None):
        if getattr(self, "kelime_ayirici", None) is None or getattr(self, "ceviri_modeli", None) is None:
            raise RuntimeError("Model yüklenmemiş.")
            
        if not metinler: return []

        cevrilmis_metinler = []
        toplam_metin = len(metinler)
        
        # NLLB'nin hedef dili bilmesi için gerekli token ID'si
        hedef_dil_id = self.kelime_ayirici.convert_tokens_to_ids(self.hedef_nllb)

        for i in range(0, toplam_metin, yigin_boyutu):
            yigin = metinler[i:i + yigin_boyutu]
            girdi_verisi = self.kelime_ayirici(
                yigin, return_tensors="pt", padding=True, truncation=True, max_length=512
            ).to(self.cihaz)

            with torch.no_grad():
                # generate fonksiyonuna hedef dili forced_bos_token_id ile veriyoruz
                cevrilmis_cikti = self.ceviri_modeli.generate(
                    **girdi_verisi, 
                    forced_bos_token_id=hedef_dil_id,
                    max_length=512
                )

            cevrilmis_yigin = self.kelime_ayirici.batch_decode(
                cevrilmis_cikti, skip_special_tokens=True
            )
            cevrilmis_metinler.extend(cevrilmis_yigin)

            if ilerleme_kancasi:
                islenen = min(i + yigin_boyutu, toplam_metin)
                yuzde = int((islenen / toplam_metin) * 100)
                ilerleme_kancasi(yuzde)

        return cevrilmis_metinler

    def saniyeyi_zaman_damgasina_cevir(self, saniye):
        zaman_farki = datetime.timedelta(seconds=saniye)
        toplam_saniye = int(zaman_farki.total_seconds())
        saat = toplam_saniye // 3600
        dakika = (toplam_saniye % 3600) // 60
        kalan_saniye = toplam_saniye % 60
        milisaniye = int(zaman_farki.microseconds / 1000)
        return "%02d:%02d:%02d,%03d" % (saat, dakika, kalan_saniye, milisaniye)

    def altyazi_olustur(self, ses_verileri, dosya_adi, ilerleme_kancasi=None):
        if not ses_verileri: return dosya_adi

        orijinal_metinler = [veri['metin'] for veri in ses_verileri]
        cevrilmis_metinler = self.metinleri_toplu_cevir(
            orijinal_metinler, yigin_boyutu=16, ilerleme_kancasi=ilerleme_kancasi
        )

        with open(dosya_adi, "w", encoding="utf-8") as dosya:
            for indeks, (veri, ceviri) in enumerate(zip(ses_verileri, cevrilmis_metinler), start=1):
                baslangic = self.saniyeyi_zaman_damgasina_cevir(veri['baslangic'])
                bitis = self.saniyeyi_zaman_damgasina_cevir(veri['bitis'])
                dosya.write(str(indeks) + "\n")
                dosya.write(baslangic + " --> " + bitis + "\n")
                dosya.write(ceviri + "\n\n")

        return dosya_adi