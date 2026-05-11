import sys
import os
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg"
import cv2
import ctypes
import platform
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFileDialog, QLabel, QProgressBar, 
                             QSlider, QFrame, QGroupBox, QComboBox, QListWidget,
                             QSpinBox, QMessageBox)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QImage, QPixmap, QFontDatabase

# --- ÇOKLU DİL SÖZLÜĞÜ ---
DIL_SECENEKLERI = {
    "Türkçe": "tr", "İngilizce": "en", "Almanca": "de", "Fransızca": "fr",
    "İspanyolca": "es", "İtalyanca": "it", "Rusça": "ru", "Arapça": "ar",
    "Çince": "zh", "Japonca": "ja", "Korece": "ko", "Portekizce": "pt"
}

ONIZLEME_METINLERI = {
    "Türkçe": "Altyazılar Böyle Gözükür",
    "İngilizce": "Subtitles look like this",
    "Almanca": "Untertitel sehen so aus",
    "Fransızca": "Les sous-titres ressemblent à ceci",
    "İspanyolca": "Los subtítulos se ven así",
    "İtalyanca": "I sottotitoli appaiono così",
    "Rusça": "Субтитры выглядят так",
    "Arapça": "تبدو الترجمة هكذا",
    "Çince": "字幕看起来像这样",
    "Japonca": "字幕はこんな感じです",
    "Korece": "자막은 이렇게 보입니다",
    "Portekizce": "As legendas ficam assim"
}

# =======================================================
# --- İŞLEYİCİ SINIFLAR (ARKA PLAN THREAD'LERİ) ---
# IDE'nin altını sarı çizdiği eksik sınıflar buradadır
# =======================================================

class KurulumIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal()

    def __init__(self, whisper_indir_lazim):
        super().__init__()
        self.whisper_indir_lazim = whisper_indir_lazim

    def run(self):
        try:
            if self.whisper_indir_lazim:
                self.ilerleme.emit(10, "Yapay Zeka Modeli İndiriliyor (Whisper ~1.5GB)...")
                from ses_ayristirma import whisper_modeli_indir
                whisper_modeli_indir("medium")
                
            self.ilerleme.emit(100, "Kurulum Tamamlandı!")
            self.tamamlandi.emit()
        except Exception as e:
            self.ilerleme.emit(0, f"Hata: {str(e)}")
            self.tamamlandi.emit()

class SttIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal(dict) # stt_verisi dönecek
    hata = pyqtSignal(str)

    def __init__(self, video_yolu):
        super().__init__()
        self.video_yolu = video_yolu

    def run(self):
        try:
            from ses_ayristirma import videodan_metin_cikar
            def durum_guncelle(yuzde, mesaj): self.ilerleme.emit(yuzde, mesaj)
            
            # STT işlemi
            stt_verisi = videodan_metin_cikar(self.video_yolu, durum_kancasi=durum_guncelle)
            self.tamamlandi.emit(stt_verisi)
        except Exception as e:
            self.hata.emit(str(e))

class ModelIndirmeIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal(bool, str)

    def __init__(self, kaynak_dil, hedef_dil):
        super().__init__()
        self.kaynak_dil = kaynak_dil
        self.hedef_dil = hedef_dil

    def run(self):
        try:
            self.ilerleme.emit(0, "Meta NLLB modeli indiriliyor. Lütfen bekleyin...")
            from ceviri_modulu import ceviri_modelini_indir
            
            basarili, mesaj = ceviri_modelini_indir()
            self.tamamlandi.emit(basarili, mesaj)
        except Exception as e:
            self.tamamlandi.emit(False, str(e))

class CeviriVeGommeIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal(bool, str)

    def __init__(self, video_yolu, cikti_yolu, hedef_dil_kodu, stil_ayarlari, stt_verisi):
        super().__init__()
        self.video_yolu = video_yolu
        self.cikti_yolu = cikti_yolu
        self.hedef_dil_kodu = hedef_dil_kodu
        self.stil_ayarlari = stil_ayarlari
        self.stt_verisi = stt_verisi

    def run(self):
        try:
            kaynak_dil = self.stt_verisi['dil']
            self.ilerleme.emit(50, f"Çeviri Modeli Hazırlanıyor ({kaynak_dil.upper()} -> {self.hedef_dil_kodu.upper()})...")
            from ceviri_modulu import CeviriVeSrtYoneticisi
            
            # Artık NLLB kullanıyoruz
            yonetici = CeviriVeSrtYoneticisi(kaynak_dil=kaynak_dil, hedef_dil=self.hedef_dil_kodu)
            
            srt_dosyasi = "gecici_altyazi.srt"
            
            def ceviri_ilerleme(yuzde):
                guncel_yuzde = 50 + int(yuzde * 0.3)
                self.ilerleme.emit(guncel_yuzde, f"Altyazılar Çevriliyor... %{yuzde}")
                
            yonetici.altyazi_olustur(self.stt_verisi['segmentler'], srt_dosyasi, ceviri_ilerleme)
            
            self.ilerleme.emit(85, "Altyazı Videoya Gömülüyor (FFmpeg)...")
            
            kutuphane_uzantisi = ".dll" if platform.system() == "Windows" else ".so"
            kutuphane_yolu = os.path.join(os.path.dirname(__file__), f"hardsubbing{kutuphane_uzantisi}")
            
            if os.path.exists(kutuphane_yolu):
                if hasattr(os, 'add_dll_directory'): os.add_dll_directory(os.path.dirname(kutuphane_yolu))
                try: c_modulu = ctypes.CDLL(kutuphane_yolu, winmode=0)
                except TypeError: c_modulu = ctypes.CDLL(kutuphane_yolu)

                altyaziyi_gom = c_modulu.altyaziyi_gom
                altyaziyi_gom.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
                
                video_b = self.video_yolu.encode('utf-8')
                srt_b = srt_dosyasi.encode('utf-8')
                cikti_b = self.cikti_yolu.encode('utf-8')
                stil_b = self.stil_ayarlari.encode('utf-8')
                
                sonuc = altyaziyi_gom(video_b, srt_b, cikti_b, stil_b)
                if sonuc != 0: raise Exception(f"FFmpeg hata kodu: {sonuc}")
            else:
                raise Exception(f"Kütüphane dosyası bulunamadı: {kutuphane_yolu}")
            
            if os.path.exists(srt_dosyasi): os.remove(srt_dosyasi)
            self.tamamlandi.emit(True, self.cikti_yolu)
            
        except Exception as hata:
            self.tamamlandi.emit(False, str(hata))

# =======================================================
# --- ANA ARAYÜZ (UI) ---
# =======================================================

