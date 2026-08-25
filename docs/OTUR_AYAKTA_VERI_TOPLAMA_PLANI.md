# Otur / Ayakta Ayrımı — Veri Toplama ve Doğrulama Planı

**Tarih:** 2026-08-25
**Bağlam:** `PROJE_DURUM_VE_KARARLAR.md` Bölüm 0 ("EN KRİTİK BULGU") ve Bölüm 5.1
**Hedef:** Final senaryoda kişi hem yürüyecek, hem duracak, hem oturacak.
Sistem üçünü de doğru ayırt etmeli.

---

## 1. Nereden başlıyoruz — ölçülmüş gerçekler

### 1.1 Otur/ayakta neden çöktü (2026-08-25'te sayısallaştırıldı)

`20260824_durus_konum_degisken` verisi yeniden analiz edildi. Sinyal
seviyesinin duruşa göre değişimi ile konuma göre değişimi karşılaştırıldı:

| Kart | Ayakta↔otur farkı | Aynı duruşun konumdan konuma yayılımı | Oran |
|---|---|---|---|
| STA-85b0 | 0.30 | **2.68** | 9.0x |
| STA-9d9c | 0.40 | **0.88** | 2.2x |

**Okunuşu:** Aradığımız sinyal (duruş farkı), aramadığımız gürültünün
(konum değişimi) 2-9 katı altında. Model bunu bulamaz — %40-46 sonucu
tam olarak bunun beklenen çıktısı. **Bu bir algoritma sorunu değil,
geometri sorunu.**

> ⚠️ Daha da kötüsü: o testte doğrulama faz-bazlı LeaveOneGroupOut'du ve
> aynı konumdaki fazlar hem eğitimde hem testte bulunabiliyordu (yani
> doğruluğu ŞİŞİREN bir kaçak vardı). Şişirilmiş haliyle bile şans
> seviyesinin altında kaldı.

### 1.2 Denenip ELENEN fikir: relatif/adım yöntemi (2026-08-25)

"Mutlak seviyeyi değil, bir önceki duruşa göre değişimin YÖNÜNÜ ölç"
hipotezi test edildi. `otur→ayakta` geçişlerinde işaretler:

| Kart | İşaretler | Yorum |
|---|---|---|
| STA-85b0 | `- - +` | tutarsız |
| STA-9d9c | `+ + +` | tutarlı görünüyor ama n=3'te rastgele çıkma ihtimali %12.5 |

**İki kart birbiriyle çelişiyor.** Bu, daha önce çöken "kayma" ölçüsüyle
(1.22x vs 0.66x) birebir aynı desen: gürültü, fizik değil. **Bu fikir
kapandı, tekrar denenmeyecek.**

### 1.3 ✅ Çalışan şey: geçiş ANININ tespiti

Her oturma/kalkma olayı, öncesindeki sessizliğe göre hareket patlaması üretti:

| Geçiş | STA-85b0 | STA-9d9c |
|---|---|---|
| otur→ayakta #1 | 2.45x | 1.61x |
| otur→ayakta #2 | 2.77x | 1.25x |
| otur→ayakta #3 | 1.84x | 1.41x |

**6/6 — iki kartta da, üç turda da.** Sistem "bir geçiş oldu"yu güvenilir
görüyor; göremediği "hangi yöne" olduğu.

---

## 2. Hipotez ve tek gerçek çözüm: KART YÜKSEKLİĞİ

`PROJE_DURUM_VE_KARARLAR.md` Bölüm 5.1 Sonuç 3 sebebi zaten yazmıştı:

> "Kartlar masa seviyesinde ve kişi tam aralarında dururken, gövde her iki
> duruşta da doğrudan hattı aynı şekilde kesiyor."

Masa hizasında (~75 cm) hem otururken hem ayaktayken gövde hattın üstünde →
ikisi de benzer şekilde engelliyor → fark yok.

**Çözüm:** Hattı, oturan kişinin BAŞININ ÜSTÜNE ama ayakta duran kişinin
GÖVDESİNİN İÇİNE denk getirmek.

```
   ayakta:  ●  baş  172 cm
            |
   ═════════╪═════════  ← KART HATTI ~154 cm : ayakta boyun/baş KESER
            |                                   otururken hat TEMİZ
   oturan:  ●  baş  136 cm
            |
   ─────────┴─────────  yer
```

