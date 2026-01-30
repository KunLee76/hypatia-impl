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


def generate_plus_grid_isls_original(output_filename_isls, n_orbits, n_sats_per_orbit, isl_shift, idx_offset=0):
    """
    Original (baseline) version: treats all constellations uniformly.
    Adjacent orbit wrapping: always ((i + 1) % n_orbits) for all inclinations.
    
    Used for: Starlink, Kuiper, Telesat (non-polar constellations).

    :param output_filename_isls     Output filename
    :param n_orbits:                Number of orbits
    :param n_sats_per_orbit:        Number of satellites per orbit
    :param isl_shift:               ISL shift between orbits (e.g., if satellite id in orbit is X,
                                    does it also connect to the satellite at X in the adjacent orbit)
    :param idx_offset:              Index offset (e.g., if you have multiple shells)
    """

    if n_orbits < 3 or n_sats_per_orbit < 3:
        raise ValueError("Number of x and y must each be at least 3")

    list_isls = []
    for i in range(n_orbits):
        for j in range(n_sats_per_orbit):
            sat = i * n_sats_per_orbit + j

            # Link to the next in the orbit
            sat_same_orbit = i * n_sats_per_orbit + ((j + 1) % n_sats_per_orbit)
            sat_adjacent_orbit = ((i + 1) % n_orbits) * n_sats_per_orbit + ((j + isl_shift) % n_sats_per_orbit)

            # Same orbit
            list_isls.append((idx_offset + min(sat, sat_same_orbit), idx_offset + max(sat, sat_same_orbit)))

            # Adjacent orbit
            list_isls.append((idx_offset + min(sat, sat_adjacent_orbit), idx_offset + max(sat, sat_adjacent_orbit)))

    with open(output_filename_isls, 'w+') as f:
        for (a, b) in list_isls:
            f.write(str(a) + " " + str(b) + "\n")

    return list_isls


def generate_plus_grid_isls_polar(output_filename_isls, n_orbits, n_sats_per_orbit, inclination_degree, isl_shift, idx_offset=0):
    """
    Polar-optimized version: handles polar constellation ISL wiring specially.
    
    For polar (80° < inc < 100°): 
        - Last orbit wraps to first with split reverse mapping at poles
        - This avoids excessive ISL length variations at polar regions
    
    For delta (all other): 
        - Standard circular wrapping ((i + 1) % n_orbits)
    
    Used for: OneWeb (87.9°), polar experimental constellations.

    :param output_filename_isls     Output filename
    :param n_orbits:                Number of orbits
    :param n_sats_per_orbit:        Number of satellites per orbit
    :param inclination_degree:      Inclination to decide constellation type
    :param isl_shift:               ISL shift between orbits
    :param idx_offset:              Index offset (e.g., if you have multiple shells)
    """

    if n_orbits < 3 or n_sats_per_orbit < 3:
        raise ValueError("Number of x and y must each be at least 3")

    # Determine constellation type
    constellation_type = (
        "polar"
        if 80.0 < inclination_degree < 100.0
        else "delta"
    )

    list_isls = []
    half = n_sats_per_orbit // 2

    for i in range(n_orbits):
        for j in range(n_sats_per_orbit):
            sat = i * n_sats_per_orbit + j

            # Same-orbit (horizontal) link
            sat_same_orbit = i * n_sats_per_orbit + ((j + 1) % n_sats_per_orbit)
            list_isls.append((
                idx_offset + min(sat, sat_same_orbit),
                idx_offset + max(sat, sat_same_orbit)
            ))

            # Compute adjacent-orbit link based on constellation type
            if constellation_type == "delta":
                # Delta: always connect to next orbit with forward shift
                next_orbit = (i + 1) % n_orbits
                offset_j = (j + isl_shift) % n_sats_per_orbit
            else:
                # Polar constellation
                if i < n_orbits - 1:
                    next_orbit = i + 1
                    offset_j = (j + isl_shift) % n_sats_per_orbit
                else:
                    # Last orbit wraps to first with split reverse mapping
                    next_orbit = 0
                    if j < half:
                        # first half reversed
                        base_idx = half - j - 1
                    else:
                        # second half reversed after half
                        base_idx = n_sats_per_orbit + half - j - 1
                    # apply shift
                    offset_j = (base_idx + isl_shift) % n_sats_per_orbit

            sat_adjacent_orbit = next_orbit * n_sats_per_orbit + offset_j
            list_isls.append((
                idx_offset + min(sat, sat_adjacent_orbit),
                idx_offset + max(sat, sat_adjacent_orbit)
            ))

    with open(output_filename_isls, 'w+') as f:
        for (a, b) in list_isls:
            f.write(str(a) + " " + str(b) + "\n")

    return list_isls


