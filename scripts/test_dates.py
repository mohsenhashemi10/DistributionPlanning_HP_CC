import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from thermal_dnep.utils.dates import (
    jalali_to_gregorian,
    create_timestamp,
)


def main():

    print("Jalali -> Gregorian")
    print(
        "1401/01/01 ->",
        jalali_to_gregorian("1401/01/01")
    )

    print("\nHourly mapping:")

    for hour in [1, 2, 12, 24]:

        timestamp = create_timestamp(
            "1401/01/01",
            hour
        )

        print(
            f"H{hour:02d} -> {timestamp}"
        )


if __name__ == "__main__":
    main()