# Deneysel çözücüler

Varsayılan çözücü openEMS'tir. **Elmer FEM — Deneysel özmodlar**, **Elmer FEM · Deneysel anten**, sabit **EMerge** WR-90 dalga kılavuzu fikstürü ve **EMerge FEM · Deneysel** (birleşik N-port Tasarım yolu: uyarılmış/toplu, düzlemsel mikroşerit veya tümü koaksiyel TEM tarifleri, en fazla 8 port), geometri ve sonuç desteği daha sınırlı, isteğe bağlı araştırma yollarıdır. Arka ucun kurulması veya bir çalıştırmanın tamamlanması, tasarımınızın sayısal doğruluğunu kanıtlamaz.

## Etkin çözücü (Simülasyon şeridi)

Masaüstü tasarımcıda **Simülasyon › Çözücü**, oturumun etkin çözücüsü olarak **openEMS** veya **EMerge (deneysel)** seçmenizi sağlar. Yeni oturumda varsayılan openEMS'tir. EMerge seçmek Çalıştır görünümünü (etiket ve vurgu), Frekans / Sınırlar / Mesh ayarlarını ve hangi Simülasyon / Sonra / Optimize eylemlerinin açık kalacağını yeniden hedefler. openEMS'i ürün varsayılanı olarak değiştirmez ve EMerge'i doğrulanmış üretim çözücüsü yapmaz.

Elmer ve sabit EMerge dalga kılavuzu fikstürü **Deneysel çözücüler** / Çalıştır penceresinin uzun seçenek listesinde kalır — bu seçicide üçüncü bir şerit vurgusu değildir. EMerge etkinken **Optimize** (Tarama / Optimizatör) kapalı kalır; bu yol ertelenmiştir. EMerge altında Mesh görünümü, Mesh oluştur (veya yüzey kenarlarını dışa aktaran bir EMerge sonucu) sonrası deneysel FEM **dış yüzey** tel çerçevesini çizer. openEMS FDTD ızgarasını tetrahedral meshmiş gibi göstermez.

Kalan EMerge izleme maddeleri: [docs/agent/BACKLOG-emerge-port-map.md](../agent/BACKLOG-emerge-port-map.md).

## Masaüstü uygulamasında kurulum

**Simülasyon › Deneysel çözücüler** komutunu veya Simülasyon çalıştır penceresindeki **Elmer kurulumu ve geçmiş** bağlantısını açın. Bir arka uç seçip çalıştırmayı göndermeden önce kullanılabilirliğini denetleyin.

Windows'ta **Elmer'i kur**, siz istediğinizde Fairbeam'in sabitlediği taşınabilir paketi indirir. Paket doğrulanır ve openEMS çalışma ortamından ayrı olarak uygulamanın veri klasörüne kaydedilir. Sistem genelinde kurulmaz. Yönetilen kopyayı kullanmak için yolu boş bırakın. Girdiğiniz klasör, `FAIRBEAM_ELMER_ROOT` veya `PATH` üzerindeki Elmer önceliklidir.

macOS ve Linux'ta Elmer'i kendiniz kurun. `bin/ElmerSolver` ve `bin/ElmerGrid` içeren kurulumu veya ikili dosya klasörünü seçin. Kullanılabilirlik denetimi yürütülebilir dosyaları bulur; fiziksel modelin veya tüm yerel bağımlılıkların yeterliliğini doğrulamaz. Hiçbir arka uç otomatik kurulmaz.

Kurulu uygulama `No module named fairbeam_elmer` veya `No module named fairbeam_emerge` bildirirse Fairbeam'i güncelleyin veya onarın. Yalnızca Elmer veya EMerge kurmak, Fairbeam'in Python bağdaştırıcılarını sağlamaz. Kaynak üzerinde çalışan katkıcılar ayrı [araştırma kurulumu ve kanıtları](RESEARCH-SOLVERS.md) kullanmalıdır.

## EMerge dalga kılavuzu fikstürü

