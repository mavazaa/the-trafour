import cv2
import numpy as np
from ultralytics import YOLO
import pandas as pd
from datetime import datetime
import time
import os


def run_monitoring_engine(cctv_config, confidence_threshold, csv_file, frame_placeholder, metric_counter,
                          table_placeholder, get_status):
    """
    Engine Hybrid CPU-Optimized dengan teknik Frame Skipping agar tidak patah-patah.
    """
    IMAGE_DIR = "captured_evidences"
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(cctv_config["video_path"])

    is_dual_lane = "kordinat_kanan" in cctv_config and "kordinat_kiri" in cctv_config

    if is_dual_lane:
        pts_kanan = np.array(cctv_config["kordinat_kanan"], np.int32).reshape((-1, 1, 2))
        pts_kiri = np.array(cctv_config["kordinat_kiri"], np.int32).reshape((-1, 1, 2))
    else:
        pts_jalur = np.array(cctv_config["kordinat_jalur"], np.int32).reshape((-1, 1, 2))

    last_log_kanan = 0
    last_log_kiri = 0
    last_log_tunggal = 0
    cooldown_seconds = 2

    #VARIABEL OPTIMASI CPU
    frame_count = 0
    skip_frames = 3  # AI hanya mendeteksi setiap 3 frame sekali (Menghemat beban CPU 66%)

    while cap.isOpened() and get_status():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret: break

        frame_count += 1
        frame = cv2.resize(frame, (1280, 720))
        current_time = time.time()

        # Gambar Poligon Visual (Selalu digambar di setiap frame agar mulus)
        if is_dual_lane:
            cv2.polylines(frame, [pts_kanan], isClosed=True, color=(255, 0, 0), thickness=2)
            cv2.polylines(frame, [pts_kiri], isClosed=True, color=(0, 165, 255), thickness=2)
        else:
            cv2.polylines(frame, [pts_jalur], isClosed=True, color=(255, 255, 0), thickness=2)

        # Proses deteksi YOLO HANYA dijalankan pada frame kelipatan skip_frames
        if frame_count % skip_frames == 0:
            results = model(frame, classes=[2, 3, 5, 7], conf=confidence_threshold, verbose=False)

            df_current = pd.read_csv(csv_file)
            total_pelanggaran = len(df_current)

            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    label_name = model.names[int(box.cls[0])]
                    cx, cy = int((x1 + x2) / 2), y2

                    inside_kanan, inside_kiri, inside_tunggal = -1, -1, -1
                    if is_dual_lane:
                        inside_kanan = cv2.pointPolygonTest(pts_kanan, (cx, cy), False)
                        inside_kiri = cv2.pointPolygonTest(pts_kiri, (cx, cy), False)
                    else:
                        inside_tunggal = cv2.pointPolygonTest(pts_jalur, (cx, cy), False)

                    if (inside_kanan >= 0 or inside_kiri >= 0 or inside_tunggal >= 0) and label_name in ['car',
                                                                                                         'motorcycle',
                                                                                                         'truck']:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        cv2.putText(frame, f"PELANGGARAN: {label_name.upper()}", (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                        waktu_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
                        trigger_save = False
                        lajur = ""

                        if inside_tunggal >= 0 and (current_time - last_log_tunggal > cooldown_seconds):
                            lajur = "KORIDOR UTAMA (LAJUR TUNGGAL)"
                            last_log_tunggal = current_time
                            trigger_save = True
                        elif inside_kanan >= 0 and (current_time - last_log_kanan > cooldown_seconds):
                            lajur = "ZONA ARAH A (LAJUR KANAN)"
                            last_log_kanan = current_time
                            trigger_save = True
                        elif inside_kiri >= 0 and (current_time - last_log_kiri > cooldown_seconds):
                            lajur = "ZONA ARAH B (LAJUR KIRI)"
                            last_log_kiri = current_time
                            trigger_save = True

                        if trigger_save:
                            total_pelanggaran += 1
                            filename = f"PELANGGAR_{timestamp_file}_{total_pelanggaran}.jpg"
                            filepath = os.path.join(IMAGE_DIR, filename)

                            crop_img = frame[max(0, y1 - 20):min(720, y2 + 20), max(0, x1 - 20):min(1280, x2 + 20)]
                            if crop_img.size > 0:
                                cv2.imwrite(filepath, crop_img)

                            new_row = pd.DataFrame(
                                [[total_pelanggaran, waktu_str, lajur, label_name.upper(), "NEED VALIDATION", filepath,
                                  "TILANG ELEKTRONIK"]],
                                columns=df_current.columns)
                            new_row.to_csv(csv_file, mode='a', header=False, index=False)

                    elif (inside_kanan >= 0 or inside_kiri >= 0 or inside_tunggal >= 0) and label_name == 'bus':
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Output render ke Streamlit UI
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)

        # Ambil data statistik untuk metrik & tabel bawah
        df_live = pd.read_csv(csv_file)
        metric_counter.metric(label="TOTAL PELANGGARAN TERDETEKSI", value=f"{len(df_live)} Unit")
        table_placeholder.dataframe(df_live.tail(10), use_container_width=True)

        time.sleep(0.01)

    cap.release()