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

class KurulumIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal()

    def _init_(self, whisper_indir_lazim, ceviri_indir_lazim):
        super()._init_()
        self.whisper_indir_lazim = whisper_indir_lazim
        self.ceviri_indir_lazim = ceviri_indir_lazim

    def run(self):
        try:
            if self.whisper_indir_lazim:
                self.ilerleme.emit(10, "Yapay Zeka Modeli İndiriliyor (Whisper ~1.5GB)...")
                from ses_ayristirma import whisper_modeli_indir
                whisper_modeli_indir("medium")
            
            if self.ceviri_indir_lazim:
                self.ilerleme.emit(60, "Temel Çeviri Modelleri İndiriliyor (~600MB)...")
                from ceviri_modulu2 import ceviri_modelini_indir
                ceviri_modelini_indir("en", "tr")
                ceviri_modelini_indir("tr", "en")
                
            self.ilerleme.emit(100, "Kurulum Tamamlandı!")
            self.tamamlandi.emit()
        except Exception as e:
            self.ilerleme.emit(0, f"Hata: {str(e)}")
            self.tamamlandi.emit()

class AltyaziIsleyicisi(QThread):
    ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal(bool, str)

    def _init_(self, video_yolu, cikti_yolu, hedef_dil_kodu, stil_ayarlari):
        super()._init_()
        self.video_yolu = video_yolu
        self.cikti_yolu = cikti_yolu
        self.hedef_dil_kodu = hedef_dil_kodu
        self.stil_ayarlari = stil_ayarlari

    def run(self):
        try:
            from ses_ayristirma import videodan_metin_cikar
            def durum_guncelle(yuzde, mesaj): self.ilerleme.emit(yuzde, mesaj)
            
            stt_verisi = videodan_metin_cikar(self.video_yolu, durum_kancasi=durum_guncelle)
            kaynak_dil = stt_verisi['dil']
            
            self.ilerleme.emit(50, f"Çeviri Modeli Hazırlanıyor ({kaynak_dil.upper()} -> {self.hedef_dil_kodu.upper()})...")
            from ceviri_modulu2 import CeviriVeSrtYoneticisi
            yonetici = CeviriVeSrtYoneticisi(kaynak_dil=kaynak_dil, hedef_dil=self.hedef_dil_kodu)
            
            srt_dosyasi = "gecici_altyazi.srt"
            
            def ceviri_ilerleme(yuzde):
                guncel_yuzde = 50 + int(yuzde * 0.3)
                self.ilerleme.emit(guncel_yuzde, f"Altyazılar Çevriliyor... %{yuzde}")
                
            yonetici.altyazi_olustur(stt_verisi['segmentler'], srt_dosyasi, ceviri_ilerleme)
            
            self.ilerleme.emit(85, "Altyazı Videoya Gömülüyor (FFmpeg)...")
            kutuphane_uzantisi = ".dll" if platform.system() == "Windows" else ".so"
            kutuphane_yolu = os.path.join(os.path.dirname(_file_), f"hardsubbing{kutuphane_uzantisi}")
            
            if os.path.exists(kutuphane_yolu):
                # --- DLL YÜKLEME ÇÖZÜMÜ BAŞLANGICI ---
                if hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(os.path.dirname(kutuphane_yolu))
                
                try:
                    c_modulu = ctypes.CDLL(kutuphane_yolu, winmode=0)
                except TypeError:
                    c_modulu = ctypes.CDLL(kutuphane_yolu)
                # --- DLL YÜKLEME ÇÖZÜMÜ BİTİŞİ ---

                altyaziyi_gom = c_modulu.altyaziyi_gom
                altyaziyi_gom.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
                
                # Windows CMD'nin utf-8 yerine kendi karakter setini beklemesi nedeniyle düzeltme:
                kodlama = 'utf-8'

                video_b = self.video_yolu.encode(kodlama)
                srt_b = srt_dosyasi.encode(kodlama)
                cikti_b = self.cikti_yolu.encode(kodlama)
                stil_b = self.stil_ayarlari.encode('utf-8') # Stil genelde ingilizce terimler içerir, utf-8 kalabilir.
                
                sonuc = altyaziyi_gom(video_b, srt_b, cikti_b, stil_b)
                if sonuc != 0: raise Exception(f"FFmpeg hata kodu: {sonuc}")
            else:
                raise Exception(f"Kütüphane dosyası bulunamadı: {kutuphane_yolu}")
            
            if os.path.exists(srt_dosyasi): os.remove(srt_dosyasi)
            self.tamamlandi.emit(True, self.cikti_yolu)
            
        except Exception as hata:
            self.tamamlandi.emit(False, str(hata))

