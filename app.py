import streamlit as st
import pandas as pd
import os
from main import run_monitoring_engine

# Konfigurasi halaman utama
st.set_page_config(page_title="Busway Guardian CMS", layout="wide")

# Database CCTV & Koordinat Kamera
DATABASE_CCTV = {
    "CCTV Sudirman - Arah Koridor 1": {
        "video_path": "Sampel_vidio.mp4",
        "kordinat_kanan": [[494, 437], [640, 440], [480, 708], [60, 700]],
        "kordinat_kiri": [[786, 440], [948, 442], [1280, 663], [900, 688]]
    },
    "CCTV Thamrin ": {
        "video_path": "Sampel_thamrin.mp4",
        "kordinat_jalur": [[235, 162], [327, 141], [950, 700], [448, 700]]

    }
}

CSV_FILE = "data_pelanggaran_busway.csv"

# Inisialisasi struktur penyimpanan log data baru dengan kolom Nomor Polisi dan Foto Bukti
if not os.path.exists(CSV_FILE):
    df_init = pd.DataFrame(
        columns=["No", "Waktu Kejadian", "Lokasi Jalur", "Jenis Kendaraan", "Nomor Polisi", "Foto Bukti", "Status"])
    df_init.to_csv(CSV_FILE, index=False)

# LAYOUT SIDEBAR PANEL CONTROL
st.sidebar.title("Busway Guardian v1.2")
st.sidebar.subheader("Management Control Station")

cctv_nama = st.sidebar.selectbox("Pilih Kamera CCTV:", list(DATABASE_CCTV.keys()))
cctv_pilihan = DATABASE_CCTV[cctv_nama]

confidence_slider = st.sidebar.slider("AI Confidence Threshold", 0.20, 0.90, 0.40, 0.05)

tombol_aktif = st.sidebar.button("AKTIFKAN AI MONITORING", use_container_width=True)
tombol_matikan = st.sidebar.button("MATIKAN SISTEM", use_container_width=True)

if "running" not in st.session_state:
    st.session_state.running = False

if tombol_aktif:
    st.session_state.running = True
if tombol_matikan:
    st.session_state.running = False
    st.rerun()

# LAYOUT ANTARMUKA UTAMA
st.title("Intelligent Traffic Command Center")
st.markdown(f"**Live Feed Monitoring:** {cctv_nama}")
st.write("---")

# Membagi kolom: Kiri untuk Video & Tabel, Kanan untuk Validasi Manual Petugas
col_video, col_validation = st.columns([2, 1])

with col_video:
    frame_placeholder = st.empty()
    st.subheader("Log Riwayat Pelanggaran Terbaru (Live)")
    table_placeholder = st.empty()

with col_validation:
    st.subheader("Panel Validasi Petugas")
    image_preview_placeholder = st.empty()

    # Form input nomor polisi untuk petugas
    with st.form("validation_form", clear_on_submit=True):
        nopol_input = st.text_input("Input Nomor Polisi Kendaraan:")
        submit_button = st.form_submit_button("Simpan Data Verifikasi")

    st.write("---")
    st.subheader("Statistik Berjalan")
    metric_counter = st.empty()
    st.success("STATUS: CONNECTED (RTSP/LIVE)")

# Membaca data terbaru untuk ditampilkan pada komponen preview kanan
df_check = pd.read_csv(CSV_FILE)

if len(df_check) > 0:
    # Mengambil baris terakhir yang status nopol-nya masih membutuhkan verifikasi
    pending_rows = df_check[df_check["Nomor Polisi"] == "NEED VALIDATION"]
    if not pending_rows.empty:
        last_pending = pending_rows.iloc[-1]
        target_no = last_pending["No"]
        img_path = last_pending["Foto Bukti"]

        if os.path.exists(img_path):
            image_preview_placeholder.image(img_path,
                                            caption=f"Pelanggaran No: {target_no} | Jenis: {last_pending['Jenis Kendaraan']}",
                                            use_container_width=True)

        # Logika ketika petugas menekan tombol simpan verifikasi
        if submit_button and nopol_input:
            df_check.loc[df_check["No"] == target_no, "Nomor Polisi"] = nopol_input.upper()
            df_check.to_csv(CSV_FILE, index=False)
            st.toast(f"Data Pelanggaran No {target_no} Berhasil Diverifikasi!", icon="✅")
            time.sleep(0.5)
            st.rerun()
    else:
        image_preview_placeholder.info("Semua data pelanggaran saat ini telah diverifikasi oleh petugas.")
else:
    image_preview_placeholder.info("Belum ada data capture pelanggaran masuk.")

# KONDISI EKSEKUSI JALANNYA ENGINES
if st.session_state.running:
    run_monitoring_engine(
        cctv_config=cctv_pilihan,
        confidence_threshold=confidence_slider,
        csv_file=CSV_FILE,
        frame_placeholder=frame_placeholder,
        metric_counter=metric_counter,
        table_placeholder=table_placeholder,
        get_status=lambda: st.session_state.running
    )
else:
    frame_placeholder.info(
        "Sistem Nonaktif. Klik tombol 'AKTIFKAN AI MONITORING' pada sidebar untuk memulai analisa CCTV.")
    df_standby = pd.read_csv(CSV_FILE)
    table_placeholder.dataframe(df_standby.tail(10), use_container_width=True)
    metric_counter.metric(label="TOTAL PELANGGARAN TERDETEKSI", value=f"{len(df_standby)} Unit")