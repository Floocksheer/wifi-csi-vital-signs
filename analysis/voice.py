"""Sesli komut - veri toplarken kullanıcıyı yönlendirmek için.

NEDEN AYRI DOSYA: Bu fonksiyon eskiden guided_capture.py'nin (seri port
dönemi) içindeydi ve modern UDP araçları sırf bunun için o dosyayı import
ediyordu; o da esp_port.py'yi çekiyordu. Yani eski mimarinin tamamı 4 satır
yüzünden canlı kalıyordu. Buraya alındı (2026-08-25).

NEDEN KRONOMETRE DEĞİL SES: Projede etiketli veri ilk kez kullanıcının kendi
kronometresiyle toplanmıştı ve etiketler veriyle hizalanmadı - kayıt
kullanılamaz hale geldi (bkz. PROJE_DURUM_VE_KARARLAR.md Bölüm 5.1).
Komut anı bilgisayarın saatiyle işaretlenince senkron hatası fiziksel
olarak imkansız oluyor.
"""
import subprocess


def speak(text):
    """Bloklamadan konuş - konuşma süresi faz zamanlamasını kaydırmasın."""
    subprocess.Popen(["say", "-v", "Yelda", text],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
