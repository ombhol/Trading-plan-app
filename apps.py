# main.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- IMPORT MODULES KUSTOM ---
from utils import sesuaikan_fraksi_bei, hitung_batas_ara_arb, cek_waktu_trading
from indicators import calculate_indicators, calculate_daily_atr
from data_fetcher import ambil_harga_realtime, get_market_data, ambil_berita_indonesia
from scanner import scan_top_saham

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Trading Plan Pro V8.2", layout="wide", page_icon="🦅")

# --- 1. INISIALISASI MEMORI (SESSION STATE) ---
if 'ticker_utama' not in st.session_state:
    st.session_state.ticker_utama = "PSAB" # Ticker default awal
if 'sudah_scan_awal' not in st.session_state:
    st.session_state.sudah_scan_awal = False

# --- UI SIDEBAR PENGATURAN ---
with st.sidebar:
    st.markdown("### ⚙️ Parameter Trading (Real Market)")
    
    # 2. HUBUNGKAN INPUT DENGAN MEMORI
    ticker_input = st.text_input("Analisis Saham Spesifik:", value=st.session_state.ticker_utama).upper()
    # Jika user mengetik manual, update memorinya
    if ticker_input != st.session_state.ticker_utama:
        st.session_state.ticker_utama = ticker_input
        
    harga_manual = st.number_input("Bypass Harga Real-Time (Opsional):", value=0, step=1, help="Isi dengan harga live dari Stockbit/Trimegah jika API delay.")
    modal_trading = st.number_input("Total Portofolio (Rp):", value=1000000, step=1000000)
    risiko_persen = st.slider("Risiko per Trade (%):", 0.1, 5.0, 2.0) / 100
    fee_broker = st.number_input("Total Fee Jual+Beli (%):", value=0.4, step=0.1) / 100
    
    st.markdown("---")
    st.markdown("### 📋 Daftar Pantauan (Scanner)")
    saham_input_user = st.text_input("Daftar Saham:", value="MPMX, ASGR, LPPF, ROTI, CNMA, RALS, TAPG, UNIC, KKGI, CITA, PTBA, UNVR, SPTO, FWCT, LPIN, TLDN, BSSR, ADRO, MARK, TPMA, SGRO, TOTL, ARNA, POWR, HRXA, NRCA, MSTI, EAST, ACES, TOTO, SIDO, AUTO, TLKM")
    daftar_pantauan = [s.strip().upper() for s in saham_input_user.split(",") if s.strip()]

# --- UI MAIN: HEADER ---
st.title("🦅 TRADING PLAN PRO V8.2 (Street Smart Edition)")

status_waktu, warna_waktu = cek_waktu_trading()
getattr(st, warna_waktu)(f"🕒 **Sesi Trading BEI Saat Ini:** {status_waktu}")

# --- UI MAIN: TOP REKOMENDASI ---
st.subheader("🏆 Top 3 Sinyal (Real Turnover > 100 Jt/5 Menit)")
with st.spinner("Memindai radar uang pintar secara paralel..."):
    top_3 = scan_top_saham(daftar_pantauan)

# 3. LOGIKA INJEKSI OTOMATIS SAAT PERTAMA KALI BROWSER DIBUKA
if top_3 and not st.session_state.sudah_scan_awal:
    # Ambil juara 1 dari Top 3
    saham_terbaik = top_3[0]['ticker']
    # Ubah memori ticker utama menjadi saham terbaik
    st.session_state.ticker_utama = saham_terbaik
    # Tandai bahwa scan awal sudah dilakukan agar tidak berulang terus-menerus
    st.session_state.sudah_scan_awal = True
    # Rerun instan agar chart di bawah langsung membedah saham juara 1
    st.rerun()

