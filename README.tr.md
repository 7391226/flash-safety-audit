# flash-safety-audit

> **Uyarı:** Bu bir ön taramadır, uyum belgesi değildir. Geçen bir sonuç
> sayfanın güvenli olduğunu kanıtlamaz.

*[English](README.md)*

Bir web sayfasını ya da videoyu **ışığa duyarlı epilepsi** riski açısından
tarayan bir [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills)
ve komut satırı aracı. Sonucu **WCAG 2.3.1 – Üç Yanıp Sönme veya Eşiğin
Altında** (Three Flashes or Below Threshold) ölçütüne göre raporlar.

Sayfayı görünmez (headless) Chromium ile kaydeder (Python için Playwright).
Kareleri [IRIS](https://github.com/electronicarts/IRIS) kitaplığının Python
uyarlaması [`iris-pse-detection`](https://pypi.org/project/iris-pse-detection/)
ile inceler. Markdown ve JSON biçiminde rapor yazar.

## Neden gerekli?

IRIS iyi bir yanıp sönme dedektörüdür. Ancak varsayılan alan eşiği 0,25'tir
(ekranın %25'i). WCAG 2.3.1 ise 1024 × 768 ekranda toplam 341 × 256 piksellik
alanı esas alır:

    341 × 256 / (1024 × 768) ≈ 0,111

Varsayılan ayarla ekranın %15, %20 ve %24'ünde saniyede 5 kez yanıp sönen
sayfalar **geçer**. 0,111 ile bu sayfalar doğru şekilde **kalır**. Bu araç
WCAG eşiğini kurar ve IRIS'in yayıncılık kurallarını WCAG kararından ayrı tutar.

## Kurulum (Windows, PowerShell)

Python 3.10 veya daha yenisi gerekir (3.13 ile sınandı).

```powershell
git clone <depo-adresi> flash-safety-audit
cd flash-safety-audit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Claude Code becerisi olarak kullanmak için klasörü
`%USERPROFILE%\.claude\skills\flash-safety-audit` (kişisel) ya da
`<proje>\.claude\skills\flash-safety-audit` (tek proje) altına kopyalayın.
Claude, örneğin "şu sayfayı epilepsi açısından denetle" dediğinizde beceriyi
kullanır.

ffmpeg **gerekmez**: OpenCV paketi Playwright'ın `.webm` kayıtlarını doğrudan
okur (Windows 11'de doğrulandı). OpenCV sürümünüz bir videoyu okuyamazsa önce
H.264 `.mp4` biçimine çevirin, örneğin `ffmpeg -i girdi.webm cikti.mp4`.

## Kullanım

```powershell
python scripts/audit.py --url https://ornek.com
python scripts/audit.py --html sayfa.html
python scripts/audit.py --video oyun_kaydi.mp4
```

| Seçenek | Varsayılan | Anlamı |
| --- | --- | --- |
| `--viewport` | `1024x768` | Tarayıcı boyutu. WCAG'ın piksel tanımıyla eşleşir. |
| `--duration` | `10` | Kayıt süresi (saniye). |
| `--settle` | `1` | Sayfa yüklendikten sonra kayıttan önce bekleme (saniye). |
| `--out` | `reports/` | Rapor klasörlerinin yeri. |
| `--area-threshold` | `0.111` | Yanıp sönme alan oranı. Yalnızca bilerek değiştirin. |

Çıkış kodu: `0` WCAG geçti, `1` WCAG kaldı, `2` hata.

Her çalıştırma `reports/<ad>-<zaman>/` klasörünü oluşturur:

- `report.md` – okunabilir rapor
- `report.json` – aynı veriler, araçlar için
- `frames.csv` – her kare için IRIS verisi
- `recording.mp4` – sayfa kaydı (`--video` ile oluşmaz)
- `iris.log` – IRIS çıktısı

## Raporu okuma

Raporda iki ayrı bölüm vardır.

**WCAG 2.3.1 sonucu – GEÇTİ / KALDI.** 0,111 alan eşiğiyle bulunan parlaklık
ve kırmızı "flash failure" kare sayıları (herhangi bir saniyede 3'ten fazla
yanıp sönme). Sıfırdan büyük her değer KALDI demektir. Zaman aralıkları
kaydın başından itibaren saniye olarak verilir.

**Ek uyarılar (WCAG dışı).** IRIS'in "extended failure" ve "warning"
kareleri. Bunlar yayıncılık kurallarından gelir, örneğin saniyede 2–3 yanıp
sönmenin yaklaşık 4 saniye sürmesi. WCAG kararını değiştirmez. Saniyede iki
kez yanıp sönen tam ekran bir sayfa WCAG'a göre geçer, ama burada "extended
failure" görünür.

## Sınırlar

- **Hızlı titreşim ölçülmez.** Sayfa kayıtları saniyede 25 karedir. Bu yüzden
  saniyede yaklaşık 12'den hızlı titreşimler (kare hızının yarısı) yanlış
  sayılabilir. GEÇTİ sonucu bu tür içeriği kapsamaz.
- **Alan modeli.** IRIS yanıp sönen alanı tüm kare üzerinden toplar; WCAG ise
  herhangi bir 341 × 256 piksellik bölgeye bakar. Ekrana dağılmış küçük yanıp
  sönmelerde sonuç WCAG'dan daha katı olabilir.
- **Başka görüntü alanları.** Görüntü alanı 1024 × 768 değilse eşik yine alanın
  0,111'i olur. Raporda "görüntü alanının tipik bir ekranı doldurduğu
  varsayıldı" notu yer alır.
- **Etkileşim yok.** Tıklama, üzerine gelme, kaydırma ve klavye bu sürümde
  desteklenmez. Bu tür içeriği kendiniz kaydedin ve `--video` kullanın.
- **Durağan sayfalar.** Ekranda bir şey değişmezse Chromium yeni kare
  göndermez. Kaydı tamamlamak için son kare tekrarlanır; rapor bunu belirtir.
- **Video kare hızı.** IRIS kare hızını tam sayıya yuvarlar (29,97 → 29). Bu,
  bu tür videolarda zamanlamayı biraz kaydırır.
- Desen (çizgi) algılama kullanılmaz.

## Sınamalar

```powershell
python -m pytest -m "not slow"   # hızlı: yapay videolar, yaklaşık 15 sn
python -m pytest                 # hepsi: 11 sayfa da kaydedilir, yaklaşık 5 dk
```

`tests/make_fixtures.py`, `tests/fixtures/` içindeki HTML sayfalarını yazar.
`tests/make_videos.py`, 640 × 360, saniyede 30 kare, 6 saniyelik yapay videolar
üretir. Yavaş sınamalar, kare atlamayı yakalamak için her kaydın 25 kare/sn
olduğunu ve yanıp sönme hızının beklenen değerin ± 0,2 içinde olduğunu da
denetler.

Windows 11'de beklenen ve ölçülen sonuçlar:

| Sayfa | Varsayılan IRIS (0,25) | WCAG ayarı (0,111) | WCAG 2.3.1 | Ek uyarı |
| --- | --- | --- | --- | --- |
| Durağan beyaz | Geçti | Geçti | GEÇTİ | Yok |
| Tam ekran, saniyede 1 | Geçti | Geçti | GEÇTİ | Yok |
| Tam ekran, saniyede 2 | Kaldı (extended) | Kaldı (extended) | GEÇTİ | Var |
| Tam ekran, saniyede 4 | Kaldı | Kaldı | KALDI | — |
| Tam ekran, saniyede 5 | Kaldı | Kaldı | KALDI | — |
| Tam ekran kırmızı (#f00), saniyede 5 | Kaldı (kırmızı da) | Kaldı | KALDI | — |
| %30 × %30 (alanın %9'u), saniyede 5 | Geçti | Geçti | GEÇTİ | Yok |
| %39 × %39 (%15), saniyede 5 | Geçti | Kaldı | KALDI | — |
| %45 × %45 (%20), saniyede 5 | Geçti | Kaldı | KALDI | — |
| %49 × %49 (%24), saniyede 5 | Geçti | Kaldı | KALDI | — |
| %60 × %60 (%36), saniyede 5 | Kaldı | Kaldı | KALDI | — |

Sınama sayfaları yanıp söner. **Onları asla görünür bir tarayıcıda açmayın.**
README bilerek yanıp sönen görüntü ya da video içermez.

## Lisans ve kaynaklar

MIT – bkz. [LICENSE](LICENSE) ve [NOTICE](NOTICE).

- [IRIS](https://github.com/electronicarts/IRIS), Electronic Arts Inc.,
  BSD-3-Clause.
- [iris-pse-detection](https://pypi.org/project/iris-pse-detection/), IRIS'in
  Python uyarlaması, MIT.
