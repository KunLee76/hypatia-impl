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
sys.path.append("../../satgenpy")
import satgen
import os
import shutil


class MainHelper:

    def __init__(
            self,
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
    ):
        self.BASE_NAME = BASE_NAME
        self.NICE_NAME = NICE_NAME
        self.ECCENTRICITY = ECCENTRICITY
        self.ARG_OF_PERIGEE_DEGREE = ARG_OF_PERIGEE_DEGREE
        self.PHASE_DIFF = PHASE_DIFF
        self.MEAN_MOTION_REV_PER_DAY = MEAN_MOTION_REV_PER_DAY
        self.ALTITUDE_M = ALTITUDE_M
        self.MAX_GSL_LENGTH_M = MAX_GSL_LENGTH_M
        self.MAX_ISL_LENGTH_M = MAX_ISL_LENGTH_M
        self.NUM_ORBS = NUM_ORBS
        self.NUM_SATS_PER_ORB = NUM_SATS_PER_ORB
        self.INCLINATION_DEGREE = INCLINATION_DEGREE

    def calculate(
            self,
            output_generated_data_dir,      # Final directory in which the result will be placed
            duration_s,
            time_step_ms,
            isl_selection,            # isls_{none, plus_grid}
            gs_selection,             # ground_stations_{top_100, paris_moscow_grid}
            dynamic_state_algorithm,  # algorithm_{free_one_only_{gs_relays,_over_isls}, paired_many_only_over_isls, hierarchical}
            num_threads,
            grid_deg=27,              # Grid degree for hierarchical algorithms (default: 27)
            k_best_gateways=8         # K-best gateways for hierarchical_virtual_gid (default: 8, 999=all)
    ):

        # Add base name to setting
        name = self.BASE_NAME + "_" + isl_selection + "_" + gs_selection + "_" + dynamic_state_algorithm
        
        # 如果是需要 grid_deg 的演算法，在名稱加上 grid_deg 後綴
        # 注意：algorithm_lohi 不使用 grid_deg，使用固定的 6×10 平面區塊分群
        if "hierarchical_virtual_gid" in dynamic_state_algorithm.lower():
            name += f"_{grid_deg}deg_k{k_best_gateways}"
            # 設定環境變數，讓演算法讀取
            os.environ['SATGEN_GRID_DEG'] = str(grid_deg)
            os.environ['K_BEST_GATEWAYS'] = str(k_best_gateways)
            print(f"[GID] Setting grid degree to {grid_deg}° and K-best to {k_best_gateways} for hierarchical GID algorithm")
        elif "hierarchical" in dynamic_state_algorithm.lower() and "lohi" not in dynamic_state_algorithm.lower():
            # 其他 hierarchical 演算法也可能需要 grid_deg
            name += f"_{grid_deg}deg"
            os.environ['SATGEN_GRID_DEG'] = str(grid_deg)
            print(f"[Hierarchical] Setting grid degree to {grid_deg}°")
        elif "lohi" in dynamic_state_algorithm.lower():
            # LoHi 使用固定的 p×s (6×10) 分群，不需要 grid_deg
            print(f"[LoHi] Using fixed 6×10 plane-block grouping (grid_deg parameter ignored)")
        else:
            # 非階層化演算法不需要 grid_deg
            print(f"[{dynamic_state_algorithm}] No grouping parameter needed")

        # Create output directories
        if not os.path.isdir(output_generated_data_dir):
            os.makedirs(output_generated_data_dir, exist_ok=True)
        if not os.path.isdir(output_generated_data_dir + "/" + name):
            os.makedirs(output_generated_data_dir + "/" + name, exist_ok=True)

        # Ground stations
        print("Generating ground stations...")
        if gs_selection == "ground_stations_top_100":
            satgen.extend_ground_stations(
                "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt",
                output_generated_data_dir + "/" + name + "/ground_stations.txt"
            )
        elif gs_selection == "ground_stations_top_100_with_hsinchu":
            satgen.extend_ground_stations(
                "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100_with_hsinchu.basic.txt",
                output_generated_data_dir + "/" + name + "/ground_stations.txt"
            )
        elif gs_selection == "ground_stations_paris_moscow_grid":
            satgen.extend_ground_stations(
                "input_data/ground_stations_paris_moscow_grid.basic.txt",
                output_generated_data_dir + "/" + name + "/ground_stations.txt"
            )
        else:
            raise ValueError("Unknown ground station selection: " + gs_selection)

        # TLEs
        print("Generating TLEs...")
        # Auto-detect: polar version for 80° < inc < 100°, original for others
        # Starlink (53°) → original, OneWeb (87.9°) → polar
        satgen.generate_tles_from_scratch_manual(
            output_generated_data_dir + "/" + name + "/tles.txt",
            self.NICE_NAME,
            self.NUM_ORBS,
            self.NUM_SATS_PER_ORB,
            self.PHASE_DIFF,
            self.INCLINATION_DEGREE,
            self.ECCENTRICITY,
            self.ARG_OF_PERIGEE_DEGREE,
            self.MEAN_MOTION_REV_PER_DAY,
            use_polar_version=None  # Auto-detect based on inclination
        )

        # ISLs
        print("Generating ISLs...")
        if isl_selection == "isls_plus_grid":
            # Auto-detect: polar version for 80° < inc < 100°, original for others
            # Starlink (53°) → original (circular wrap), OneWeb (87.9°) → polar (seam handling)
            satgen.generate_plus_grid_isls(
                output_generated_data_dir + "/" + name + "/isls.txt",
                self.NUM_ORBS,
                self.NUM_SATS_PER_ORB,
                isl_shift=0,
                idx_offset=0,
                inclination_degree=self.INCLINATION_DEGREE,
                use_polar_version=None  # Auto-detect based on inclination
            )
        elif isl_selection == "isls_none":
            satgen.generate_empty_isls(
                output_generated_data_dir + "/" + name + "/isls.txt"
            )
        elif isl_selection.startswith("isls_failure_"):
            # ISL 失效場景：從預先生成的文件複製
            failure_level = isl_selection.replace("isls_", "")  # 提取 "failure_XX"
            source_file = f"input_data/failure_scenarios/isls_{failure_level}.txt"
            dest_file = output_generated_data_dir + "/" + name + "/isls.txt"
            
            if not os.path.exists(source_file):
                raise FileNotFoundError(f"失效場景文件不存在: {source_file}")
            
            print(f"使用失效場景: {failure_level}")
            print(f"  複製 {source_file} -> {dest_file}")
            
            shutil.copy2(source_file, dest_file)
        elif isl_selection.startswith("isls_random_"):
            # ISL 隨機失效場景：靜態生成（在生成拓撲時就移除固定的 ISL）
            # 格式: isls_random_p1 (1%), isls_random_p5 (5%), isls_random_p10 (10%)
            import re
            match = re.search(r'isls_random_p(\d+)', isl_selection)
            if not match:
                raise ValueError(f"Invalid random failure format: {isl_selection}, expected isls_random_pX where X is 1, 5, or 10")
            
            failure_percent = int(match.group(1))
            failure_probability = failure_percent / 100.0
            random_seed = 42  # 固定種子以確保可重複性
            
            print(f"使用靜態隨機失效場景: {failure_percent}% 失效率 (seed={random_seed})")
            
            satgen.generate_plus_grid_isls_with_random_failures(
                output_generated_data_dir + "/" + name + "/isls.txt",
                self.NUM_ORBS,
                self.NUM_SATS_PER_ORB,
                isl_shift=0,
                failure_probability=failure_probability,
                random_seed=random_seed,
                idx_offset=0,
                inclination_degree=self.INCLINATION_DEGREE,
                use_polar_version=None  # Auto-detect based on inclination
            )
        elif isl_selection.startswith("isls_dynamic_"):
            # ISL 動態失效場景：生成完整的 plus_grid ISL，依賴 Chaos Monkey 動態移除
            # 格式: isls_dynamic_p1, isls_dynamic_p5, isls_dynamic_p10
            # Chaos Monkey 會通過環境變數 CHAOS_FAILURE_RATE 控制失效率
            import re
            match = re.search(r'isls_dynamic_p(\d+)', isl_selection)
            if not match:
                raise ValueError(f"Invalid dynamic failure format: {isl_selection}, expected isls_dynamic_pX where X is 1, 5, or 10")
            
            failure_percent = int(match.group(1))
            print(f"使用動態失效場景: {failure_percent}% 失效率 (依賴 Chaos Monkey)")
            print(f"  生成完整的 plus_grid ISL 拓撲，Chaos Monkey 將動態移除 ISL")
            
            # 生成完整的 ISL 拓撲（與 isls_plus_grid 相同）
            satgen.generate_plus_grid_isls(
                output_generated_data_dir + "/" + name + "/isls.txt",
                self.NUM_ORBS,
                self.NUM_SATS_PER_ORB,
                isl_shift=0,
                idx_offset=0,
                inclination_degree=self.INCLINATION_DEGREE,
                use_polar_version=None  # Auto-detect based on inclination
            )
        else:
            raise ValueError("Unknown ISL selection: " + isl_selection)

        # Description
        print("Generating description...")
        satgen.generate_description(
            output_generated_data_dir + "/" + name + "/description.txt",
            self.MAX_GSL_LENGTH_M,
            self.MAX_ISL_LENGTH_M
        )

        # GSL interfaces
        ground_stations = satgen.read_ground_stations_extended(
            output_generated_data_dir + "/" + name + "/ground_stations.txt"
        )
        if dynamic_state_algorithm == "algorithm_free_one_only_gs_relays" \
                or dynamic_state_algorithm == "algorithm_free_one_only_over_isls" \
                or dynamic_state_algorithm == "algorithm_hierarchical" \
                or dynamic_state_algorithm == "algorithm_hierarchical_virtual_gid" \
                or dynamic_state_algorithm == "algorithm_hierarchical_virtual_gid_dijkstra" \
                or dynamic_state_algorithm == "algorithm_free_one_only_over_isls_with_stats" \
                or dynamic_state_algorithm == "algorithm_lohi":
            # One GSL interface per satellite
            gsl_interfaces_per_satellite = 1
        elif dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":
            gsl_interfaces_per_satellite = len(ground_stations)
        else:
            raise ValueError("Unknown dynamic state algorithm: " + dynamic_state_algorithm)

        print("Generating GSL interfaces info..")
        satgen.generate_simple_gsl_interfaces_info(
            output_generated_data_dir + "/" + name + "/gsl_interfaces_info.txt",
            self.NUM_ORBS * self.NUM_SATS_PER_ORB,
            len(ground_stations),
            gsl_interfaces_per_satellite,  # GSL interfaces per satellite
            1,  # (GSL) Interfaces per ground station
            1,  # Aggregate max. bandwidth satellite (unit unspecified)
            1   # Aggregate max. bandwidth ground station (same unspecified unit)
        )

        # Forwarding state
        print("Generating forwarding state...")
        satgen.help_dynamic_state(
            output_generated_data_dir,
            num_threads,  # Number of threads
            name,
            time_step_ms,
            duration_s,
            self.MAX_GSL_LENGTH_M,
            self.MAX_ISL_LENGTH_M,
            dynamic_state_algorithm,
            True
        )