Bu, modelin ezberlemesine gerek bırakmayan, **fiziksel olarak zorunlu**
bir fark yaratır. Doküman bunu "önerilen çözüm, henüz denenmedi (uygun yer
yoktu)" diye işaretlemişti — **projedeki en yüksek getirili, hiç denenmemiş
değişiklik budur.**

### 2.1 Doğru yükseklik teoriden hesaplanamaz

2.4 GHz'de, 5 m aralıklı iki kart arasında birinci Fresnel bölgesinin
yarıçapı orta noktada ≈ **40 cm**. Yani hattın ±40 cm'i "duyarlı bölge".
Oturan başın tepesi ile ayakta omuz arası tipik olarak sadece ~8 cm —
bu payın çok içinde. Bu yüzden yüksekliği **hesaplayarak değil, ÖLÇEREK**
seçeceğiz.

### 2.2 Kendi ölçünü al (planı kişiselleştirir)

Kayda başlamadan önce iki ölçü al:

| Ölçü | Nasıl |
|---|---|
| **H_otur** | Kullanacağın sandalyeye otur, yerden başının tepesine kadar ölç |
| **H_ayakta** | Ayakta dur, yerden başının tepesine kadar ölç |

Denenecek üç yükseklik:
- **A = H_otur + 15 cm** (agresif, ayakta gövde iyi kesiliyor)
- **B = (H_otur + H_ayakta) / 2** (orta nokta — en olası aday)
- **C = H_ayakta − 5 cm** (temkinli, otururken hat kesinlikle temiz)

Tipik değerlerle: H_otur≈136, H_ayakta≈172 → A=151, B=154, C=167.

---

## 3. ⛔ KARAR KAPISI — buraya dikkat

Faz 0 (aşağıda) **3 yükseklikte de ayrım gücü d < 1.0** verirse:

> **DUR. Faz 1'e geçme. 2 saat veri toplamayı yakma.**

Bu durumda fizik "hayır" diyor demektir ve Plan B'ye geçilir (Bölüm 9).
Bu kapı bilerek konuldu — bu proje daha önce iki kez, işe yaramayan bir
yöne saatler harcadı.

**Devam kriteri:** en az bir yükseklikte **d ≥ 1.5** (tercihen ≥ 2.0).

---

## 4. FAZ 0 — Geometri taraması (~15 dk)

**Amaç:** Hangi yükseklik? Kanıt üretmek değil, yükseklikleri birbiriyle
kıyaslamak.

### Kurulum
- İki kart **aynı yükseklikte**, odanın iki ucunda, aralarında 4-5 m
- Aradaki hat, kişinin duracağı noktadan geçmeli
- **Powerbank kullan** — 5V adaptör + priz, yüksekliği ayarlamayı zorlaştırır.
  Powerbank'le kartı istediğin yere bantlayabilirsin (dolap üstü, kapı
  pervazı, kitaplık rafı, duvara bant, süpürge sapı).
- Kartların **anteni serbest** olsun (metal yüzeye yapışık olmasın)

### Çalıştırma

Her yükseklik için (~2 dk):

```bash
cd analysis && source venv/bin/activate
python3 probe_geometry.py --height 151
```

Sonra kartları yükselt/alçalt, tekrarla:

```bash
python3 probe_geometry.py --height 154
python3 probe_geometry.py --height 167
```

**Bu testte kişi TEK bir noktada durur** (kartların tam ortasında, hattın
üstünde). Komut gelince hemen otur/kalk, sonra sabit kal.

### Okunuşu

Script tek bir sayı basar — **ayrım gücü d**:

| d | Anlamı |
|---|---|
| < 1.0 | Fark gürültünün içinde → bu yükseklik işe yaramaz |
| 1.0 – 2.0 | Sınırda, umut var |
| > 2.0 | Fark gürültüden büyük → sınıflandırma mümkün ✓ |

**Kıyas noktası (dünkü masa hizası):** d ≈ 0.2 (85b0) ve 0.9 (9d9c).
Yenmesi gereken sayı bu.

