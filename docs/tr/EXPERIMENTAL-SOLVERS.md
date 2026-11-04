# Deneysel çözücüler

Varsayılan çözücü openEMS'tir. **Elmer FEM — Deneysel özmodlar**, **Elmer FEM · Deneysel anten**, sabit **EMerge** WR-90 dalga kılavuzu fikstürü, **EMerge · Deneysel anten** (sınırlı Tasarım alt kümesi) ve **EMerge FEM · Deneysel düzlemsel iki port** (hairpin sınıfı mikroşerit), geometri ve sonuç desteği daha sınırlı, isteğe bağlı araştırma yollarıdır. Arka ucun kurulması veya bir çalıştırmanın tamamlanması, tasarımınızın sayısal doğruluğunu kanıtlamaz.

## Masaüstü uygulamasında kurulum

**Simülasyon › Deneysel çözücüler** komutunu veya Simülasyon çalıştır penceresindeki **Elmer kurulumu ve geçmiş** bağlantısını açın. Bir arka uç seçip çalıştırmayı göndermeden önce kullanılabilirliğini denetleyin.

Windows'ta **Elmer'i kur**, siz istediğinizde Fairbeam'in sabitlediği taşınabilir paketi indirir. Paket doğrulanır ve openEMS çalışma ortamından ayrı olarak uygulamanın veri klasörüne kaydedilir. Sistem genelinde kurulmaz. Yönetilen kopyayı kullanmak için yolu boş bırakın. Girdiğiniz klasör, `FAIRBEAM_ELMER_ROOT` veya `PATH` üzerindeki Elmer önceliklidir.

macOS ve Linux'ta Elmer'i kendiniz kurun. `bin/ElmerSolver` ve `bin/ElmerGrid` içeren kurulumu veya ikili dosya klasörünü seçin. Kullanılabilirlik denetimi yürütülebilir dosyaları bulur; fiziksel modelin veya tüm yerel bağımlılıkların yeterliliğini doğrulamaz. Hiçbir arka uç otomatik kurulmaz.

Kurulu uygulama `No module named fairbeam_elmer` bildirirse Fairbeam'i güncelleyin veya onarın. Yalnızca Elmer ikili dosyalarını kurmak, Fairbeam'in Python bağdaştırıcısını sağlamaz. Kaynak üzerinde çalışan katkıcılar ayrı [araştırma kurulumu ve kanıtları](RESEARCH-SOLVERS.md) kullanmalıdır.

## EMerge dalga kılavuzu fikstürü

Yalnızca sabit WR-90 hava dolu dalga kılavuzu fikstürü için Simülasyon → Deneysel çözücüler içinde **EMerge** arka ucunu seçin. A düzeyi mevcut tasarımı çevirmez. `coarse` veya `fine` çözünürlüğü seçip gönderin; sonuçlar Araştırma panelinde analitik düz dalga kılavuzu referansına göre denetlenir.

Windows'ta **EMerge'i kur**, PyPI'dan hash kilitli `emerge==3.0.0b12` ile sabitlenmiş bir Python 3.13 sanal ortamı oluşturur. Araştırma paneli, Kur düğmesinden önce EMerge'in GPL-2.0-or-later bildirimini ve Intel MKL'nin özel lisansını gösterir. Kilitli indirme kümesi yaklaşık 399 MiB'tır (418619020 bayt, PyPI tekerlek boyutları 2026-11-04). `3.0.0b12` için 2026-11-04'te ölçülen yönetilen kurulum 1421133962 bayt (1355,3 MiB) ve 80,9 s sürdü. Yönetilen kopyayı kullanmak için yolu boş bırakın. Girdiğiniz klasör veya `FAIRBEAM_EMERGE_PYTHON` önceliklidir. Sistem genelinde hiçbir şey kurulmaz ve EMerge Fairbeam kurucusuna gömülmez.

macOS ve Linux'ta yönetilen kurucu yoktur. `emerge==3.0.0b12` içeren kendi Python 3.10–3.13 ortamınızı oluşturun, ardından yol alanına o ortamın klasörünü (veya Python yürütülebilir dosyasını) girin ya da `FAIRBEAM_EMERGE_PYTHON` ayarlayın.

Fikstür tanımı, kabul ölçütleri ve kaydedilmiş yerel gözlemler için [EMerge deneyine](EMERGE-EXPERIMENT.md) bakın.