Yalnızca sabit WR-90 hava dolu dalga kılavuzu fikstürü için Simülasyon → Deneysel çözücüler içinde **EMerge** arka ucunu seçin. A düzeyi mevcut tasarımı çevirmez. `coarse` veya `fine` çözünürlüğü seçip gönderin; sonuçlar Araştırma panelinde analitik düz dalga kılavuzu referansına göre denetlenir.

Windows'ta **EMerge'i kur**, PyPI'dan hash kilitli `emerge==3.0.0b12` ile sabitlenmiş bir Python 3.13 sanal ortamı oluşturur. Araştırma paneli, Kur düğmesinden önce EMerge'in GPL-2.0-or-later bildirimini ve Intel MKL'nin özel lisansını gösterir. Kilitli indirme kümesi yaklaşık 399 MiB'tır (418619020 bayt, PyPI tekerlek boyutları 2026-11-04). `3.0.0b12` için 2026-11-04'te ölçülen yönetilen kurulum 1421133962 bayt (1355,3 MiB) ve 80,9 s sürdü. Yönetilen kopyayı kullanmak için yolu boş bırakın. Girdiğiniz klasör veya `FAIRBEAM_EMERGE_PYTHON` önceliklidir. Sistem genelinde hiçbir şey kurulmaz ve EMerge Fairbeam kurucusuna gömülmez.

macOS ve Linux'ta yönetilen kurucu yoktur. `emerge==3.0.0b12` içeren kendi Python 3.10–3.13 ortamınızı oluşturun, ardından yol alanına o ortamın klasörünü (veya Python yürütülebilir dosyasını) girin ya da `FAIRBEAM_EMERGE_PYTHON` ayarlayın.

Fikstür tanımı, kabul ölçütleri ve kaydedilmiş yerel gözlemler için [EMerge deneyine](EMERGE-EXPERIMENT.md) bakın.

## EMerge FEM · Deneysel (birleşik N-port)

Çalıştırma sunucusu `emerge` ≥ 3 bildiriyorsa **Çalıştır**, Elmer seçeneklerinden sonra **EMerge FEM · Deneysel** sunar. Tek giriş şu Tasarım tariflerini kapsar: uyarılmış/toplu (eksenlere paralel dielektrik kutular ve metal levhalar), düzlemsel mikroşerit/Ayrık (altta toprak ve üstte z-normal bakırlı tek katman tahta), klasik CPW (eşdüzlemli üst topraklar; `accept_modal_ports` / `accept_lumped_terminals` arkasında `WavePort` / toplu boşluk plakası) ve tümü koaksiyel TEM (analitik `CoaxPort`, sabit εr dolgu, açık `accept_coaxial_tem`). Port sayısı, tek türden **1…8** olabilir; karışık türler, çok katman, via, topraklı CPW, eğriler ve desteklenmeyen geometri reddedilir. Yaklaşık eşlemeler mevcut `accept_*` kapılarını korur. Tasarım düzlemsel sınıflanırsa muhafaza / hava / pay görünür; koaksiyel taslaklarda bunun yerine koaksiyel kabul açıklaması gösterilir. Uzak alan ve kazanç belgesi yoktur; durum `results_exported`'tur. Paylaşılan Sonuçlar, openEMS'in yerine geçmeden eksiksiz N×N deneysel S matrisini gösterir. B/C aşaması sınırları [EMerge deneyinde](EMERGE-EXPERIMENT.md) yer alır.

Çözünürlükler `f_max`teki dalga boyu kesirleridir: `coarse` = 0,25, `fine` = 0,15. Nokta sayısı 3–41. Uyarılmış sınıf işçi zaman aşımı 1800 s (hacim vekili); düzlemsel sınıf 3600 s (tetrahedra vekili, 400000). Şema `fairbeam.emerge-result/2`.

Kayıtlı Patch ve hairpin yerel sayıları (ve EMerge'in openEMS S parametresi uyumu iddia etmediği dürüstlük ifadeleri) [EMerge deneyinde](EMERGE-EXPERIMENT.md) kalır. Mesh oluştur çözümsüz deneysel FEM yüzeyini de üretebilir; ayrıntılar İngilizce sayfa ve README ile aynıdır.

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