> ⚠️ Script'in bastığı "LOGO doğruluk" satırına **güvenme**. Kişi sabit
> noktada durduğu için yüksek çıkar ve yanıltıcıdır — projenin en pahalı
> dersi buydu. Sadece `d`'yi ve yükseklikler arası SIRALAMAYI kullan.

---

## 5. FAZ 1 — Ana eğitim seti (~35 dk)

Faz 0 kapıyı geçtiyse. Kartlar **kazanan yükseklikte sabitlenir ve artık
hiç oynatılmaz** (yükseklik değişirse tüm veri geçersiz olur).

### 5.1 Konum tasarımı — "algılama koridoru"nu haritalar

Yöntem hat engellemesine dayandığı için **sadece hattın yakınında çalışır.**
Bu bir kusur değil, ölçülmesi ve raporlanması gereken bir **spesifikasyon.**
Konumlar bunu haritalayacak şekilde seçildi:

| # | Konum | Beklenti |
|---|---|---|
| P1 | Hat üstü, tam orta | En güçlü |
| P2 | Hat üstü, A kartına 1/4 mesafede | Güçlü |
| P3 | Hat üstü, B kartına 1/4 mesafede | Güçlü |
| P4 | Hattan **0.5 m** yanda, orta hizada | Fresnel bölgesinin kenarı — sınırda |
| P5 | Hattan **1.5 m** yanda, orta hizada | Bölge dışı — bozulması BEKLENİYOR |

P4 ve P5'in kötü çıkması **başarısızlık değil**; sistemin kapsama alanını
sayıyla belgeler ("kişi hattın ±X m'sindeyken çalışır").

### 5.2 Kayıt sırası — zaman kaymasını konumdan ayırmak için

Bölüm 3.7'de ortam kayması 2 saatte sınıf farkının **5 katına** çıkmıştı.
Eğer P1'i iki kez üst üste, sonra P2'yi iki kez... çekersek **konum ile
zaman birbirine karışır** ve model hangisini öğrendiğini bilemeyiz.

**Bu yüzden tur tur gidilir:**

```
1. tur:  P1 → P2 → P3 → P4 → P5
2. tur:  P1 → P2 → P3 → P4 → P5
```

### 5.3 Her kayıt

- **8 faz × 12 sn = 96 sn** (otur/ayakta dönüşümlü, 4 otur + 4 ayakta)
- Sandalye her konuma taşınır; kişi sandalyeden kalkar, yerinde durur
  (sandalye her iki duruşta da orada — tutarlı)
- Toplam: 5 konum × 2 tur = **10 kayıt ≈ 16 dk kayıt + taşıma süresi**

```bash
python3 guided_capture_udp.py --phases 8 --phase-sec 12 \
    --position P1 --height 154 --session tur1 \
    --output ../data/posture_v2/tur1_P1
```

> `--position`, `--height`, `--session` argümanları **henüz yok** —
> eklenmesi gerekiyor (Bölüm 8). Konum etiketi olmadan doğru doğrulama
> yapılamaz.

### 5.4 Boş oda taban kaydı (60 sn, bir kez)

```bash
python3 csi_udp_server.py --duration 60 --output ../data/posture_v2/bos_oda
```

Odadan çık. Bu kayıt gürültü tabanını verir ve "odada kimse yok" durumunu
tanımayı mümkün kılar. Ucuz, değerli.

### 5.5 Toplanacak veri hacmi

10 kayıt × 8 faz = 80 faz (40 otur, 40 ayakta).
Faz başına kullanılabilir ~8 sn → 2 sn'lik kayan pencerelerle ~7 pencere.
**≈ 280 pencere / sınıf.** Fazlasıyla yeterli.

---

## 6. FAZ 2 — Taze oturum testi (~10 dk) — ASIL SINAV

Bölüm 3.7'nin dersi: aynı oturum içindeki doğrulama **yanıltıcıdır**.
Model 2 saat sonra tamamen çökmüştü.

**Protokol:**
1. Faz 1 bitince **en az 30 dk ara ver**
2. **İki kartın da gücünü kes ve tekrar ver** (reset — gerçek kullanımda olacak şey)
3. Sunucuyu yeniden başlat
4. 3 kayıt al: **P1, P3** (görülmüş konumlar) + **P6 = yepyeni bir konum**

