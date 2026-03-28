#!/usr/bin/env python3
"""
Compute Pc Script — conjunction-analysis-agent
Computes analytic collision probability using the Chan formula.
Output: outputs/YYYY-MM-DD_HHMM_conjunction-events.json

Dependencies: pip install numpy scipy
"""
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

# ── Default covariance models (1-sigma, km, in RSW frame) ────────────────────
DEFAULT_COVARIANCE = {
    'LEO': {'radial': 0.02, 'intrack': 0.15, 'crosstrack': 0.02},
    'GEO': {'radial': 0.1,  'intrack': 1.0,  'crosstrack': 0.1},
}

# Hard-body radii (km) per satellite class
HBR_BY_NORAD = {
    39522: 0.030,   # Türksat 4A (GEO bus)
    40985: 0.030,   # Türksat 4B
    47790: 0.030,   # Türksat 5A
    49077: 0.030,   # Türksat 5B
    41875: 0.020,   # GÖKTÜRK-1
    38704: 0.020,   # GÖKTÜRK-2
    37791: 0.020,   # RASAT
    55491: 0.020,   # İMECE
}
DEFAULT_HBR_KM = 0.020   # 20 m default for unknown objects

# Severity thresholds
TIER_THRESHOLDS = [
    ('RED',    1e-3),
    ('ORANGE', 1e-4),
    ('YELLOW', 1e-6),
    ('GREEN',  0.0),
]

# Miss distance based tier override (used when Pc underestimates risk)
# Physically: < 1km at high velocity = operationally significant regardless of Pc
MISS_DIST_TIERS = [
    ('RED',    1.0),   # < 1 km
    ('ORANGE', 3.0),   # < 3 km
    ('YELLOW', 8.0),   # < 8 km
    ('GREEN',  float('inf')),
]

def assign_tier_by_miss(miss_km: float, vel_km_s: float) -> str:
    for tier, threshold in MISS_DIST_TIERS:
        if miss_km < threshold:
            # Require minimum velocity for RED/ORANGE
            if tier in ('RED', 'ORANGE') and vel_km_s < 1.0:
                continue
            return tier
    return 'GREEN'


def assign_tier(pc: float) -> str:
    for tier, threshold in TIER_THRESHOLDS:
        if pc >= threshold:
            return tier
    return 'GREEN'


def rsw_cov_matrix(sigma_r: float, sigma_s: float, sigma_w: float) -> np.ndarray:
    """Build 3×3 diagonal covariance matrix in RSW frame."""
    return np.diag([sigma_r**2, sigma_s**2, sigma_w**2])


def build_rsw_rotation(r_hat: np.ndarray, s_hat: np.ndarray, w_hat: np.ndarray) -> np.ndarray:
    """Build rotation matrix from RSW to ECI frame (columns are RSW unit vectors)."""
    return np.column_stack([r_hat, s_hat, w_hat])


def chan_pc(miss_vec_eci: np.ndarray, rel_vel_eci: np.ndarray,
            C_combined_eci: np.ndarray, hbr_km: float) -> float:
    """
    Compute collision probability using the Chan analytic formula.
    Projects combined ECI covariance onto the miss plane (perpendicular to rel velocity).

    Returns Pc (probability, 0–1).
    """
    # Miss plane basis vectors
    rel_vel_norm = np.linalg.norm(rel_vel_eci)
    if rel_vel_norm < 1e-6:
        return 0.0
    e_vel = rel_vel_eci / rel_vel_norm

    miss_norm = np.linalg.norm(miss_vec_eci)
    if miss_norm < 1e-9:
        # Objects at same position → very high Pc
        return 1.0

    # Miss plane perpendicular basis (Gram-Schmidt)
    e_miss = miss_vec_eci / miss_norm
    e_miss = e_miss - np.dot(e_miss, e_vel) * e_vel
    e_miss_norm = np.linalg.norm(e_miss)
    if e_miss_norm < 1e-9:
        e_miss = np.array([1.0, 0.0, 0.0]) - np.dot([1.0, 0.0, 0.0], e_vel) * e_vel
        e_miss = e_miss / np.linalg.norm(e_miss)
    else:
        e_miss = e_miss / e_miss_norm

    e_perp = np.cross(e_vel, e_miss)
    e_perp = e_perp / np.linalg.norm(e_perp)

    # Project covariance onto miss plane (2×2)
    B = np.column_stack([e_miss, e_perp])  # (3, 2)
    C_2d = B.T @ C_combined_eci @ B        # (2, 2)

    # Eigen-decomposition for principal axes
    eigvals, eigvecs = np.linalg.eigh(C_2d)
    eigvals = np.maximum(eigvals, 1e-12)   # numerical safety
    sigma_u = math.sqrt(eigvals[0])
    sigma_v = math.sqrt(eigvals[1])

    # Miss vector projected onto miss plane principal axes
    miss_2d = B.T @ miss_vec_eci   # (2,)
    x_miss = float(eigvecs[:, 0] @ miss_2d)
    y_miss = float(eigvecs[:, 1] @ miss_2d)

    # Chan Gaussian approximation
    # Pc = (pi * HBR^2) / (2*pi*sigma_u*sigma_v) * exp(-0.5*((x/su)^2 + (y/sv)^2))
    exponent = -0.5 * ((x_miss / sigma_u)**2 + (y_miss / sigma_v)**2)
    pc = (math.pi * hbr_km**2) / (2 * math.pi * sigma_u * sigma_v) * math.exp(exponent)
    return min(pc, 1.0)


