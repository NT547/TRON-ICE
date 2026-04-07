import os
import pandas as pd
import ijson
import glob
from src.utils.helper import parse_trc20,parse_trx
def exact_json_to_csv(file_dir):
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

            trx = parse_trx(tx)
            if trx:
                batch_trx.append(trx)

            trc20 = parse_trc20(tx)
            if trc20:
                batch_trc20.append(trc20)

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
    
               
def exact_csv_by_service(data_dir=None):
    if data_dir is None:
        data_dir = "data/raw/"  

    json_files = glob.glob(os.path.join(data_dir, "*.json"))

    for file_name in json_files:
        print(f"Exacting {file_name} to .csv")
        exact_json_to_csv(file_dir=file_name)
    