class ModernAltyaziUygulamasi(QMainWindow):
    def _init_(self):
        super()._init_()
        self.setWindowTitle("Offline Auto Sub")
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
            from ceviri_modulu2 import ceviri_modeli_kontrol_et
            
            # Eksik dosyaların boyutlarını hesapla
            whisper_boyut = whisper_modeli_kontrol_et("medium")
            ceviri_boyut_en_tr = ceviri_modeli_kontrol_et("en", "tr")
            ceviri_boyut_tr_en = ceviri_modeli_kontrol_et("tr", "en")
            
            toplam_boyut = whisper_boyut + ceviri_boyut_en_tr + ceviri_boyut_tr_en
            
            if toplam_boyut > 0:
                mesaj = (f"Uygulamanın çevrimdışı ve tam performanslı çalışabilmesi için "
                         f"bazı yapay zeka modelleri eksik.\n\n"
                         f"İndirilecek Toplam Veri: ~{toplam_boyut} MB\n\n"
                         f"Bu işlem internet hızınıza bağlı olarak zaman alabilir. Şimdi indirilsin mi?")
                
                cevap = QMessageBox.question(
                    self, "Gerekli Modeller İndirilecek", mesaj,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if cevap == QMessageBox.StandardButton.Yes:
                    self.whisper_lazim = whisper_boyut > 0
                    self.ceviri_lazim = (ceviri_boyut_en_tr + ceviri_boyut_tr_en) > 0
                    self.kurulum_ekranini_baslat()
                else:
                    self.durum_mesaji.setText("Kurulum atlandı. Olası yavaşlıklar yaşanabilir.")
        except Exception as e:
            print("Kurulum kontrolünde hata:", e)

    def kurulum_ekranini_baslat(self):
        self.baslat_butonu.setEnabled(False)
        self.durum_mesaji.setText("Modeller indiriliyor, lütfen bekleyin...")
        self.ilerleme_cubugu.setValue(0)
        
        self.kurulum_isleyici = KurulumIsleyicisi(self.whisper_lazim, self.ceviri_lazim)
        self.kurulum_isleyici.ilerleme.connect(self.arayuzu_guncelle)
        self.kurulum_isleyici.tamamlandi.connect(self.kurulum_bitti)
        self.kurulum_isleyici.start()

    def kurulum_bitti(self):
        if "Hata" not in self.durum_mesaji.text():
            QMessageBox.information(self, "Başarılı", "Tüm modeller başarıyla indirildi. Uygulama çevrimdışı kullanıma hazır!")
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

        # Sürükle Bırak ve Dosya Seçici Butonu
        self.surukleme_etiketi = QLabel("\n\n🎥 Videoyu Buraya Sürükle\nveya Dosya Seç")
        self.surukleme_etiketi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.surukleme_etiketi.setObjectName("suruklemeAlani")
        self.surukleme_etiketi.setFixedSize(350, 120)
        sol_panel.addWidget(self.surukleme_etiketi)
        
        self.dosya_sec_butonu = QPushButton("🎬 Video Dosyası Seç")
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
        # Sistemdeki TÜM fontları otomatik çek
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
        self.konum_kutusu.addItems(["Alt (Bottom)", "Orta (Middle)", "Üst (Top)"])
        self.konum_kutusu.currentIndexChanged.connect(self.altyazi_onizlemesini_guncelle)
        stil_yerlesimi.addWidget(QLabel("Konum:"))
        stil_yerlesimi.addWidget(self.konum_kutusu)
        stil_grubu.setLayout(stil_yerlesimi)
        sol_panel.addWidget(stil_grubu)

        self.cikti_butonu = QPushButton("📂 Çıktı Klasörü Seç")
        self.cikti_butonu.clicked.connect(self.cikti_klasoru_sec)
        sol_panel.addWidget(self.cikti_butonu)

        sag_panel = QVBoxLayout()
        self.onizleme_kapsayici = QWidget()
        self.onizleme_kapsayici.setFixedSize(640, 360)
        self.onizleme_kapsayici.setStyleSheet("background-color: #000;")
        
        # Önizleme Karesi ve Altyazı Katmanı
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

        if konum_indeksi == 0: # Alt
            self.katman_yerlesimi.addStretch()
            self.katman_yerlesimi.addWidget(self.altyazi_katmani)
        elif konum_indeksi == 1: # Orta
            self.katman_yerlesimi.addStretch()
            self.katman_yerlesimi.addWidget(self.altyazi_katmani)
            self.katman_yerlesimi.addStretch()
        else: # Üst
            self.katman_yerlesimi.addWidget(self.altyazi_katmani)
            self.katman_yerlesimi.addStretch()

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
        basarili, kare = yakala.read()
        if basarili:
            kare = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
            h, w, ch = kare.shape
            q_resim = QImage(kare.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.video_karesi.setPixmap(QPixmap.fromImage(q_resim).scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio))
            self.altyazi_onizlemesini_guncelle() # Önizleme yazısını göster
        yakala.release()

    def cikti_klasoru_sec(self):
        self.cikti_yolu = QFileDialog.getExistingDirectory(self, "Klasör Seç")

    def islemi_baslat(self):
        # 1. Kontrol: Gerekli dosyalar seçilmiş mi?
        if not self.dosya_yolu:
            QMessageBox.warning(self, "Hata", "Lütfen önce bir video dosyası seçin veya sürükleyin!")
            return
        if not self.cikti_yolu:
            QMessageBox.warning(self, "Hata", "Lütfen bir çıktı klasörü seçin!")
            return

        # 2. Hata Yakalama Bloğu: İşlemler başlarken çökmeyi engellemek için
        try:
            # Arayüzden değerleri al
            font = self.font_kutusu.currentText()
            boyut = self.font_boyutu.value()
            
            # Konum dönüşümü (Güvenli liste erişimi)
            konum_indeksi = self.konum_kutusu.currentIndex()
            # 2: at, 5: Orta, 8: Üst (FFmpeg ASS formatına göre)
            hizalama_degerleri = [2, 5, 8]
            
            # Eğer olur da combobox'tan geçersiz bir değer gelirse varsayılan olarak Alt(2) seç
            if 0 <= konum_indeksi < len(hizalama_degerleri):
                hizalama = hizalama_degerleri[konum_indeksi]
            else:
                hizalama = 2 

            # Eğer üst seçiliyse (8), ekranın tepesine yapışmaması için dikey marjin veriyoruz.
            # Eğer alt/orta seçiliyse standart boşluk bırakıyoruz.
            margin_v = 30 if hizalama == 8 else 10
            
            stil = f"Fontname={font},Fontsize={boyut},Alignment={hizalama},MarginV={margin_v}"
            
            #dl seçimi
            secilen_dil = self.dil_kutusu.currentText()
            hedef_dil = DIL_SECENEKLERI.get(secilen_dil, "tr") # Sözlükten bulamazsa varsayılan tr

            # Çıktı dosyasının adını oluştur
            orijinal_isim = os.path.splitext(os.path.basename(self.dosya_yolu))[0]
            cikti_dosyasi = os.path.join(self.cikti_yolu, f"{orijinal_isim}_{hedef_dil}_altyazili.mp4")

            #  ileyiciyi (Thread) Başlat
            self.durum_mesaji.setText("İşlem başlatılıyor...")
            
            self.isleyici = AltyaziIsleyicisi(self.dosya_yolu, cikti_dosyasi, hedef_dil, stil)
            self.isleyici.ilerleme.connect(self.arayuzu_guncelle)
            self.isleyici.tamamlandi.connect(self.islem_tamamlandi)
            self.isleyici.start()
            
            #buton durumlarını güncelle
            self.baslat_butonu.setEnabled(False)
            self.iptal_butonu.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Kritik Hata", f"İşlem başlatılırken beklenmeyen bir hata oluştu:\n{str(e)}")
            self.baslat_butonu.setEnabled(True)
            self.iptal_butonu.setEnabled(False)

    def arayuzu_guncelle(self, deger, mesaj):
        self.ilerleme_cubugu.setValue(deger)
        self.durum_mesaji.setText(mesaj)

    def islemi_iptal_et(self):
        if hasattr(self, 'isleyici'): self.isleyici.terminate()
        self.baslat_butonu.setEnabled(True)
        self.durum_mesaji.setText("İptal edildi.")

    def islem_tamamlandi(self, basarili, mesaj):
        self.baslat_butonu.setEnabled(True)
        self.iptal_butonu.setEnabled(False)
        if basarili: QMessageBox.information(self, "Tamamlandı", f"Video hazır: {mesaj}")
        else: QMessageBox.critical(self, "Hata", f"Hata: {mesaj}")

if _name_ == "_main_":
    uygulama = QApplication(sys.argv)
    pencere = ModernAltyaziUygulamasi()
    pencere.show()
    sys.exit(uygulama.exec())