Bu üç şeyi aynı anda test eder: oturumlar arası kayma, reset dayanıklılığı,
görülmemiş konuma genelleme.

---

## 7. FAZ 3 — Gerçekçi final senaryosu (~10 dk)

Kullanıcının tarif ettiği asıl kullanım: *"hem yürüyüp hem durup hem oturma
yapacağım"*.

### 7.1 Yürüme ile geçişi ayırmak — kullanıcının asıl isteği

> *"sinyalin sadece belli bir yerde bozulduğunu görürse yürümediğimi anlamalı"*

Bunun fiziksel karşılığı **SÜRE**:

| Olay | Hareket enerjisi deseni |
|---|---|
| Oturma/kalkma | 1-2 sn'lik **patlama**, sonra sessizlik |
| Yürüme | 5+ sn **sürekli** yüksek |

Dünkü veri bunu destekliyor (geçişler 1.25-2.77x ve KISA). Gereken:
`N` eşiğini ölçmek — "kaç saniye sürekli yüksek kalırsa yürüme sayılır".

### 7.2 Kayıt

Düzensiz, gerçekçi bir dizi (kullanıcı komutu duyunca yapar):

```bash
python3 guided_capture_udp.py \
  --cues "otur,kalk,yürü,dur,otur,kalk,yürü,otur,yürü,dur,kalk,otur" \
  --phase-sec 10 --position karisik --height 154 --session final \
  --output ../data/posture_v2/final_senaryo
```

Bu kayıt **eğitime girmez** — sadece uçtan uca test ve demo provası.

---

## 8. Gereken kod değişiklikleri

| # | Dosya | Değişiklik | Neden |
|---|---|---|---|
| 1 | `guided_capture_udp.py` | `--position`, `--height`, `--session` → JSON'a yaz | Konum etiketi olmadan doğru doğrulama İMKANSIZ |
| 2 | **yeni** `evaluate_posture_lopo.py` | **Leave-One-Position-Out**, çok dosyalı | Faz-bazlı LOGO konum kaçağı yapıyor (Bölüm 1.1) |
| 3 | `live_server_udp.py` | Histerezis + süre kuralı | İbre kararsızlığı + yürüme/geçiş ayrımı |
| 4 | `live_server_udp.py` | Duruş katmanı | Faz 1-2 başarılı olursa |

### 8.1 En önemlisi: doğrulama Leave-One-**Position**-Out olmalı

Mevcut `evaluate_udp_session.py` grupları **fazlara** göre ayırıyor. Aynı
konumdaki başka bir faz eğitimde kalabildiği için model konumu ezberleyip
test fazında onu kullanabiliyor → **doğruluk şişiyor.**

Yeni kural: **bir konumun TÜM fazları ya eğitimde ya testtedir.**
Rapora yazılacak sayı budur.

### 8.2 İbre kararsızlığı (kullanıcının şikayeti)

Şu an tek eşik + 3 oy çoğunluğu var; eşiğin etrafında değer titreyince
ekran zıplıyor. Üç düzeltme:

- **Histerezis:** girişte yüksek eşik (taban×1.4), çıkışta düşük eşik
  (taban×1.1). Aradaki bölgede mevcut karar korunur.
