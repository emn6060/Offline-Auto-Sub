#include <iostream>
#include <string>
#include <cstdlib>

extern "C" {
    __declspec(dllexport) int altyaziyi_gom(const char* video_yolu, const char* srt_yolu, const char* cikti_yolu, const char* stil_ayarlari) { 
        std::string guvenli_srt_yolu = srt_yolu;    
        for (char& c : guvenli_srt_yolu) {
            if (c == '\\') c = '/';
        }

        std::string kacisli_srt_yolu = "";
        for (char c : guvenli_srt_yolu) {
            if (c == ':') kacisli_srt_yolu += "\\:"; // FFmpeg için iki noktadan kaçış
            else kacisli_srt_yolu += c;
        }
        
        std::string stil = stil_ayarlari;
        std::cout << "Altyazi videoya gomuluyor...\n";
        
        // Komut doğrudan C:\ffmpeg\ffmpeg.exe olarak güncellendi
        std::string komut = "C:\\ffmpeg\\ffmpeg.exe -y -i \"" + std::string(video_yolu) + 
                            "\" -vf \"subtitles='" + kacisli_srt_yolu + "':force_style='" + stil + "'\" -c:a copy \"" + 
                            std::string(cikti_yolu) + "\"";
    
        int sonuc = std::system(komut.c_str()); 
        
        if (sonuc == 0) {
            std::cout << "Video basariyla olusturuldu!\n";
        } else {
            std::cerr << "Hata! FFmpeg cikis kodu: " << sonuc << "\n";
        }
        return sonuc;
    }
}