def generate_plus_grid_isls_with_random_failures(output_filename_isls, n_orbits, n_sats_per_orbit, isl_shift, 
                                                  failure_probability, random_seed=None, idx_offset=0,
                                                  inclination_degree=None, use_polar_version=None):
    """
    Generate ISL topology with random distributed failures.
    
    This function first generates a complete ISL topology (using either original or polar version),
    then randomly removes ISLs based on the specified failure probability.
    
    Args:
        output_filename_isls: Output filename for ISL topology
        n_orbits: Number of orbits
        n_sats_per_orbit: Number of satellites per orbit
        isl_shift: ISL shift between orbits
        failure_probability: Probability of each ISL failing (e.g., 0.01 for 1%, 0.05 for 5%, 0.10 for 10%)
        random_seed: Random seed for reproducibility (if None, uses unpredictable randomness)
        idx_offset: Index offset for multi-shell constellations
        inclination_degree: Inclination to decide polar/delta (required if use_polar_version=None)
        use_polar_version: 
            - None (default): Auto-detect based on inclination_degree
            - True: Force polar version
            - False: Force original version
    
    Returns:
        list_isls: List of surviving ISL tuples after random failures
    """
    import random
    
    # Set random seed for reproducibility
    if random_seed is not None:
        random.seed(random_seed)
    
    # Step 1: Generate complete ISL topology (auto-select polar/original version)
    if use_polar_version is None:
        if inclination_degree is None:
            raise ValueError("Must provide inclination_degree for auto-detection, or explicitly set use_polar_version")
        use_polar_version = (80.0 < inclination_degree < 100.0)
    
    if use_polar_version:
        if inclination_degree is None:
            raise ValueError("inclination_degree is required for polar version")
        complete_isls = generate_plus_grid_isls_polar(
            "/dev/null",  # Temporary output, we'll write the filtered list later
            n_orbits, n_sats_per_orbit, inclination_degree, isl_shift, idx_offset
        )
    else:
        complete_isls = generate_plus_grid_isls_original(
            "/dev/null",  # Temporary output
            n_orbits, n_sats_per_orbit, isl_shift, idx_offset
        )
    
    # Step 2: Randomly remove ISLs based on failure probability
    surviving_isls = []
    failed_count = 0
    
    for isl in complete_isls:
        # Each ISL has (1 - failure_probability) chance to survive
        if random.random() > failure_probability:
            surviving_isls.append(isl)
        else:
            failed_count += 1
    
    # Step 3: Write surviving ISLs to output file
    with open(output_filename_isls, 'w+') as f:
        for (a, b) in surviving_isls:
            f.write(str(a) + " " + str(b) + "\n")
    
    print(f"[ISL Random Failure] Total ISLs: {len(complete_isls)}, "
          f"Failed: {failed_count} ({failed_count/len(complete_isls)*100:.2f}%), "
          f"Surviving: {len(surviving_isls)} ({len(surviving_isls)/len(complete_isls)*100:.2f}%)")
    
    return surviving_isls


def generate_plus_grid_isls(output_filename_isls, n_orbits, n_sats_per_orbit, isl_shift, idx_offset=0, 
                            inclination_degree=None, use_polar_version=None):
    """
    Smart wrapper that automatically selects the appropriate ISL generation version.
    
    Args:
        inclination_degree: Required if use_polar_version is None (for auto-detection)
        use_polar_version: 
            - None (default): Auto-detect based on inclination_degree
            - True: Force polar version (polar seam handling)
            - False: Force original version (standard circular wrapping)
    
    Auto-detection logic:
        - Polar (80° < inc < 100°): Use polar version
        - Delta (all other): Use original version
    """
    # Auto-detect if not explicitly specified
    if use_polar_version is None:
        if inclination_degree is None:
            raise ValueError("Must provide inclination_degree for auto-detection, or explicitly set use_polar_version")
        use_polar_version = (80.0 < inclination_degree < 100.0)
    
    if use_polar_version:
        if inclination_degree is None:
            raise ValueError("inclination_degree is required for polar version")
        return generate_plus_grid_isls_polar(
            output_filename_isls, n_orbits, n_sats_per_orbit, 
            inclination_degree, isl_shift, idx_offset
        )
    else:
        return generate_plus_grid_isls_original(
            output_filename_isls, n_orbits, n_sats_per_orbit, 
            isl_shift, idx_offset
        )