## EMerge · Deneysel anten

Çalıştırma sunucusu `emerge` ≥ 2 bildiriyorsa **Simülasyon çalıştır** penceresinde Elmer seçeneklerinden sonra **EMerge · Deneysel anten** görünür. Elmer'in uyarılmış anten yolundakiyle aynı sınırlı sınıfı kabul eder: eksenlere paralel dielektrik kutular, PEC levhalar, tek Ayrık port, açıkça kabul edilen sonlu besleme genişliği, isteğe bağlı `approximate_metals` ve kayıp varsa sabit `tan_d`. Ek portlar, dirençler, toplu elemanlar, dönüşümler, kesiler, boşluklar, örtüşmeler ve kutu olmayan ilkeller reddedilir. Dış sınır: dolgulu hava kutusunun soğurucu yüzleri (PML değil). Uzak alan ve kazanç belgesi yoktur; durum `results_exported`'tur.

Çözünürlükler `f_max`teki dalga boyu kesirleridir: `coarse` = 0,25, `fine` = 0,15. İşçi zaman aşımı 1800 saniyedir; ucuz bir hacim vekili aşırı büyük alanları başlatmadan reddeder. S11 ve Zin, openEMS'in yerine geçmeden paylaşılan Sonuçlar görünümünde yer alır.

Yerleşik Patch şablonu için 2026-11-04 yerel çalıştırmalarında EMerge S11 minimumu 2,30 GHz'te kaydedildi (2–3 GHz, 11 nokta; coarse −7,427 dB, fine −6,349 dB). Aynı şablonun Fairbeam openEMS çalıştırmasında S11 minimumu 2,453981250 GHz (−45,574 dB) idi. EMerge Tasarım yolu bu openEMS sonucuyla uyum iddia etmez. Ayrıntılar: [EMerge deneyi](EMERGE-EXPERIMENT.md).

## EMerge FEM · Deneysel düzlemsel iki port

Çalıştırma sunucusu `emerge` ≥ 3 bildiriyorsa **Simülasyon çalıştır** penceresinde **EMerge · Deneysel anten** seçeneğinden sonra **EMerge FEM · Deneysel düzlemsel iki port** görünür. Tek katmanlı mikroşerit iki port sınıfını kabul eder: bir alttaş kutusu, altta toprak, alttaş üstünde z-normal bakır çokgenler (veya z-düz kutular), tahta kenarında tam iki mikroşerit port. Çok katman, via, CPW, diğer port türleri veya sayıları, dirençler, dönüşümler, kesiler, boşluklar ve başka yüksekliklerde metal reddedilir. Her mikroşerit port, yalnızca bu çalıştırma için tahta kenarında şeritten toprağa toplu terminale dönüşür (`accept_lumped_terminals`); besleme ve ölçüm kaymaları kullanılmaz. Sonlu bakır için `approximate_metals` (PEC levhalar) gerekir. Muhafaza `shielded` (kapalı PEC kutu) veya `open` (`padding_mm` ile soğurucu yanlar ve üst) olur. Uzak alan ve kazanç belgesi yoktur; durum `results_exported`'tur. Paylaşılan Sonuçlar, openEMS'in yerine geçmeden eksiksiz 2 × 2 S matrisini gösterir.

Çözünürlükler `f_max`teki dalga boyu kesirleridir: `coarse` = 0,25, `fine` = 0,15. İşçi zaman aşımı 3600 saniyedir; tetrahedra vekili 400000 üzerini başlatmadan reddeder. Nokta sayısı 3–41.

Hairpin test fikstürü için 2026-11-04 yerel EMerge 2.8.9 çalıştırmalarında (15 nokta, 0,75–1,25 GHz, levha bakır) en iyi |S21| **1,071429 GHz**'te kaydedildi (shielded coarse ve fine −0,63 dB; open coarse −0,51 dB). Bu ızgarada coarse→fine tepe kayması 0 idi. Aynı fikstürün Fairbeam openEMS GPU çalıştırması (varsayılan tek port uyarımı) fiziksel olmayan |S21| > 1 bildirdi; bu yüzden B2 düzeyi o openEMS yoluyla S parametresi uyumu iddia etmez. Ayrıntılar: [EMerge deneyi](EMERGE-EXPERIMENT.md).

## Mevcut tasarımın özmodları