def load_latest_file(directory: str, suffix: str) -> str | None:
    files = sorted([f for f in os.listdir(directory) if f.endswith(suffix)])
    return os.path.join(directory, files[-1]) if files else None


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    # Load TCA results
    tca_path = load_latest_file(outputs_dir, '_tca-results.json')
    if not tca_path:
        print("[ERROR] No TCA results found")
        return
    with open(tca_path) as f:
        tca_data = json.load(f)

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    conjunction_events = []
    tier_counts = {'RED': 0, 'ORANGE': 0, 'YELLOW': 0, 'GREEN': 0}

    for rec in tca_data['tca_results']:
        band     = rec['orbital_band']
        t_norad  = rec['turkish_norad_id']
        hbr_km   = HBR_BY_NORAD.get(t_norad, DEFAULT_HBR_KM)
        cov_def  = DEFAULT_COVARIANCE[band]

        # Build combined covariance in RSW frame (primary + secondary, assume equal)
        C_primary   = rsw_cov_matrix(cov_def['radial'], cov_def['intrack'], cov_def['crosstrack'])
        C_secondary = C_primary.copy()
        C_combined_rsw = C_primary + C_secondary

        # Build RSW rotation for the primary satellite using miss vector components
        # We use RSW decomposition from TCA results as proxy
        r_miss = rec['radial_miss_km']
        s_miss = rec['intrack_miss_km']
        w_miss = rec['crosstrack_miss_km']
        miss_vec_eci = np.array([r_miss, s_miss, w_miss])  # approximation in RSW basis

        # For the ECI covariance, rotate C_combined_rsw to ECI
        # Without exact ECI→RSW rotation at TCA we use RSW frame directly
        # (valid when the covariance is defined in the conjunction geometry frame)
        C_combined_eci = C_combined_rsw

        # Relative velocity approximation: along-track dominant
        rel_vel_mag = rec['relative_velocity_km_s']
        rel_vel_eci = np.array([0.0, rel_vel_mag, 0.0])  # approximate as along-track

        pc = chan_pc(miss_vec_eci, rel_vel_eci, C_combined_eci, hbr_km)
        tier_pc   = assign_tier(pc)
        tier_miss = assign_tier_by_miss(rec['miss_distance_km'], rec['relative_velocity_km_s'])
        # Take the worse (higher risk) of the two
        tier_order = ['GREEN', 'YELLOW', 'ORANGE', 'RED']
        tier = tier_order[max(tier_order.index(tier_pc), tier_order.index(tier_miss))]
        tier_counts[tier] += 1

        event = {**rec, 'analytic_pc': pc, 'severity_tier': tier,
                 'hbr_km': hbr_km, 'covariance_source': 'DEFAULT'}
        conjunction_events.append(event)

    # Write output
    output = {
        'computed_at_utc':    now.isoformat(),
        'total_events':       len(conjunction_events),
        'tier_counts':        tier_counts,
        'conjunction_events': conjunction_events,
    }
    output_path = os.path.join(outputs_dir, f"{ts}_conjunction-events.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[Pc] {len(conjunction_events)} events | RED:{tier_counts['RED']} ORANGE:{tier_counts['ORANGE']} YELLOW:{tier_counts['YELLOW']} GREEN:{tier_counts['GREEN']}")
    print(f"     Written: {os.path.basename(output_path)}")

    # Flag RED events to console for immediate attention
    red_events = [e for e in conjunction_events if e['severity_tier'] == 'RED']
    for ev in red_events:
        print(f"  !! RED: {ev['turkish_name']} × NORAD {ev['debris_norad_id']} | TCA {ev['tca_utc']} | Pc={ev['analytic_pc']:.2e}")

    return output_path


if __name__ == '__main__':
    main()
