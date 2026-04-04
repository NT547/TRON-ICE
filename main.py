import argparse
from src.data_collection.scraper_trongrid import scaping_trongrid


def main():
    #python main.py --service fixedfloat --year 2025 #get data for fixedfloat in 2025
    
    parser = argparse.ArgumentParser(description="Run Trongrid scraper")

    parser.add_argument(
        "--service",
        type=str,
        required=True,
        choices=["changenow", "fixedfloat", "sideshift"],
        help="Service name (changenow, fixedfloat, sideshift)"
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
        choices=range(2020, 2026),
        help="Year to scrape (e.g., 2025)"
    )

    args = parser.parse_args()

    scaping_trongrid(
        service=args.service,
        year=args.year
    )


if __name__ == "__main__":
    main()