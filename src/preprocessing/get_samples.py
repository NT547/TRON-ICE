# =============================
# Module: get_samples.py
# Mục đích: Lấy mẫu dữ liệu từ các file JSON gốc, phục vụ cho việc kiểm thử, huấn luyện mô hình hoặc phân tích nhanh.
# =============================

import ijson
import os
import glob
from src.utils.helper import save_json


def load_sampled_transactions(file_dir: str, limit_per_file: int = 1000):
    """
    Đọc file JSON chứa danh sách giao dịch, lấy ra một số lượng giao dịch đầu tiên (theo limit_per_file).
    Thường dùng để lấy mẫu nhỏ từ file lớn để kiểm thử hoặc huấn luyện nhanh.

    Tham số:
        file_dir (str): Đường dẫn tới file JSON gốc.
        limit_per_file (int): Số lượng giao dịch muốn lấy mẫu.

    Trả về:
        List các giao dịch mẫu (dạng dict).
    """
    sampled_data = []

    if not os.path.exists(file_dir):
        return sampled_data

    try:
        with open(file_dir, "r", encoding="utf-8") as f:
            for i, tx in enumerate(ijson.items(f, "item")):
                sampled_data.append(tx)

                if i + 1 >= limit_per_file:
                    break

        print(f"  ✅ {file_dir}: Lấy {len(sampled_data)} giao dịch đầu tiên.")

    except Exception as e:
        print(f"  ❌ Lỗi khi đọc {file_dir}: {e}")

    print("-" * 50)
    return sampled_data


def exacting_samples(data_dir=None, samples_dir=None):
    """
    Duyệt toàn bộ các file JSON trong thư mục data/raw/ (hoặc thư mục chỉ định), lấy mẫu dữ liệu từ mỗi file,
    và lưu ra file mới trong thư mục samples_dir (mặc định: data/samples/).

    Tham số:
        data_dir (str): Thư mục chứa file JSON gốc.
        samples_dir (str): Thư mục lưu file mẫu.
    """
    if data_dir is None:
        data_dir = "data/raw/"
    if samples_dir is None:
        samples_dir = "data/samples/"

    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    if not json_files:
        print(f"⚠️ Không tìm thấy file .json nào trong {data_dir}")
        return

    for json_file in json_files:
        file_name = os.path.basename(json_file).removesuffix(".json")

        data = load_sampled_transactions(json_file, limit_per_file=1000)

        save_json(file_name=f"{samples_dir}{file_name}_samples", data=data)
