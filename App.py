import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Trading Plan Pro + Dividen + News", page_icon="📈", layout="wide")

# --- STYLE PREMIUM ANTI-BLUR (Warna Teks Putih Terang) ---
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

st.title("🦅 DASHBOARD TRADING PLAN HARIAN & AGREGATOR BERITA")
st.write(f"Analisis Teknikal, Jadwal Dividen & Sentimen Pasar — Update: {date.today().strftime('%d %B %Y')}")

ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BRMS, BBCA, TLKM)", "BBCA").upper()
ticker_code = f"{ticker_input}.JK"

st.markdown("---")

# --- FUNGSI AMBIL BERITA DARI GOOGLE NEWS INDONESIA ---
def ambil_berita_indonesia(ticker):
    daftar_berita = []
    try:
        query = urllib.parse.quote(f"{ticker} saham")
        url = f"https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            source = item.find('source').text if item.find('source') is not None else "Sumber Lokal"
            
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            daftar_berita.append({"title": title, "link": link, "source": source, "date": pub_date[:16]})
    except Exception as e:
        pass
    return daftar_berita

try:
    start_date = date.today() - timedelta(days=365)
    end_date = date.today()
    
    with st.spinner('Memindai grafik, jadwal dividen, dan agregator berita...'):
        data_saham = yf.download(ticker_code, start=start_date, end=end_date, interval="1d")
        
        # Ambil Profil Lengkap Emiten untuk Data Dividen
        ticker_obj = yf.Ticker(ticker_code)
        try:
            info_saham = ticker_obj.info
            hist_div = ticker_obj.dividends
        except:
            info_saham = {}
            hist_div = pd.Series(dtype=float)

        berita_lokal = ambil_berita_indonesia(ticker_input)
        
    if not data_saham.empty:
        if isinstance(data_saham.columns, pd.MultiIndex):
            data_saham.columns = data_saham.columns.get_level_values(0)
            
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if isinstance(data_saham[col], pd.DataFrame):
                data_saham[col] = data_saham[col].iloc[:, 0]

        open_arr = data_saham['Open'].values
        high_arr = data_saham['High'].values
        low_arr = data_saham['Low'].values
        close_arr = data_saham['Close'].values
        volume_arr = data_saham['Volume'].values

        harga_terakhir = float(close_arr[-1])
        harga_sebelumnya = float(close_arr[-2])
        perubahan = harga_terakhir - harga_sebelumnya
        persentase_ubah = (perubahan / harga_sebelumnya) * 100

        data_saham['Vol_Avg'] = data_saham['Volume'].rolling(window=20).mean()
        vol_avg = float(data_saham['Vol_Avg'].iloc[-1])

        # --- LOGIKA DETEKSI POTENSI ARA / ARB ---
        status_ekstrem = "NORMAL"
        pesan_ekstrem = ""
        warna_box = "#1f2937"

        ledakan_volume = volume_arr[-1] > (2.5 * vol_avg)
        harga_terkunci_atas = (high_arr[-1] - harga_terakhir) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        
        if ledakan_volume and harga_terkunci_atas and persentase_ubah > 4:
            status_ekstrem = "ARA_POTENTIAL"
            warna_box = "#10B981"
            pesan_ekstrem = "🔥 KEPUTUSAN ARA / MOMENTUM BOOM: Buyer menguasai 100% papan perdagangan. Volume meledak masif! Rekomendasi: HOLD/BUY ON OPEN besok pagi jika belum punya barang, ikuti momentum searah!"

        harga_terkunci_bawah = (harga_terakhir - low_arr[-1]) <= (0.01 * (high_arr[-1] - low_arr[-1]) if (high_arr[-1] - low_arr[-1]) > 0 else 1)
        if harga_terkunci_bawah and persentase_ubah < -4:
            status_ekstrem = "ARB_WARNING"
            warna_box = "#EF4444"
            pesan_ekstrem = "🚨 PERINGATAN ARB / PANIC SELLING: Seller mengunci harga di batas terendah harian tanpa perlawanan. Rekomendasi: JANGAN FOMO MASUK, JUAL/AVOID terlebih dahulu demi keamanan modal Anda!"

        # --- PEMBACAAN 5 POLA CANDLESTICK ---
        pola_terdeteksi = []
        if len(close_arr) >= 4:
            body_1 = abs(close_arr[-1] - open_arr[-1])
            ushadow_1 = high_arr[-1] - max(open_arr[-1], close_arr[-1])
            lshadow_1 = min(open_arr[-1], close_arr[-1]) - low_arr[-1]
            body_2 = abs(close_arr[-2] - open_arr[-2])
            bear_2 = close_arr[-2] < open_arr[-2]
            bull_1 = close_arr[-1] > open_arr[-1]
            body_3 = abs(close_arr[-3] - open_arr[-3])
            bear_3 = close_arr[-3] < open_arr[-3]
            bull_2 = close_arr[-2] > open_arr[-2]
            bull_3 = close_arr[-3] > open_arr[-3]

            if lshadow_1 >= 2 * body_1 and ushadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("🔨 Hammer")
            if bear_2 and bull_1 and close_arr[-1] >= open_arr[-2] and open_arr[-1] <= close_arr[-2]:
                pola_terdeteksi.append("🔥 Bullish Engulfing")
            if bear_3 and body_2 < 0.3 * body_3 and bull_1 and close_arr[-1] > (open_arr[-3] + close_arr[-3])/2:
                pola_terdeteksi.append("🌅 Morning Star")
            if bull_3 and bull_2 and bull_1 and close_arr[-1] > close_arr[-2] > close_arr[-3]:
                pola_terdeteksi.append("⚔️ Three White Soldiers")
            if ushadow_1 >= 2 * body_1 and lshadow_1 <= 0.2 * body_1 and body_1 > 0:
                pola_terdeteksi.append("📐 Inverted Hammer")

        # Hitung Pivot S&R
        data_1w = data_saham.tail(5)
        h_1w, l_1w, c_1w = float(data_1w['High'].max()), float(data_1w['Low'].min()), float(data_1w['Close'].iloc[-1])
        pivot = (h_1w + l_1w + c_1w) / 3
        r1, r2 = (2 * pivot) - l_1w, pivot + (h_1w - l_1w)
        s1, s2 = (2 * pivot) - h_1w, pivot - (h_1w - l_1w)

        buy_area_bawah, buy_area_atas = int(s1), int(harga_terakhir)
        stop_loss = int(s2 * 0.99)
        tp1, tp2 = int(r1), int(r1 * 1.03)

        # Tampilan 3 Kolom Metrik Atas
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("EMITEN SAHAM", f"{ticker_input}.JK", "TF: HARIAN (1D)")
        col_m2.metric("HARGA CLOSE TERAKHIR", f"Rp {harga_terakhir:,.0f}", f"{perubahan:+,.0f} ({persentase_ubah:+.2f}%)")
        col_m3.metric("VOLUME TRANSAKSI", f"{volume_arr[-1]/1e6:.1f} M", f"Rata-rata 20H: {vol_avg/1e6:.1f} M", delta_color="off")

        st.markdown("---")

        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.subheader("🚨 MONITORING VOLATILITAS EKSTREM")
            if status_ekstrem != "NORMAL":
                st.markdown(f"""
                    <div style='background-color:{warna_box}; padding:15px; border-radius:8px; color:white; font-weight:bold;'>
                        {pesan_ekstrem}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("⚪ **Status Pergerakan:** Pergerakan harga harian masih dalam batas wajar bursa (Tidak terdeteksi akumulasi/distribusi ekstrem calon ARA/ARB).")

            st.write("---")
            
            st.subheader("🔮 PEMBACAAN CANDLE & SINYAL BESOK")
            if pola_terdeteksi and status_ekstrem != "ARB_WARNING":
                for pola in pola_terdeteksi:
                    st.success(f"**Pola Reversal Aktif:** {pola}")
                st.markdown("""
                    <div style='background-color:#10B981; padding:12px; border-radius:8px; text-align:center;'>
                        <h4 style='color:white; margin:0;'>🚀 SIGNAL: BUY (UNTUK CANDLE BESOK)</h4>
                    </div>
                """, unsafe_allow_html=True)
            elif status_ekstrem == "ARB_WARNING":
                st.error("❌ **Sinyal Candlestick Dimatikan:** Terdeteksi kepanikan (Panic Selling), abaikan semua pola buy sampai harga stabil.")
            else:
                st.write("• Tidak ada 5 pola bullish candlestick utama malam ini. Jalankan taktik antre beli bawah.")

            st.write("---")
            
            st.subheader("🏹 TRADING PLAN SETUP")
            st.info(f"🛒 **BUY AREA:** Rp {buy_area_bawah:,.0f} - Rp {buy_area_atas:,.0f}")
            st.error(f"⚠️ **STOP LOSS (SL):** Rp {stop_loss:,.0f}")
            st.success(f"🎯 **TARGET UNTUNG:** TP1: Rp {tp1:,.0f} | TP2: Rp {tp2:,.0f}")

        with col_right:
            st.subheader("📊 ANALISIS GRAFIK CANDLESTICK HARIAN")
            df_chart = data_saham.tail(40)
            fig = go.Figure(data=[go.Candlestick(
                x=df_chart.index, open=df_chart['Open'], high=df_chart['High'],
                low=df_chart['Low'], close=df_chart['Close'], name='Candle Harian'
            )])
            fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=380)
            st.plotly_chart(fig, use_container_width=True)
            
            # --- SEKSI BARU: INFO DIVIDEN (CUM & EX DATE) ---
            st.write("---")
            st.subheader("💰 INFO DIVIDEN (CUM & EX DATE)")
            
            div_yield = info_saham.get('dividendYield', None)
            ex_div_date_unix = info_saham.get('exDividendDate', None)
            
            ex_div_date_str = "Belum Ada Jadwal"
            cum_div_date_str = "Belum Ada Jadwal"
            
            # Jika ada jadwal ex-date dari Yahoo
            if ex_div_date_unix:
                ex_date_obj = pd.to_datetime(ex_div_date_unix, unit='s')
                ex_div_date_str = ex_date_obj.strftime('%d %B %Y')
                # Cum date bursa regular umumnya 1 hari kerja sebelum Ex-Date
                cum_date_obj = ex_date_obj - pd.offsets.BDay(1)
                cum_div_date_str = cum_date_obj.strftime('%d %B %Y')
                
            last_div_date_str = "-"
            last_cum_date_str = "-"
            last_div_amount = 0
            
            # Tarik riwayat dividen terakhir
            if not hist_div.empty:
                last_ex_date = hist_div.index[-1]
                last_div_date_str = last_ex_date.strftime('%d %B %Y')
                last_cum_date = last_ex_date - pd.offsets.BDay(1)
                last_cum_date_str = last_cum_date.strftime('%d %B %Y')
                last_div_amount = hist_div.iloc[-1]

            if not hist_div.empty or div_yield:
                c1, c2 = st.columns(2)
                c1.info(f"**Riwayat Dividen Terakhir**\n\nNominal: **Rp {last_div_amount:,.2f}** / lembar\n\nCum-Date: **{last_cum_date_str}**\n\nEx-Date: **{last_div_date_str}**")
                
                yield_str = f"{div_yield * 100:.2f}%" if div_yield else "N/A"
                c2.success(f"**Proyeksi Jadwal Mendatang**\n\nEstimasi Yield: **{yield_str}**\n\nCum-Date: **{cum_div_date_str}**\n\nEx-Date: **{ex_div_date_str}**")
            else:
                st.info("⚪ Tidak ada data histori / pembagian dividen untuk emiten ini yang tercatat.")

            # --- SEKSI BERITA MULTI-SOURCE GOOGLE NEWS INDONESIA ---
            st.write("---")
            st.subheader("📰 BERITA & SENTIMEN PASAR LOKAL (ID)")
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔗 **[{item['title']}]({item['link']})**")
                    st.caption(f"📰 {item['source']} | 🕒 {item['date']}")
                    st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)
            else:
                st.info(f"⚪ Tidak ditemukan berita spesifik dalam Bahasa Indonesia untuk kata kunci '{ticker_input} saham' hari ini.")

    else:
        st.error("Data saham tidak ditemukan.")
except Exception as e:
    st.error(f"Gagal memuat analisis harian: {str(e)}")
