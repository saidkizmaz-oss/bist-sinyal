# BIST Sinyal Sistemi — Railway Deploy

## Railway'e Yükleme (5 dakika)

### 1. GitHub hesabı aç
https://github.com → Sign Up (yoksa)

### 2. Yeni repo oluştur
- GitHub'da "New repository" 
- İsim: `bist-sinyal`
- Public seç → Create

### 3. Dosyaları yükle
"uploading an existing file" linkine tıkla
Bu klasördeki TÜM dosyaları sürükle bırak:
- server.py
- requirements.txt
- Procfile
- nixpacks.toml
- static/ klasörü (index.html, manifest.json, sw.js)

"Commit changes" butonuna bas

### 4. Railway hesabı aç
https://railway.app → Login with GitHub

### 5. Deploy et
- "New Project" → "Deploy from GitHub repo"
- `bist-sinyal` reposunu seç
- Otomatik deploy başlar (~2-3 dk)
- Bitince sana bir URL verir: `https://bist-sinyal-xxx.railway.app`

### 6. iPhone'a ekle
- iPhone'da Safari'yi aç
- URL'yi gir
- Alt ortadaki "Paylaş" (kutu+ok) butonuna bas
- "Ana Ekrana Ekle" seç
- "Ekle" → uygulama gibi açılır!

## Notlar
- Railway ücretsiz planda aylık 500 saat veriyor
- Uygulama sürekli açık kalırsa ~21 gün/ay ücretsiz
- Daha fazla için $5/ay Pro plan

⚠️ Yatırım tavsiyesi değildir. Eğitim amaçlıdır.
