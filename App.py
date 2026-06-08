import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Trading Plan Pro - Trending Detector", page_icon="📈", layout="wide")

# --- STYLE PREMIUM ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetric"] {
        background-color: #1f2937 !important;
        padding: 15px !important;
        border-radius: 10px !important;
        border: 1px solid #374151 !important;
    }
    div[data-testid="stMetricLabel"] > div { color: #9ca3af !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 DASHBOARD TRADING PLAN & DETEKTOR SAHAM TRENDING")
st.write(f"Screener Otomatis Saham Berpotensi Trending Hari Ini & Besok — Update: {date.today().strftime('%d %B %Y')}")

ticker_clean = st.text_input("Masukkan Kode Saham Utama (Contoh: PTBA, BRMS, BBCA)", "PTBA").strip().upper()
ticker_code = f"{ticker_clean}.JK"

st.markdown("---")

# --- FUNGSI AMBIL DATA DIVIDEN ---
def ambil_dividen_dari_finance(ticker_obj):
    try:
        hist_div = ticker_obj.dividends
        if not hist_div.empty:
            terakhir_ex_date = hist_div.index[-1]
            nominal = hist_div.iloc[-1]
            estimasi_cum_date = terakhir_ex_date - pd.offsets.BDay(1)
            
            return {
                "ada": True,
                "nominal": f"Rp {nominal:,.2f}",
                "cum_date": estimasi_cum_date.strftime('%d %B %Y'),
                "ex_date": terakhir_ex_date.strftime('%d %B %Y')
            }
    except:
        pass
    return {"ada": False}

# --- FUNGSI AMBIL BERITA ---
def ambil_berita_indonesia(ticker):
    daftar_berita = []
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            root = ET.fromstring(response.read())
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            if " - " in title: title = title.rsplit(" - ", 1)[0]
            daftar_berita.append({"title": title, "link": item.find('link').text, "source": item.find('source').text if item.find('source') is not None else "Media", "date": item.find('pubDate').text[:16]})
    except:
        pass
    return daftar_berita

# --- PROSES UTAMA SAHAM UTAMA ---
try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner(f'Menganalisis pergerakan market dan saham {ticker_clean}...'):
        ticker_obj = yf.Ticker(ticker_code)
        df_raw = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        data_dividen = ambil_dividen_dari_finance(ticker_obj)
        berita_lokal = ambil_berita_indonesia(ticker_clean)
        
    if df_raw is not None and not df_raw.empty:
        data_saham = df_raw.copy()
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        open_arr = data_saham['Open'].to_numpy().flatten()
        high_arr = data_saham['High'].to_numpy().flatten()
        low_arr = data_saham['Low'].to_numpy().flatten()
        close_arr = data_saham['Close'].to_numpy().flatten()
        volume_arr = data_saham['Volume'].to_numpy().flatten()

        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100
        
        # Analisis Volume Spike
        vol_series = pd.Series(volume_arr)
        vol_avg = float(vol_series.rolling(window=20).mean().iloc[-1])
        vol_avg_5h = float(vol_series.tail(5).mean())
        Rasio_Volume = volume_arr[-1] / vol_avg if vol_avg > 0 else 1.0

        # --- SEKSI ANALISIS PREDIKSI TRENDING (HARI INI & BESOK) ---
        st.subheader("🔮 ANALISIS PROYEKSI TRENDING (HARI INI & BESOK)")
        
        # Logika Prediksi Skor Trending
        skor_trending = 0
        faktor_pendukung = []
        
        if Rasio_Volume > 2.0:
            skor_trending += 40
            faktor_pendukung.append(f"Spike Volume Masif ({Rasio_Volume:.1f}x lipat dari rata-rata sebulan)")
        elif Rasio_Volume > 1.2:
            skor_trending += 20
            faktor_pendukung.append("Volume di atas rata-rata wajar harian (+Akumulasi Awal)")
            
        if persentase_ubah > 3.0:
            skor_trending += 30
            faktor_pendukung.append(f"Breakout Bullish Kuat ({persentase_ubah:+.2f}%)")
        elif persentase_ubah < -3.0:
            skor_trending -= 20
            faktor_pendukung.append(f"Tekanan Jual / Distribusi Kuat ({persentase_ubah:+.2f}%)")

        # Indikator Candle Close mendekati High (Bagus untuk kelanjutan besok pagi)
        rentang_harian = high_arr[-1] - low_arr[-1]
        posisi_close = (harga_terakhir - low_arr[-1]) / rentang_harian if rentang_harian > 0 else 0.5
        if posisi_close > 0.8 and persentase_ubah > 0:
            skor_trending += 30
            faktor_pendukung.append("Harga ditutup di area tertinggi harian (Potensi GAP UP besok pagi tinggi)")

        # Tampilan Hasil Proyeksi
        if skor_trending >= 60:
            st.success(f"🔥 **POTENSI TRENDING SANGAT TINGGI ({skor_trending}%)**")
            st.markdown(f"""
            * **Analisis Besok:** Saham ini memiliki momentum beli yang sangat kuat hari ini. Kemungkinan besar pergerakan naik akan berlanjut besok pagi semenjak pembukaan bursa (*Open Gap Up*).
            * **Faktor Kunci:** {', '.join(faktor_pendukung)}
            """)
        elif 30 <= skor_trending < 60:
            st.warning(f"⚡ **POTENSI TRENDING MENENGAH / SIDEWAYS UP ({skor_trending}%)**")
            st.markdown(f"""
            * **Analisis Besok:** Saham mulai masuk radar akumulasi, namun pergerakannya cenderung akan menguji area *resistance* terdekat terlebih dahulu besok. Cocok untuk *Buy on Weakness*.
            * **Faktor Kunci:** {', '.join(faktor_pendukung)}
            """)
        else:
            st.info(f"⚪ **POTENSI TRENDING RENDAH / KONSOLIDASI ({skor_trending}%)**")
            st.markdown(f"""
            * **Analisis Besok:** Saham bergerak stabil atau cenderung mengalami tekanan konsolidasi. Pergerakan hari ini dan besok diperkirakan masih sepi dari pergerakan agresif.
            * **Faktor Kunci:** {', '.join(faktor_pendukung) if faktor_pendukung else 'Tidak ada sinyal volatilitas signifikan'}
            """)

        # --- MONITORING ARA / ARB ---
        status_ekstrem = "NORMAL"
        pesan_ekstrem = ""
        warna_box = "#1f2937"

        ledakan_volume = volume_arr[-1] > (2.5 * vol_avg)
        harga_terkunci_atas = (high_arr[-1] - harga_terakhir) <= (0.005 * harga_terakhir)
        harga_terkunci_bawah = (harga_terakhir - low_arr[-1]) <= (0.005 * harga_terakhir)
        
        if ledakan_volume and harga_terkunci_atas and persentase_ubah > 4:
            status_ekstrem = "ARA_POTENTIAL"
            warna_box = "#10B981"
            pesan_ekstrem = "🔥 MOMENTUM ARA / ACCUMULATION BOOM: Pembeli mengunci harga hingga batas atas bursa!"
        elif harga_terkunci_bawah and persentase_ubah < -4:
            status_ekstrem = "ARB_WARNING"
            warna_box = "#EF4444"
            pesan_ekstrem = "🚨 PERINGATAN ARB / PANIC SELLING: Harga terkunci di batas bawah harian oleh tekanan jual."

        if status_ekstrem != "NORMAL":
            st.markdown(f"<div style='background-color:{warna_box}; padding:15px; border-radius:8px; color:white; font-weight:bold; margin-top:10px;'>{pesan_ekstrem}</div>", unsafe_allow_html=True)

        st.markdown("---")
        
        # Hitung Pivot S&R
        high_5h, low_5h = float(max(high_arr[-5:])), float(min(low_arr[-5:]))
        pivot = (high_5h + low_5h + harga_terakhir) / 3
        r1, r2 = (2 * pivot) - low_5h, pivot + (high_5h - low_5h)
        s1, s2 = (2 * pivot) - high_5h, pivot - (high_5h - low_5h)

        # 3 Kolom Metrik Atas
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_clean}", "Status: Terhubung Aktif")
        col_m2.metric("HARGA CLOSE TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME TRANSAKSI", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20H: {vol_avg/1e6:.1f} M", delta_color="off")

        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {int(s1):,.0f} - Rp {int(harga_terakhir):,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {int(s2 * 0.99):,.0f}")
            st.success(f"🎯 **TARGET UNTUNG:** TP1: Rp {int(r1):,.0f} | TP2: Rp {int(r2):,.0f}")

        with col_right:
            st.subheader("📊 ANALISIS GRAFIK CANDLESTICK HARIAN")
            idx_data = data_saham.index[-40:]
            fig = go.Figure(data=[go.Candlestick(x=idx_data, open=open_arr[-40:], high=high_arr[-40:], low=low_arr[-40:], close=close_arr[-40:])])
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=350)
            st.plotly_chart(fig, use_container_width=True)
            
            # --- SEKSI INFO DIVIDEN ---
            st.write("---")
            st.subheader("💰 JADWAL DIVIDEN EMITEN (DATA TERBARU)")
            if data_dividen["ada"]:
                st.markdown(f"""
                <div style="background-color: #1f2937; padding: 15px; border-radius: 8px; border-left: 5px solid #10B981;">
                    <h5 style="margin:0; color:#10B981;">📢 Informasi Pembagian Dividen Tunai</h5>
                    <p style="margin:8px 0; color:white; font-size:16px;"><b>Besaran Dividen:</b> <span style="color:#10B981; font-weight:bold;">{data_dividen['nominal']}</span> per lembar saham</p>
                    <table style="width:100%; margin-top:10px; color:white; font-size:14px;">
                        <tr><td><b>📅 CUM DATE (Pasar Reguler):</b></td><td style="color:#FBBF24;"><b>{data_dividen['cum_date']}</b></td></tr>
                        <tr><td><b>📅 EX DATE (Pasar Reguler):</b></td><td style="color:#EF4444;"><b>{data_dividen['ex_date']}</b></td></tr>
                    </table>
                </div>
                """, unsafe_allow_html=True)

            # --- SEKSI BERITA ---
            st.write("---")
            st.subheader("📰 AGREGATOR BERITA & SENTIMEN LOKAL (ID)")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
            else:
                st.info(f"⚪ Tidak ditemukan berita spesifik harian.")
    else:
        st.error("Data saham tidak ditemukan.")
except Exception as e:
    st.error(f"Gagal memuat aplikasi: {str(e)}")