if top_3:
    cols_top = st.columns(3)
    for i, data in enumerate(top_3):
        warna_skor = "#10B981" if data['skor'] >= 70 else "#FBBF24"
        with cols_top[i]:
            st.markdown(f"""
            <div style="background-color: #1f2937; padding: 20px; border-radius: 12px; border-top: 5px solid {warna_skor}; text-align: center;">
                <h2 style="margin: 0; color: white;">{data['ticker']}</h2>
                <h1 style="margin: 5px 0; color: {warna_skor};">{data['skor']} / 100</h1>
                <hr style="border-color: #374151; margin: 10px 0;">
                <p style="margin: 0; color: white; font-weight: bold;">Harga Indikatif: Rp {data['harga']:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Scanner Kosong: Belum ada saham yang memenuhi kriteria.")
st.markdown("---")

# --- UI MAIN: REKOMENDASI STRATEGI SESI (HIGH SENSITIVITY) ---
if top_3:
    st.markdown("### 🧭 Peta Taktis & Eksekusi Sesi Ini")
    
    if "Pagi" in status_waktu:
        kandidat = max(top_3, key=lambda x: x['vol_spike'])
        st.success("🔥 **STRATEGI: Momentum Scalping (Hit & Run)**")
        st.write("**Kondisi Market:** Pasar baru buka. Uang pintar sedang mencari pijakan awal. Kita ikut arus momentum terkuat.")
        cols_rek1, cols_rek2 = st.columns([1, 2])
        with cols_rek1:
            st.metric("🎯 Stockpick Sesi Ini", kandidat['ticker'], f"Vol Spike: {kandidat['vol_spike']:.1f}x dari Rata-rata")
        with cols_rek2:
            st.write(f"**💡 Kenapa {kandidat['ticker']}?** Algoritma mendeteksi anomali volume ({kandidat['vol_spike']:.1f} kali lipat dari MA20) tepat di sesi pagi. Ini sinyal jelas bandar sedang agresif HAKA.")
            st.write(f"**⚡ Cara Eksekusi:** *Buy on Momentum* di harga Rp {kandidat['harga']:,.0f}. Gunakan porsi 30%. Siapkan jari di tombol *Sell* untuk taking profit cepat (1-3%). Jika harga mendadak turun di bawah Rp {kandidat['vwap']:,.0f} (VWAP), langsung Cut Loss!")

    elif "Siang" in status_waktu:
        kandidat_valid = [x for x in top_3 if x['rsi'] < 60]
        kandidat = min(kandidat_valid, key=lambda x: abs(x['harga'] - x['vwap'])) if kandidat_valid else min(top_3, key=lambda x: abs(x['harga'] - x['vwap']))
        jarak_vwap = (abs(kandidat['harga'] - kandidat['vwap']) / kandidat['vwap']) * 100
        
        st.warning("⚠️ **STRATEGI: Buy on Weakness (Jaring Bawah / Cicil VWAP)**")
        st.write("**Kondisi Market:** Volume bursa menipis. Harga rawan *false breakout*. Fokus pada saham yang sedang *pullback* (koreksi sehat) tanpa volume buangan besar.")
        cols_rek1, cols_rek2 = st.columns([1, 2])
        with cols_rek1:
            st.metric("🎯 Stockpick Sesi Ini", kandidat['ticker'], f"Jarak VWAP: {jarak_vwap:.1f}% | RSI: {kandidat['rsi']:.0f}")
        with cols_rek2:
            st.write(f"**💡 Kenapa {kandidat['ticker']}?** RSI sudah *cooling down* ({kandidat['rsi']:.0f}) menandakan tekanan jual ritel mulai habis. Harganya (Rp {kandidat['harga']:,.0f}) sangat presisi merapat ke area Ekuilibrium Bandar (VWAP: Rp {kandidat['vwap']:,.0f}).")
            st.write(f"**⚡ Cara Eksekusi:** Antre beli (Pasang *Bid*) di sekitar garis VWAP (Rp {kandidat['vwap']:,.0f}). Jangan dikejar ke atas. Risiko *downside* di area ini sangat kecil.")

    else:
        kandidat = min(top_3, key=lambda x: (x['high_today'] - x['harga']) / x['high_today'] if x['high_today'] > 0 else 1)
        jarak_pucuk = ((kandidat['high_today'] - kandidat['harga']) / kandidat['high_today']) * 100 if kandidat['high_today'] > 0 else 0
        
        st.info("📊 **STRATEGI: Beli Sore Jual Pagi (BSJP) & Pre-Closing Mark-up**")
        st.write("**Kondisi Market:** Persiapan *window dressing* harian institusi. Kita mencari saham yang diakumulasi sejak pagi dan tidak ada guyuran distribusi menjelang tutup.")
        cols_rek1, cols_rek2 = st.columns([1, 2])
        with cols_rek1:
            st.metric("🎯 Stockpick Sesi Ini", kandidat['ticker'], f"Kedekatan High: -{jarak_pucuk:.1f}%")
        with cols_rek2:
            st.write(f"**💡 Kenapa {kandidat['ticker']}?** Terdeteksi anomali! Harga saat ini (Rp {kandidat['harga']:,.0f}) dijaga sangat ketat oleh *market maker*, nyaris menyentuh harga tertinggi hariannya (Rp {kandidat['high_today']:,.0f}). Tidak ada *profit taking* berarti sore ini.")
            st.write(f"**⚡ Cara Eksekusi:** Beli di rentang jam 15:45 - 15:55 WIB. Tahan (*Hold*). Jual esok hari saat sesi *pre-opening* atau 10 menit pertama jam perdagangan saat *bid* mulai ditebalkan.")

    st.markdown("---")

# --- UI MAIN: DEEP DIVE ANALISIS ---
# 4. UBAH KE st.session_state.ticker_utama
st.subheader(f"🔎 Deep Dive Analisis: {st.session_state.ticker_utama}")

df_5m, df_1d = get_market_data(st.session_state.ticker_utama)

if not df_5m.empty and not df_1d.empty:
    
    # Injeksi Real-time Engine & Manual Override
    if harga_manual > 0:
        df_5m.loc[df_5m.index[-1], 'Close'] = float(harga_manual)
        st.success(f"⚡ **Manual Override Active:** Menggunakan harga input pengguna (Rp {harga_manual:,.0f})")
    else:
        harga_realtime_deep = ambil_harga_realtime(st.session_state.ticker_utama)
        if harga_realtime_deep and harga_realtime_deep > 0:
            df_5m.loc[df_5m.index[-1], 'Close'] = harga_realtime_deep
            st.success(f"⚡ **Auto Real-time Active:** Tersinkronisasi dengan Live Market API (Rp {harga_realtime_deep:,.0f})")
        else:
            st.warning("⚠️ **Mode Delay Active:** Gagal sinkronisasi API. Menggunakan data yfinance (Delay 15 Menit).")
        
    df_5m = calculate_indicators(df_5m)
    df_clean = df_5m.dropna(subset=['VWAP', 'EMA20', 'Turnover_MA20'])
    
    if df_clean.empty:
        st.warning("Data kurang atau saham baru IPO/Suspen.")
    else:
        curr_5m = df_clean.iloc[-1]
        entry = float(curr_5m['Close'])
        
        if entry <= 50:
            st.error("🚨 SAHAM GOCAP (Rp 50): Sistem dihentikan demi keselamatan portofolio.")
            st.stop()
            
        ma20_daily = df_1d['Close'].rolling(20).mean().iloc[-1]
        tren_harian = "UPTREND 🟢" if df_1d['Close'].iloc[-1] > ma20_daily else "DOWNTREND 🔴"
        
        close_kemarin = float(df_1d['Close'].iloc[-2]) if len(df_1d) > 1 else entry
        persen_kenaikan = ((entry - close_kemarin) / close_kemarin) * 100 if close_kemarin > 0 else 0
        
        # Batas ARA / ARB
        batas_ara, batas_arb = hitung_batas_ara_arb(close_kemarin)
        
        atr_daily = calculate_daily_atr(df_1d)
        atr_final = atr_daily if atr_daily > 0 else (float(curr_5m['ATR']) * 5)
        
        # Stop Loss & Take Profit logic
        sl_mentah = entry - (atr_final * 1.0)
        sl = sesuaikan_fraksi_bei(sl_mentah, 'sl')
        if sl <= batas_arb: sl = batas_arb
            
        batas_tp_min = entry * (1 + fee_broker + 0.005) 
        tp1_mentah = entry + (float(curr_5m['ATR']) * 3.0) 
        if tp1_mentah < batas_tp_min: tp1_mentah = batas_tp_min
        
        tp2_mentah = entry + (atr_final * 0.5) 
        if tp2_mentah <= tp1_mentah: tp2_mentah = tp1_mentah + (float(curr_5m['ATR']) * 3.0)
            
        tp1 = sesuaikan_fraksi_bei(tp1_mentah, 'tp')
        tp2 = sesuaikan_fraksi_bei(tp2_mentah, 'tp')
        
        if tp1 > batas_ara: tp1 = batas_ara
        if tp2 > batas_ara: tp2 = batas_ara
        
        # Safe Lot Management
        jarak_sl_rp = entry - sl
        lot_by_risk = int(((modal_trading * risiko_persen) / max(1, jarak_sl_rp)) / 100) if jarak_sl_rp > 0 else 0
        
        rata_volume_pasar_lot = float(curr_5m['Vol_MA20']) / 100
        lot_by_liquidity = int(rata_volume_pasar_lot * 0.05) 
        total_lot = min(lot_by_risk, lot_by_liquidity)
        
        turnover_5m_rata_rata = float(curr_5m['Turnover_MA20'])
        
        skor_utama = 0
        if entry > curr_5m['VWAP']: skor_utama += 30
        if entry > curr_5m['EMA20']: skor_utama += 20
        if 40 < curr_5m['RSI'] < 65: skor_utama += 20
        elif curr_5m['RSI'] >= 70: skor_utama -= 20
        
        if curr_5m['Volume'] > (curr_5m['Vol_MA20'] * 3): skor_utama += 30
        elif curr_5m['Volume'] > curr_5m['Vol_MA20']: skor_utama += 10
        
        vwap_val = float(curr_5m['VWAP']) if pd.notnull(curr_5m['VWAP']) else 0
        jarak_vwap_persen = ((entry - vwap_val) / vwap_val * 100) if vwap_val > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tren (Daily)", tren_harian)
        c2.metric("Harga VWAP", f"Rp {vwap_val:,.0f}", f"{jarak_vwap_persen:+.2f}%", delta_color="normal" if entry > vwap_val else "inverse")
        c3.metric("Harga Saat Ini", f"Rp {entry:,.0f}", f"{persen_kenaikan:+.2f}%")
        
        with c4:
            alasan_lot = "Dibatasi Likuiditas" if lot_by_liquidity < lot_by_risk else "Sesuai Risk Profile"
            st.metric("Safe Lot Size", f"{total_lot} Lot", alasan_lot)
            st.metric("Skor Saham", f"{skor_utama} / 100")
        
        tab1, tab2, tab3 = st.tabs(["📊 Eksekusi Order & Net PnL", "📰 Sentimen & Berita", "📖 Rules & Panduan"])
        
        with tab1:
            col_plan, col_rules = st.columns([1.5, 1])
            entry_cicil_1 = sesuaikan_fraksi_bei(entry)
            entry_cicil_2 = sesuaikan_fraksi_bei(vwap_val) if vwap_val > 0 else entry
            if entry_cicil_2 >= entry_cicil_1: entry_cicil_2 = sesuaikan_fraksi_bei(float(curr_5m['EMA20']))

            with col_plan:
                st.markdown("### 🎯 Skenario Entry Anti-Guyur")
                if persen_kenaikan > 5.5 or jarak_vwap_persen > 2.5:
                    st.warning(f"🚨 **RAWAN GUYURAN:** Harga sudah melesat jauh dari rata-rata modal bandar (VWAP).")
                    st.write(f"🔹 **Tranche 1 (Test Water - 30%):** Rp {entry_cicil_1}")
                    st.write(f"🔥 **Tranche 2 (Pullback - 70%):** Rp {entry_cicil_2}")
                else:
                    st.success("✅ **ZONA AKUMULASI AMAN:** Harga merapat ke ekuilibrium market harian.")
                    st.write(f"🔹 **Tranche 1 (Masuk Awal - 50%):** Rp {entry_cicil_1}")
                    st.write(f"🔹 **Tranche 2 (Jaring Bawah - 50%):** Rp {entry_cicil_2}")

                st.markdown("---")
                st.markdown("### 🛡️ Target Realisasi Cuan")
                
                modal_terpakai = entry * total_lot * 100
                if modal_terpakai > 0:
                    jual_tp1_val = tp1 * total_lot * 100
                    estimasi_fee_tp1 = (modal_terpakai + jual_tp1_val) * fee_broker
                    net_rp_tp1 = (jual_tp1_val - modal_terpakai) - estimasi_fee_tp1
                    net_persen_tp1 = (net_rp_tp1 / modal_terpakai) * 100
                    
                    jual_tp2_val = tp2 * total_lot * 100
                    estimasi_fee_turn = (modal_terpakai + jual_tp2_val) * fee_broker
                    net_rp_tp2 = (jual_tp2_val - modal_terpakai) - estimasi_fee_turn
                    net_persen_tp2 = (net_rp_tp2 / modal_terpakai) * 100
                    
                    if net_persen_tp1 <= 0:
                        st.error(f"⚠️ **TP1 (Rp {tp1:,}):** Margin dihabiskan oleh fee broker.")
                    else:
                        st.success(f"🎯 **TP1 (Quick Scalp 50%): Rp {tp1:,}** | Nett: {net_persen_tp1:.1f}% (~Rp {net_rp_tp1:,.0f})")
                        
                    st.info(f"🚀 **TP2 (Swing Intraday): Rp {tp2:,}** | Nett: {net_persen_tp2:.1f}% (~Rp {net_rp_tp2:,.0f})")
                else:
                    st.warning("Lot size 0. Jarak Stop Loss terlalu lebar atau Likuiditas mati.")
                    
                st.error(f"📉 **STOP LOSS STRICT:** Rp {sl:,.0f} *(Batas ARB Hari Ini: Rp {batas_arb:,.0f})*")
                
            with col_rules:
                st.markdown("### 📝 Validasi Real Market")
                if turnover_5m_rata_rata < 100000000:
                    st.error(f"❌ **Saham Ilusi (Low Turnover):** Omset 5 mnt hanya Rp {turnover_5m_rata_rata/1000000:,.1f} Jt. Rawan manipulasi Bid/Offer!")
                elif tren_harian == "DOWNTREND 🔴" and skor_utama >= 60:
                    st.warning("⚠️ **REBOUND PLAY:** Spekulatif pantulan cepat. Wajib Hit & Run!")
                elif tren_harian == "DOWNTREND 🔴": 
                    st.error("❌ **Trend Hancur:** Market membuang emiten ini. Jangan menahan pisau jatuh.")
                elif persen_kenaikan > 8.0: 
                    st.error("❌ **Ekstrem FOMO:** Hindari masuk di zona pucuk harian.")
                else: 
                    st.success("🚀 **Clear for Takeoff:** Momentum dan struktur uptrend valid.")
                    
            st.markdown("---")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_5m.index, open=df_5m['Open'], high=df_5m['High'], low=df_5m['Low'], close=df_5m['Close'], name="Harga"))
            fig.add_trace(go.Scatter(x=df_5m.index, y=df_5m['VWAP'], line=dict(color='#3b82f6', width=2), name='VWAP'))
            fig.update_layout(template="plotly_dark", height=400, xaxis_rangeslider_visible=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader(f"📰 Katalis Media: {st.session_state.ticker_utama}")
            berita_lokal = ambil_berita_indonesia(st.session_state.ticker_utama)
            if berita_lokal:
                for item in berita_lokal:
                    st.markdown(f"🔹 **[{item['title']}]({item['link']})**")
                    st.caption(f"🗞️ Sumber: {item['source']} | 🕒 {item['date']}")
            else:
                st.info("Market hening. Tidak ada sentimen berita penggerak.")
                
        with tab3:
            st.subheader("📖 Panduan Penggunaan & SOP Day Trader BEI")
            
            st.markdown("""
            ### 🎯 5 Langkah Eksekusi Taktis
            1. **Atur Amunisi (Sidebar Kiri):** Masukkan Total Modal yang siap di-tradingkan dan atur batas persentase *Cut Loss* (Risiko). Biarkan sistem menghitung batas lot maksimum yang aman untuk Anda beli.
            2. **Perhatikan Sesi Jam (Indikator Atas):** * **Pagi (09:00 - 10:00 WIB):** Sesi paling agresif. Volatilitas sangat tinggi, cocok untuk eksekusi kilat.
               * **Siang (10:00 - 14:00 WIB):** Rawan *sideways* dan *false breakout*. Disarankan untuk menahan diri (*wait & see*).
               * **Sore (14:00 - 16:00 WIB):** Waktu ideal untuk mencari sinyal akumulasi saham guna strategi Beli Sore Jual Pagi (BSJP).
            3. **Pantau Scanner (Top 3):** Sistem akan menyaring puluhan saham dari Daftar Pantauan untuk memunculkan emiten yang volume intraday-nya sedang diakumulasi oleh uang pintar.
            4. **Deep Dive Emiten:** Ketik kode saham incaran dari daftar *Top 3* ke kolom **Analisis Saham Spesifik** di sidebar kiri untuk membedah target harga terperinci. Gunakan *Bypass Harga Real-Time* jika harga telat (*delay*).
            5. **Eksekusi Order (Aplikasi Sekuritas):** Patuhi **Skenario Entry Anti-Guyur** (disarankan mecicil 2 titik) dan pastikan jumlah lot yang Anda input di sekuritas tidak melebihi rekomendasi **Safe Lot Size**.

            ---
            ### ⚠️ Rules Sistem & Keamanan Portofolio
            * **Keamanan Anti-Ban (Teknis):** Sistem menggunakan eksekusi asinkronus `yfinance` untuk *Scanner* agar server terhindar dari pemblokiran otomatis, sementara bagian analisa mendalam diinjeksi dengan harga presisi *real-time* langsung dari *Google Finance* atau input manual (*Override*).
            * **Disiplin Cut Loss:** Eksekusi Cut Loss di aplikasi Anda tanpa kompromi bila harga penutupan menyentuh angka **Stop Loss Strict**. Jangan pernah melakukan *averaging down* (menangkap pisau jatuh) saat tren harian berstatus *Downtrend*.
            * **Validasi Likuiditas Manual:** Meskipun sistem sudah menyaring saham dengan Turnover minimal Rp 100 Juta, Anda **WAJIB** mengecek ketebalan lot *Bid-Offer* dan *Running Trade* secara langsung di aplikasi sekuritas (seperti Stockbit/Trimegah) sebelum menekan tombol Hajar Kanan (HAKA).
            """)
else:
    st.error("Gagal menarik data. Pastikan format ticker benar (contoh: BBCA) dan koneksi server aktif.")
