
import ijson
import os
import glob



from src.utils.helper import save_json


import ijson

def load_sampled_transactions(file_dir: str, limit_per_file: int = 1000):
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


def exacting_samples(data_dir = None, samples_dir = None):
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

        save_json(
            file_name=f"{samples_dir}{file_name}_samples",
            data=data
        )
            
        
        
        
    
    
    