- **EMA yumuşatma:** enerjiye üstel hareketli ortalama (α≈0.3)
- **Süre kuralı:** "yürüyor" demek için N saniye sürekli yüksek kalmalı
  (7.1'deki ölçümden gelecek)

Bu üçü hem ekranı sakinleştirir hem de geçiş/yürüme ayrımını çözer —
aynı taşla iki kuş.

---

## 9. Eski veri kullanılabilir mi? — DEĞERLENDİRME

Kullanıcının sorusu: dünkü eğitim setini yeni veriyle birleştirelim mi?

### ❌ HAYIR — eğitim setine KATILMAMALI

**Gerekçe:** Dünkü veri **masa hizası** geometrisiyle toplandı, yeni veri
**~154 cm** ile toplanacak. İkisini tek sete koyarsan model duruşu değil
**hangi geometride kaydedildiğini** öğrenir. Bu, projeyi daha önce iki kez
yakan tuzağın birebir aynısı:

1. Sabit konumda toplanan veri → %70-74 "başarı" → konum ezberiymiş
2. Örnekleme hızı değişince format değişti → eski modeller uyumsuz kaldı
   (`data/archive_lowrate/`)

Üstelik dünkü veride ayrım gücü **d ≈ 0.2 / 0.9** — yani içinde aradığımız
sinyal zaten yok denecek kadar az. Temiz veriyi kirletir.

### ✅ EVET — şu üç amaçla kullanılacak

1. **Kıyas ölçüsü (benchmark):** Yeni geometri, d ≈ 0.2/0.9'u yenmek
   zorunda. Başarının tanımı bu sayı.
2. **Negatif kontrol:** "Yöntem eski veride çalışmıyor, yenisinde çalışıyor"
   → farkın geometriden geldiğinin kanıtı. Rapor için güçlü bir argüman.
3. **Hareket/yürüme verisi hâlâ geçerli:** `20260824_hareket_teshis`
   (%85-87) geometriye bu kadar bağımlı değil, silinmeyecek.

### Dosya düzeni

```
data/udp_session/     ← DOKUNMA. Eski geometri. Kıyas ve hareket verisi.
data/geometry_probe/  ← YENİ. Faz 0 yükseklik taramaları.
data/posture_v2/      ← YENİ. Faz 1-2-3. Sadece kazanan geometri.
```

Ayrı klasör şart: `posture_v2/` içindeki her kayıt aynı geometriye ait
olmalı, tek bir set olarak eğitilebilmeli.

---

## 10. Zaman planı

| Faz | Süre | Çıktı |
|---|---|---|
| Ölçü alma (H_otur, H_ayakta) | 2 dk | Denenecek 3 yükseklik |
| **Faz 0** — geometri taraması | 15 dk | Kazanan yükseklik + d |
| **⛔ KARAR KAPISI** | — | d ≥ 1.5 yoksa Plan B |
| **Faz 1** — ana set (10 kayıt) | 35 dk | `posture_v2/` eğitim seti |
| Ara (zorunlu) | 30+ dk | — |
| **Faz 2** — taze oturum | 10 dk | Gerçek genelleme sayısı |
| **Faz 3** — final senaryo | 10 dk | Uçtan uca test + demo provası |

**Toplam ≈ 1.5 saat aktif çalışma.**

---

## 11. Plan B — Faz 0 kapıyı geçemezse

Bu ihtimal gerçek ve buna hazırlıklı olmak lazım. O durumda dürüst teslim
edilebilir çıktı:

1. **Hareket / hareketsiz tespiti** — %85-87, üç geometride doğrulanmış ✅
2. **Nefes hızı** — frekans tabanlı, ortamdan bağımsız ✅
3. **Geçiş sayacı + durum makinesi:** Geçiş ANI %100 yakalanıyor (Bölüm 1.3).
   Başlangıç durumu kalibrasyonla verilirse ("şimdi otur" → sistem işaretler),
   sonraki her geçiş durumu çevirir. **Kısıt:** tek bir kaçan geçiş, sonraki
   tüm durumları bozar — bu açıkça belirtilmeli, gizlenmemeli.
4. **Otur/ayakta:** donanım sınırı olarak raporlanır (1 anten, 2.4 GHz).
   Bölüm 4'teki tablo bunu zaten öngörüyordu.

Bu, "çalışmıyor" değil, **sınırları ölçülmüş ve dürüstçe raporlanmış bir
sistem** demektir — ki bu da geçerli bir mühendislik çıktısıdır.

---

## 12. Kontrol listesi (kayda başlamadan)

- [ ] `ipconfig getifaddr en0` → laptop kartlarla aynı `172.20.10.x` ağında
- [ ] `python3 csi_udp_server.py --duration 15` → iki kart da görünüyor, hız > 100 Hz
- [ ] İki kart **aynı yükseklikte**, anten serbest, powerbank'te
- [ ] Odada başka hareketli kaynak yok (**vantilatör kapalı** — Bölüm 6 tuzağı)
- [ ] Sandalye hazır, konumlar (P1-P5) yere işaretlendi (bant/kağıt)
- [ ] H_otur ve H_ayakta ölçüldü
- [ ] Kartlar Faz 1 boyunca **hiç oynatılmayacak** — kararlaştırıldı
