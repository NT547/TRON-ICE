# Phân loại giao dịch thành DEPOSIT và WITHDRAWAL dựa trên danh sách hot wallets của từng service
# Ghi các file phân loại vào thư mục data/classified/{service}_deposits.csv và {service}_withdrawals.csv
import pandas as pd
import os
import glob
from src.config import HOT_WALLETS


def identify_operations(chunk: pd.DataFrame):
    chunk = chunk.copy()
    chunk["to"] = chunk["to"].str.lower()
    chunk["from"] = chunk["from"].str.lower()

    # flatten wallet → service
    wallet_to_service = {}
    for service, wallets in HOT_WALLETS.items():
        for wallet in wallets:
            wallet_to_service[wallet.lower()] = service

    # map trực tiếp
    to_service = chunk["to"].map(wallet_to_service)
    from_service = chunk["from"].map(wallet_to_service)

    deposits = chunk[chunk["service"] == to_service]
    withdrawals = chunk[chunk["service"] == from_service]

    return deposits, withdrawals



def classify(csv_direction = None, classified_direction = None, pattern = None):
    csv_direction = "data/processed/" if csv_direction is None else csv_direction
    classified_direction = "data/classified/" if classified_direction is None else classified_direction
    pattern = "*.csv" if pattern is None else pattern
    
    # Checking and creating directory 
    os.makedirs(csv_direction, exist_ok=True)
    os.makedirs(classified_direction, exist_ok=True)
    
    try:
        csv_path = f"data/processed/"
        csv_files = glob.glob(os.path.join(csv_path,pattern))

                
        for csv_file in csv_files:
            #Exacting file name
            file_name = str(os.path.basename(csv_file))
            file_name = file_name.removesuffix('.csv')
            file_name = file_name.replace('trongrid_','')
            
            #file direction that saved deposits and withdrawals
            deposit_dir = f"data/classified/{file_name}_deposits.csv"
            withdrawals_dir = f"data/classified/{file_name}_withdrawals.csv"
            
            #load data by chunk
            transaction_chunks = pd.read_csv(csv_file,chunksize=10000)
            
            #
            deposits_chunk = []
            withdrawals_chunk = []
            for transaction_chunk in transaction_chunks:
                
                deposits_chunk, withdrawals_chunk = identify_operations(transaction_chunk)
                deposits_chunk['transaction_type'] = 'deposit'
                withdrawals_chunk['transaction_type'] = ' withdrawal'
                

                if not deposits_chunk.empty:
                    deposits_chunk.to_csv(deposit_dir ,index=False, mode='a',header=not os.path.exists(deposit_dir))
                if not withdrawals_chunk.empty:
                    withdrawals_chunk.to_csv(withdrawals_dir, index=False, mode='a',header=not os.path.exists(withdrawals_dir))
             
                    
            #saving log
            message = f"""Deposits: {len(deposits_chunk)}" 
                        Withdrawals: {len(withdrawals_chunk)}
                        💾 Deposits Saved in {deposit_dir}
                        💾 Withdraw Saved in {withdrawals_dir}\n"""  
            print(message)
            log_path = "result/logs/processing"
            os.makedirs(log_path, exist_ok=True)
            log_file = f'{log_path}/classified.log'
            with open (log_file,'w',encoding='utf-8') as file:
                file.write(message)
                
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")

