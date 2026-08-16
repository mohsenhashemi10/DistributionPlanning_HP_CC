from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src")
)

import pandapower as pp

from thermal_dnep.network.ieee33 import (
    create_ieee33_network,
)


def main():

    net = create_ieee33_network()

    pp.runpp(
        net,
        algorithm="bfsw",
    )

    print("\n=== IEEE 33-BUS TEST ===")

    print(
        f"Number of buses : {len(net.bus)}"
    )

    print(
        f"Number of lines : {len(net.line)}"
    )

    print(
        f"Number of loads : {len(net.load)}"
    )

    print("\nMinimum voltage:")
    print(
        net.res_bus.vm_pu.min()
    )

    print("\nMaximum line loading:")
    print(
        net.res_line.loading_percent.max()
    )


if __name__ == "__main__":
    main()