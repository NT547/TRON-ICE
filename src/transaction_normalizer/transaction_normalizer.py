
import os
import pandas as pd
import ijson
import glob
from src.transaction_normalizer.parser import parse_trc20, parse_trx
from src.utils.configs import HOT_WALLETS

def exact_json_to_csv(file_dir):
    os.makedirs('data/processed/',exist_ok=True)
    if not os.path.exists(file_dir):
        return

    file_name = os.path.basename(file_dir).removesuffix(".json")

    trx_out = f"data/processed/{file_name}.csv"
    trc20_out = f"data/processed/{file_name}.csv"

    batch_trx = []
    batch_trc20 = []
    batch_size = 10000

    first_trx = True
    first_trc20 = True

    with open(file_dir, 'r', encoding='utf-8') as file:
        for tx in ijson.items(file, 'item'):
            for service, wallets in HOT_WALLETS.items():
                if service in file_name:
                    parsed = parse_trx(tx)
                    if parsed:
                        parsed['service'] = service
                        batch_trx.append(parsed)

                    parsed = parse_trc20(tx)
                    if parsed:
                        parsed['service'] = service
                        batch_trc20.append(parsed)
            
            
            
                    
            # ghi batch
            if len(batch_trx) >= batch_size:
                pd.DataFrame(batch_trx).to_csv(
                    trx_out, mode='a', index=False, header=first_trx
                )
                first_trx = False
                batch_trx.clear()

            if len(batch_trc20) >= batch_size:
                pd.DataFrame(batch_trc20).to_csv(
                    trc20_out, mode='a', index=False, header=first_trc20
                )
                first_trc20 = False
                batch_trc20.clear()

    # ghi phần còn lại
    if batch_trx:
        pd.DataFrame(batch_trx).to_csv(trx_out, mode='a', index=False, header=first_trx)

    if batch_trc20:
        pd.DataFrame(batch_trc20).to_csv(trc20_out, mode='a', index=False, header=first_trc20)

    print("✅ Done") 
    
               
def transaction_normalizer(raw_files:str):
    raw_file_pattern = raw_files
    json_files = glob.glob(os.path.join(raw_file_pattern))
    
    if not json_files:
            log_msg(f"[CẢNH BÁO] Không tìm thấy file dữ liệu nào khớp với {json_files}")
            return {"deposits": [], "withdrawals": []}
    
    # --- THIẾT LẬP GHI LOG ---
    log_dir = "results/logs/normalizer"
    os.makedirs(log_dir, exist_ok=True)
    
    base_name_clean = os.path.basename(json_files[0]).replace(".json", "")
    log_file_path = os.path.join(log_dir, f"normalizer_{base_name_clean}.log")
    with open(log_file_path, "w", encoding="utf-8") as log_file:
        def log_msg(msg: str):
                print(msg)
                log_file.write(msg + "\n")
        
            
        for file_name in json_files:
            log_msg(f"Normalizing {file_name}...")
            exact_json_to_csv(file_dir=file_name)
            
        log_msg("=== HOÀN THÀNH QUÁ TRÌNH CHUẨN HÓA GIAO DỊCH ===")
    