Tasarımı kaydedin, **Simülasyon çalıştır** penceresini açın ve **Elmer FEM — Deneysel özmodlar** seçeneğini seçin. Milimetre cinsinden çevreleyen kutu sınırlarını, en büyük hücre boyutunu ve hedef frekansı gözden geçirin. Kapalı PEC kutusunu açıkça kabul edin: altı yüzün tamamı iletken duvardır; açık ışınım sınırı değildir.

Bu yol, sabit, pozitif, kayıpsız izotropik dielektrik özelliklerine veya PEC malzemeye sahip eksenlere paralel kutu hacimlerini kabul eder. Örtüşmeler, portlar, toplu elemanlar, levhalar, eğriler, dönüşümler, kesiler, kayıp ve dispersiyon reddedilir. Çözücü hedef frekansa yakın iki mod arar; bunların en düşük modlar olması gerekmez.

Sınırlandırılmış çözüm en fazla 4.000 eleman ve 10.000 düğüm, bir CPU iş parçacığı ve 120 saniye yerel yürütme kullanır. Sonuçlar özfrekanslar ile saklanan alanlar/günlüklerdir; anten S parametreleri, kazanç veya ışınım örüntüsü değildir. Tamamlanma `results_validated` olarak değil, `results_exported` olarak kaydedilir.

## Uyarılmış anten deneyleri

Eksenlere paralel dielektrik kutular, PEC levhalar ve tek ideal çizgi ayrık porttan oluşan tasarım için **Elmer FEM · Deneysel anten** seçeneğini kullanın. Sonlu dikdörtgen FEM terminal genişliğini kabul edin; hava payını, mesh boyutunu ve frekans örneklerini gözden geçirin. Terminalin iki ucu da PEC levhalara temas etmelidir. Bu ayarlar FEM anlık kopyasına aittir; özgün tasarım ve openEMS ayarları değişmez.

Açık bölge PML değil, birinci dereceden soğurucu sınırlar kullanır. Sonlu iletkenlikli metaller FEM anlık kopyasında PEC ile yaklaşıklanır; iletken kaybı dışarıda bırakılır ve etkilenen malzemeler kaydedilir. Eğriler, dönüşümler, kesiler, ek toplu elemanlar ve birden fazla port reddedilir.

Sınırlar 10.000 hücre, istenen uzak alan frekansına ek olarak 3–21 tarama örneği, bir CPU iş parçacığı ve frekans başına 180 saniyedir. Sonuçlar karmaşık S11, normalize 3B örüntü ve yönlülük kesitlerini içerir; kazanç ve verim verilmez. Dışa aktarılan sonuçlar yakınsama belgesi değildir. Yeni bir modeli yorumlamadan önce [kayıtlı deneyleri ve kalan yeterlilik çalışmalarını](RESEARCH-SOLVERS.md) inceleyin.

## Kuyruk, sonuçlar ve iptal

Deneysel çalıştırmalar ortak seri kuyruğu kullanır. Hataları, ham girdileri, ayarları, mesh dosyalarını ve günlükleri çözücü geçmişinden inceleyin. Paneli kapatmak çalıştırmayı iptal etmez; kuyruğun iptal komutunu kullanın. Kesilen iş otomatik yeniden başlatılmak yerine saklanır.

Geçmiş her çalıştırmanın girdi anlık kopyasını ve hash değerlerini korur. Deneysel sonuçlar görüntüleyicideki mevcut openEMS anten sonucunun yerini almaz. Mühendislik sonucu çıkarmadan önce mesh düzeylerini ve uygun fiziksel referansları karşılaştırın.

## Diğer deneysel iş akışları

**Koaksiyel TEM (deneysel)**, belirli geometri ve yayın sınırları olan bir openEMS port iş akışıdır; [Koaksiyel portlar](COAXIAL-PORTS.md) sayfasına bakın. Elmer kurulum seçeneği değildir.

Periyodik hücre deneyi ayrı derlenen bir araştırma arka ucu gerektirir. Standart openEMS ve normal GPU motoru bunun yerine geçmez. Desteklenen kapsam normal geliş, sıfır x/y faz kayması ve ilk boşluk kırınım eşiğinin altında eş kutuplu temel yansıma/iletimdir. Genel Floquet portları, eğik geliş ve yüksek mertebeli modlar uygulanmamıştır. Önkoşullar ve saklanan sayısal kanıtlar için [araştırma notlarına](RESEARCH-SOLVERS.md#periodic-unit-cell) bakın.
