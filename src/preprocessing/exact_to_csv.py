# =============================
# Module: exact_to_csv.py
# Mục đích: Tiền xử lý dữ liệu JSON gốc, chuyển đổi sang CSV, lọc và phân loại giao dịch TRX/TRC20 theo từng dịch vụ (service)
# =============================

import os
import pandas as pd
import ijson
import glob
from src.processing.parser import parse_trc20, parse_trx
from src.utils.configs import HOT_WALLETS


def exact_json_to_csv(file_dir):
    """
    Đọc file JSON chứa danh sách giao dịch, phân tích từng giao dịch, lọc theo từng dịch vụ (service) dựa vào HOT_WALLETS,
    phân loại thành giao dịch TRX và TRC20, sau đó ghi ra file CSV theo từng loại.

    Tham số:
        file_dir (str): Đường dẫn tới file JSON gốc.

    Đầu ra:
        - Tạo file CSV trong data/processed/ chứa các giao dịch đã được phân tích, mỗi dòng là một giao dịch.
    """
    os.makedirs("data/processed/", exist_ok=True)
    if not os.path.exists(file_dir):
        return

    file_name = os.path.basename(file_dir).removesuffix(".json")

    trx_out = f"data/processed/{file_name}.csv"
    trc20_out = f"data/processed/{file_name}.csv"

    batch_trx = []  # Lưu tạm các giao dịch TRX để ghi theo lô
    batch_trc20 = []  # Lưu tạm các giao dịch TRC20 để ghi theo lô
    batch_size = 10000  # Số lượng giao dịch ghi mỗi lần

    first_trx = True  # Đánh dấu lần ghi đầu tiên để ghi header
    first_trc20 = True

    with open(file_dir, "r", encoding="utf-8") as file:
        for tx in ijson.items(file, "item"):
            # Duyệt qua từng dịch vụ, kiểm tra file thuộc dịch vụ nào
            for service, wallets in HOT_WALLETS.items():
                if service in file_name:
                    # Phân tích giao dịch TRX
                    parsed = parse_trx(tx)
                    if parsed:
                        parsed["service"] = service
                        batch_trx.append(parsed)

                    # Phân tích giao dịch TRC20
                    parsed = parse_trc20(tx)
                    if parsed:
                        parsed["service"] = service
                        batch_trc20.append(parsed)

            # Khi đủ batch_size thì ghi ra file để tránh tràn bộ nhớ
            if len(batch_trx) >= batch_size:
                pd.DataFrame(batch_trx).to_csv(
                    trx_out, mode="a", index=False, header=first_trx
                )
                first_trx = False
                batch_trx.clear()

            if len(batch_trc20) >= batch_size:
                pd.DataFrame(batch_trc20).to_csv(
                    trc20_out, mode="a", index=False, header=first_trc20
                )
                first_trc20 = False
                batch_trc20.clear()

    # Ghi nốt phần còn lại nếu chưa đủ batch_size
    if batch_trx:
        pd.DataFrame(batch_trx).to_csv(trx_out, mode="a", index=False, header=first_trx)

    if batch_trc20:
        pd.DataFrame(batch_trc20).to_csv(
            trc20_out, mode="a", index=False, header=first_trc20
        )

    print("✅ Done")


def exact_csv_by_service(data_dir=None):
    """
    Hàm tiện ích: Duyệt toàn bộ các file JSON trong thư mục data/raw/ (hoặc thư mục chỉ định),
    chuyển đổi từng file sang CSV bằng hàm exact_json_to_csv.

    Tham số:
        data_dir (str): Thư mục chứa các file JSON gốc.
    """
    if data_dir is None:
        data_dir = "data/raw/"

    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    for file_name in json_files:
        print(f"Exacting {file_name} to .csv")
        exact_json_to_csv(file_dir=file_name)
