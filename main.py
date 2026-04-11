<<<<<<< HEAD

from src.data_collection.scraper_trongrid import scaping_trongrid


if __name__ == "__main__":
    scaping_trongrid()
=======
from src.identify_operations import classify
from src.baseline_algorithm import matching

if __name__ == "__main__":
    # classify()
    matching(input_dir="data/classified", output_dir="data/matched")
>>>>>>> feature/baseline_algorithm
