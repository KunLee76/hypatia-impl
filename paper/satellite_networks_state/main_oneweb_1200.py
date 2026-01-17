# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import math
from main_helper import MainHelper

# Earth radius from WGS72 geodetic system (equatorial radius: 6,378,135 m)
# Note: WGS84 uses 6,378,137 m (2m difference, negligible for LEO orbit calculations)
EARTH_RADIUS = 6378135.0

# GENERATION CONSTANTS

BASE_NAME = "oneweb_1200"
NICE_NAME = "OneWeb-1200"

# OneWeb constellation parameters

ECCENTRICITY = 0.0000001  # Circular orbits are zero, but pyephem does not permit 0, so lowest possible value
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True

################################################################
# The below constants are taken from OneWeb constellation and LoHi paper:
# [1]: LoHi paper - "Scalable Hierarchical Routing for Low Earth Orbit Satellite Networks"
# [2]: OneWeb constellation: 720 satellites, 18 planes, 40 sats/plane
# [3]: ITU filing for OneWeb
################################################################

# Calculated from altitude ~1,200 km
# Using Kepler's third law: T = 2π√(a³/μ)
# where a = EARTH_RADIUS + ALTITUDE_M
# Mean motion = 86400 / T (revolutions per day)
MEAN_MOTION_REV_PER_DAY = 13.16  # Calculated from 1200 km altitude
ALTITUDE_M = 1200000  # Altitude 1200 km

# Considering an elevation angle of 30 degrees (similar to Kuiper)
SATELLITE_CONE_RADIUS_M = ALTITUDE_M / math.tan(math.radians(30.0))

MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))

# ISLs are not allowed to dip below 80 km altitude in order to avoid weather conditions
MAX_ISL_LENGTH_M = 2 * math.sqrt(math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2))

# OneWeb constellation configuration
NUM_ORBS = 18  # 18 orbital planes
NUM_SATS_PER_ORB = 40  # 40 satellites per plane
INCLINATION_DEGREE = 87.9  # Near-polar orbit (Walker Polar constellation)

################################################################

main_helper = MainHelper(
        BASE_NAME,
        NICE_NAME,
        ECCENTRICITY,
        ARG_OF_PERIGEE_DEGREE,
        PHASE_DIFF,
        MEAN_MOTION_REV_PER_DAY,
        ALTITUDE_M,
        MAX_GSL_LENGTH_M,
        MAX_ISL_LENGTH_M,
        NUM_ORBS,
        NUM_SATS_PER_ORB,
        INCLINATION_DEGREE,
)


def main():
    args = sys.argv[1:]
    if len(args) != 6 and len(args) != 7 and len(args) != 8:
        print("Must supply exactly six, seven or eight arguments")
        print("Usage: python main_oneweb_1200.py [duration (s)] [time step (ms)] "
              "[isls_plus_grid / isls_none] "
              "[ground_stations_{top_100, paris_moscow_grid}] "
              "[algorithm_{free_one_only_over_isls, free_one_only_gs_relays, "
              "paired_many_only_over_isls, lohi}] "
              "[num threads] [grid_deg (optional, default: 15)] [k_best_gateways (optional, default: 8)]")
        print("")
        print("Examples:")
        print("  # LoHi (uses fixed 6×10 grouping, grid_deg ignored)")
        print("  python main_oneweb_1200.py 20 100 isls_plus_grid "
              "ground_stations_top_100 algorithm_lohi 4")
        print("")
        print("  # Free one only over ISLs")
        print("  python main_oneweb_1200.py 20 100 isls_plus_grid "
              "ground_stations_top_100 algorithm_free_one_only_over_isls 4")
        print("")
        print("  # Hierarchical with custom grid_deg=27, k=8")
        print("  python main_oneweb_1200.py 100 100 isls_plus_grid "
              "ground_stations_top_100 algorithm_hierarchical_virtual_gid 4 27 8")
        print("")
        print("  # Hierarchical with k=999 (All)")
        print("  python main_oneweb_1200.py 100 100 isls_plus_grid "
              "ground_stations_top_100 algorithm_hierarchical_virtual_gid 4 27 999")
        exit(1)
    else:
        # 向下相容：支援 6, 7, 8 個參數
        grid_deg = int(args[6]) if len(args) >= 7 else 15
        k_best_gateways = int(args[7]) if len(args) == 8 else 8
        
        main_helper.calculate(
            "gen_data",
            int(args[0]),
            int(args[1]),
            args[2],
            args[3],
            args[4],
            int(args[5]),
            grid_deg,
            k_best_gateways,
        )


if __name__ == "__main__":
    main()