class ModernAltyaziUygulamasi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IronScript")
        self.setMinimumSize(1100, 750)
        self.setAcceptDrops(True)
        self.dosya_yolu = ""
        self.cikti_yolu = ""
        
        self.stilleri_uygula()
        self.arayuzu_hazirla()

        QTimer.singleShot(500, self.kurulum_kontrolu)

    def kurulum_kontrolu(self):
        try:
            from ses_ayristirma import whisper_modeli_kontrol_et
            
            whisper_boyut = whisper_modeli_kontrol_et("medium")
            
            if whisper_boyut > 0:
                mesaj = (f"Uygulamanın çalışabilmesi için ses tanıma modelinin indirilmesi gerekiyor.\n\n"
                         f"İndirilecek Veri: ~{whisper_boyut} MB\n\n"
                         f"Şimdi indirilsin mi?")
                
                cevap = QMessageBox.question(
                    self, "Gerekli Modeller İndirilecek", mesaj,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if cevap == QMessageBox.StandardButton.Yes:
                    self.kurulum_ekranini_baslat(whisper_boyut > 0)
                else:
                    self.durum_mesaji.setText("Kurulum atlandı. Olası hatalar yaşanabilir.")
        except Exception as e:
            print("Kurulum kontrolünde hata:", e)

    def kurulum_ekranini_baslat(self, whisper_lazim):
        self.baslat_butonu.setEnabled(False)
        self.durum_mesaji.setText("Modeller indiriliyor, lütfen bekleyin...")
        self.ilerleme_cubugu.setValue(0)
        
        self.kurulum_isleyici = KurulumIsleyicisi(whisper_lazim)
        self.kurulum_isleyici.ilerleme.connect(self.arayuzu_guncelle)
        self.kurulum_isleyici.tamamlandi.connect(self.kurulum_bitti)
        self.kurulum_isleyici.start()

    def kurulum_bitti(self):
        if "Hata" not in self.durum_mesaji.text():
            QMessageBox.information(self, "Başarılı", "Model başarıyla indirildi.")
            self.durum_mesaji.setText("Hazır")
        self.baslat_butonu.setEnabled(True)
        self.ilerleme_cubugu.setValue(0)
     
    def stilleri_uygula(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0f111a; }
            QGroupBox { color: #82aaff; font-weight: bold; border: 1px solid #1f2233; margin-top: 15px; padding: 10px; border-radius: 5px; }
            QLabel { color: #bfc7d5; }
            QPushButton { background-color: #1f2233; color: #eeffff; border-radius: 4px; padding: 8px; }
            QPushButton:hover { background-color: #292d3e; }
            #suruklemeAlani { border: 2px dashed #444; border-radius: 10px; background-color: #1a1c25; }
            #islemButonu { background-color: #c3e88d; color: #000; font-weight: bold; }
            #iptalButonu { background-color: #ff5370; color: #fff; }
        """)

    def arayuzu_hazirla(self):
        ana_yerlesim = QHBoxLayout()
        sol_panel = QVBoxLayout()

        self.surukleme_etiketi = QLabel("\n\nVideoyu Buraya Sürükle\nveya Dosya Seç")
        self.surukleme_etiketi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.surukleme_etiketi.setObjectName("suruklemeAlani")
        
        sol_panel.addWidget(self.surukleme_etiketi)
        from PyQt6.QtWidgets import QSizePolicy
        self.surukleme_etiketi.setMinimumHeight(120)
        self.surukleme_etiketi.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.dosya_sec_butonu = QPushButton("Video Dosyası Seç")
        self.dosya_sec_butonu.clicked.connect(self.video_dosyasi_sec)
        sol_panel.addWidget(self.dosya_sec_butonu)

        bilgi_grubu = QGroupBox("Dosya Bilgisi")
        self.bilgi_etiketi = QLabel("Çözünürlük: -\nSüre: -\nFormat: -")
        bilgi_yerlesimi = QVBoxLayout()
        bilgi_yerlesimi.addWidget(self.bilgi_etiketi)
        bilgi_grubu.setLayout(bilgi_yerlesimi)
        sol_panel.addWidget(bilgi_grubu)

        stil_grubu = QGroupBox("Altyazı Stili")
        stil_yerlesimi = QVBoxLayout()
        h_yerlesim = QHBoxLayout()
        self.font_kutusu = QComboBox()
        font_ailesi = QFontDatabase.families()
        self.font_kutusu.addItems(font_ailesi)
        if "Arial" in font_ailesi:
            self.font_kutusu.setCurrentText("Arial")
        self.font_kutusu.currentTextChanged.connect(self.altyazi_onizlemesini_guncelle)
        
        self.font_boyutu = QSpinBox()
        self.font_boyutu.setRange(10, 80)
        self.font_boyutu.setValue(24)
        self.font_boyutu.valueChanged.connect(self.altyazi_onizlemesini_guncelle)
        
        h_yerlesim.addWidget(QLabel("Font:"))
        h_yerlesim.addWidget(self.font_kutusu)
        h_yerlesim.addWidget(QLabel("Boyut:"))
        h_yerlesim.addWidget(self.font_boyutu)
        stil_yerlesimi.addLayout(h_yerlesim)

        self.konum_kutusu = QComboBox()
        self.konum_kutusu.addItems(["Alt (Bottom)", "Orta (Middle)"])
        self.konum_kutusu.currentIndexChanged.connect(self.altyazi_onizlemesini_guncelle)
        stil_yerlesimi.addWidget(QLabel("Konum:"))
        stil_yerlesimi.addWidget(self.konum_kutusu)
        stil_grubu.setLayout(stil_yerlesimi)
        sol_panel.addWidget(stil_grubu)

        self.cikti_butonu = QPushButton("Çıktı Klasörü Seç")
        self.cikti_butonu.clicked.connect(self.cikti_klasoru_sec)
        sol_panel.addWidget(self.cikti_butonu)

        sag_panel = QVBoxLayout()
        self.onizleme_kapsayici = QWidget()
        self.onizleme_kapsayici.setFixedSize(640, 360)
        self.onizleme_kapsayici.setStyleSheet("background-color: #000;")
        
        self.video_karesi = QLabel(self.onizleme_kapsayici)
        self.video_karesi.setFixedSize(640, 360)
        
        self.katman_yerlesimi = QVBoxLayout(self.onizleme_kapsayici)
        self.altyazi_katmani = QLabel("Altyazılar Böyle Gözükür")
        self.altyazi_katmani.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.altyazi_katmani.setHidden(True)
        self.katman_yerlesimi.addWidget(self.altyazi_katmani)
        
        sag_panel.addWidget(QLabel("Canlı Ön İzleme Paneli:"))
        sag_panel.addWidget(self.onizleme_kapsayici)

        self.dil_kutusu = QComboBox()
        self.dil_kutusu.addItems(list(DIL_SECENEKLERI.keys()))
        self.dil_kutusu.currentTextChanged.connect(self.altyazi_onizlemesini_guncelle)
        sag_panel.addWidget(QLabel("Hedef Dil:"))
        sag_panel.addWidget(self.dil_kutusu)

        self.ilerleme_cubugu = QProgressBar()
        self.durum_mesaji = QLabel("Hazır")
        sag_panel.addWidget(self.durum_mesaji)
        sag_panel.addWidget(self.ilerleme_cubugu)

        butonlar = QHBoxLayout()
        self.baslat_butonu = QPushButton("İşlemi Başlat")
        self.baslat_butonu.setObjectName("islemButonu")
        self.baslat_butonu.clicked.connect(self.islemi_baslat)
        self.iptal_butonu = QPushButton("İptal")
        self.iptal_butonu.setObjectName("iptalButonu")
        self.iptal_butonu.setEnabled(False)
        self.iptal_butonu.clicked.connect(self.islemi_iptal_et)
        butonlar.addWidget(self.baslat_butonu)
        butonlar.addWidget(self.iptal_butonu)
        sag_panel.addLayout(butonlar)

        ana_yerlesim.addLayout(sol_panel, 1)
        ana_yerlesim.addLayout(sag_panel, 2)
        kapsayici = QWidget()
        kapsayici.setLayout(ana_yerlesim)
        self.setCentralWidget(kapsayici)

    def katman_yerlesimini_temizle(self):
        while self.katman_yerlesimi.count():
            item = self.katman_yerlesimi.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def altyazi_onizlemesini_guncelle(self):
        if not self.dosya_yolu: return
        font_ailesi = self.font_kutusu.currentText()
        boyut = self.font_boyutu.value()
        konum_indeksi = self.konum_kutusu.currentIndex()

        self.katman_yerlesimini_temizle()

        if konum_indeksi == 0:
            self.katman_yerlesimi.addStretch()
            self.katman_yerlesimi.addWidget(self.altyazi_katmani)
        elif konum_indeksi == 1:
            self.katman_yerlesimi.addStretch()
            self.katman_yerlesimi.addWidget(self.altyazi_katmani)
            self.katman_yerlesimi.addStretch()

        secilen_dil = getattr(self, 'dil_kutusu', None)
        if secilen_dil:
            onizleme_metni = ONIZLEME_METINLERI.get(secilen_dil.currentText(), "Altyazılar Böyle Gözükür")
            self.altyazi_katmani.setText(onizleme_metni)

        self.altyazi_katmani.setStyleSheet(f"""
            color: rgba(255, 255, 255, 255);
            font-family: {font_ailesi};
            font-size: {boyut}px;
            background-color: rgba(0, 0, 0, 150);
            padding: 5px;
            border-radius: 4px;
        """)
        self.altyazi_katmani.setHidden(False)

    def video_dosyasi_sec(self):
        dosya_adi, _ = QFileDialog.getOpenFileName(self, "Video Seç", "", "Video Dosyaları (*.mp4 *.mkv *.avi)")
        if dosya_adi:
            self.dosya_yolu = dosya_adi
            self.surukleme_etiketi.setText(f"Dosya: {os.path.basename(self.dosya_yolu)}")
            self.video_onizlemesini_goster(self.dosya_yolu)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        dosyalar = [u.toLocalFile() for u in event.mimeData().urls()]
        if dosyalar:
            self.dosya_yolu = dosyalar[0]
            self.surukleme_etiketi.setText(f"Dosya: {os.path.basename(self.dosya_yolu)}")
            self.video_onizlemesini_goster(self.dosya_yolu)

    def video_onizlemesini_goster(self, yol):
        yakala = cv2.VideoCapture(yol)

        # Dosya bilgilerini çekme ve ekrana yazdırma
        genislik = int(yakala.get(cv2.CAP_PROP_FRAME_WIDTH))
        yukseklik = int(yakala.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = yakala.get(cv2.CAP_PROP_FPS)
        kare_sayisi = int(yakala.get(cv2.CAP_PROP_FRAME_COUNT))
        
        sure_str = "-"
        if fps > 0:
            toplam_saniye = int(kare_sayisi / fps)
            dakika, saniye = divmod(toplam_saniye, 60)
            saat, dakika = divmod(dakika, 60)
            sure_str = f"{saat:02d}:{dakika:02d}:{saniye:02d}"
            
        dosya_formati = os.path.splitext(yol)[1].upper().replace(".", "")
        self.bilgi_etiketi.setText(f"Çözünürlük: {genislik}x{yukseklik}\nSüre: {sure_str}\nFormat: {dosya_formati}")
        
        basarili, kare = yakala.read()
        if basarili:
            kare = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
            h, w, ch = kare.shape
            q_resim = QImage(kare.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.video_karesi.setPixmap(QPixmap.fromImage(q_resim).scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio))
            self.altyazi_onizlemesini_guncelle()
        yakala.release()

    def cikti_klasoru_sec(self):
        self.cikti_yolu = QFileDialog.getExistingDirectory(self, "Klasör Seç")

    def islemi_baslat(self):
        if not self.dosya_yolu or not self.cikti_yolu:
            QMessageBox.warning(self, "Hata", "Lütfen video ve çıktı klasörü seçin!")
            return

        self.baslat_butonu.setEnabled(False)
        self.iptal_butonu.setEnabled(True)
        self.durum_mesaji.setText("Video dili analiz ediliyor...")
        
        self.stt_isleyici = SttIsleyicisi(self.dosya_yolu)
        self.stt_isleyici.ilerleme.connect(self.arayuzu_guncelle)
        self.stt_isleyici.tamamlandi.connect(self.stt_tamamlandi)
        self.stt_isleyici.hata.connect(lambda msg: self.islem_tamamlandi(False, msg))
        self.stt_isleyici.start()

    def stt_tamamlandi(self, stt_verisi):
        self.stt_verisi = stt_verisi
        kaynak_dil = stt_verisi['dil']
        
        secilen_dil_ismi = self.dil_kutusu.currentText()
        hedef_dil = DIL_SECENEKLERI.get(secilen_dil_ismi, "tr")
        self.hedef_dil = hedef_dil 

        from ceviri_modulu import ceviri_modeli_kontrol_et
        gerekli_boyut = ceviri_modeli_kontrol_et()

        if gerekli_boyut > 0:
            cevap = QMessageBox.question(
                self, "Ana Çeviri Modeli Gerekli",
                f"Videonun dili '{kaynak_dil.upper()}' olarak tespit edildi.\n\n"
                f"Tüm dillerde çeviri yapabilmek için Meta NLLB ana modelinin "
                f"(~{gerekli_boyut} MB) indirilmesi gerekiyor.\n\n"
                f"Şimdi indirilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if cevap == QMessageBox.StandardButton.Yes:
                self.model_indirmeyi_baslat(kaynak_dil, hedef_dil)
            else:
                self.arayuzu_sifirla()
        else:
            self.ceviri_ve_gomme_baslat()

    def model_indirmeyi_baslat(self, kaynak_dil, hedef_dil):
        self.durum_mesaji.setText("Meta NLLB Modeli indiriliyor...")
        self.indirme_isleyici = ModelIndirmeIsleyicisi(kaynak_dil, hedef_dil)
        self.indirme_isleyici.ilerleme.connect(self.arayuzu_guncelle)
        self.indirme_isleyici.tamamlandi.connect(self.model_indirme_bitti)
        self.indirme_isleyici.start()

    def model_indirme_bitti(self, basarili, mesaj):
        if basarili:
            self.ceviri_ve_gomme_baslat()
        else:
            QMessageBox.critical(self, "Hata", f"Model indirilemedi: {mesaj}")
            self.arayuzu_sifirla()

    def ceviri_ve_gomme_baslat(self):
        font = self.font_kutusu.currentText()
        boyut = self.font_boyutu.value()
        konum_indeksi = self.konum_kutusu.currentIndex()
        hizalama = 2 if konum_indeksi == 0 else 5
        stil = f"Fontname={font},Fontsize={boyut},Alignment={hizalama},MarginV=10"

        orijinal_isim = os.path.splitext(os.path.basename(self.dosya_yolu))[0]
        cikti_dosyasi = os.path.join(self.cikti_yolu, f"{orijinal_isim}_{self.hedef_dil}_altyazili.mp4")

        self.ceviri_isleyici = CeviriVeGommeIsleyicisi(
            self.dosya_yolu, cikti_dosyasi, self.hedef_dil, stil, self.stt_verisi
        )
        self.ceviri_isleyici.ilerleme.connect(self.arayuzu_guncelle)
        self.ceviri_isleyici.tamamlandi.connect(self.islem_tamamlandi)
        self.ceviri_isleyici.start()

    def arayuzu_sifirla(self):
        self.baslat_butonu.setEnabled(True)
        self.iptal_butonu.setEnabled(False)
        self.ilerleme_cubugu.setValue(0)
        self.durum_mesaji.setText("Hazır")

    def arayuzu_guncelle(self, deger, mesaj):
        self.ilerleme_cubugu.setValue(deger)
        self.durum_mesaji.setText(mesaj)

    def islemi_iptal_et(self):
        if hasattr(self, 'stt_isleyici'): self.stt_isleyici.terminate()
        if hasattr(self, 'indirme_isleyici'): self.indirme_isleyici.terminate()
        if hasattr(self, 'ceviri_isleyici'): self.ceviri_isleyici.terminate()
        self.arayuzu_sifirla()
        self.durum_mesaji.setText("İşlem kullanıcı tarafından iptal edildi.")

    def islem_tamamlandi(self, basarili, mesaj):
        self.arayuzu_sifirla()
        if basarili: QMessageBox.information(self, "Tamamlandı", f"Video hazır:\n{mesaj}")
        else: QMessageBox.critical(self, "Hata", f"Hata: {mesaj}")

if __name__ == "__main__":
    uygulama = QApplication(sys.argv)
    pencere = ModernAltyaziUygulamasi()
    pencere.show()
    sys.exit(uygulama.exec())