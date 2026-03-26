#!/usr/bin/env python3
"""
Self-contained test of the transpose+flip orientation technique.

Tests that applying a signed permutation matrix to a 4D volume (time, z, y, x)
via np.transpose + np.flip produces correct results for all 24 proper
axis-aligned rotation matrices.

No Django or DICOM dependencies — pure numpy.
"""
import numpy as np
from itertools import permutations


# ── technique under test ──────────────────────────────────────────────────────

def apply_transpose_flip(volume, M):
    """
    Apply a 3x3 signed permutation matrix M to a 4D volume (time, z, y, x),
    reorienting it to standard axial orientation.

    Decomposes M into:
      1. Axis permutation  → np.transpose  (which input axis maps to each output axis)
      2. Axis sign flips   → np.flip       (negate axes that point backwards)

    M is in DICOM coordinate order: rows = (row-dir, col-dir, slice-normal),
    columns = (x, y, z) patient axes.  The volume's spatial axes, however,
    are ordered (slice=z, row=y, col=x) — reversed from M's convention.

    To convert M to volume-axis space we remap both input and output indices
    from (x,y,z) to (z,y,x): M_vol = M^T reversed on both axes.
    """
    # Remap M from coordinate order to volume-axis order
    M_vol = M.T[::-1, ::-1]

    perm  = np.argmax(np.abs(M_vol), axis=1)   # perm[i] = input axis for output axis i
    signs = M_vol[np.arange(3), perm]           # +1 or -1 for each output axis

    # Reorder spatial axes (offset by 1 to skip the time axis at dim 0)
    volume = np.transpose(volume, axes=[0, perm[0]+1, perm[1]+1, perm[2]+1])

    # Flip axes where the sign is -1
    for i, sign in enumerate(signs):
        if sign < 0:
            volume = np.flip(volume, axis=i+1)

    return volume


# ── reference implementation (mat_to_rotations from cine_generation.py) ───────

_ROTS = [
    np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]),
    np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
    np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]),
]

def _mat_to_rotations(mat):
    mat = mat.copy().astype(float)
    rotations = []

    n = 0
    while not np.allclose(mat @ [1, 0, 0], [1, 0, 0]) and n < 4:
        mat = mat @ _ROTS[2]
        n += 1
    if n and n < 4:
        rotations += [(n, (2, 1))]

    if n == 4:
        n = 0
        while not np.allclose(mat @ [1, 0, 0], [1, 0, 0]) and n < 4:
            mat = mat @ _ROTS[1]
            n += 1
        if n > 3:
            raise ValueError("mat_to_rotations failed (Y phase)")
        if n:
            rotations += [(n, (0, 2))]

    n = 0
    while not np.allclose(mat @ [0, 1, 0], [0, 1, 0]):
        mat = mat @ _ROTS[0]
        n += 1
        if n > 3:
            raise ValueError("mat_to_rotations failed (Z phase)")
    if n:
        rotations += [(n, (1, 0))]

    assert np.allclose(mat, np.identity(3))
    rotations.reverse()
    return rotations


def _apply_mat_to_rotations(volume, M):
    """Reference: apply mat_to_rotations to a 4D volume."""
    for k, axes in _mat_to_rotations(M):
        volume = np.rot90(volume, k=k, axes=[a+1 for a in axes])
    return volume


# ── test helpers ──────────────────────────────────────────────────────────────

def all_orientation_matrices():
    """
    Return all 24 proper-rotation (det=+1) signed permutation matrices.

    These represent every axis-aligned orientation a DICOM volume can have.
    Each matrix has exactly one ±1 per row and column.
    """
    matrices = []
    for perm in permutations([0, 1, 2]):
        for sign_bits in range(8):                      # 2^3 sign combinations
            signs = [1 if sign_bits & (1 << i) else -1 for i in range(3)]
            M = np.zeros((3, 3), dtype=int)
            for out_row, in_col in enumerate(perm):
                M[out_row, in_col] = signs[out_row]
            if round(np.linalg.det(M)) == 1:            # proper rotations only
                matrices.append(M)
    return matrices


def make_volume(shape=(2, 3, 4, 5)):
    """
    4D volume (T, Z, Y, X) with unique position-encoded integer values:
      vol[t, z, y, x] = t*1000 + z*100 + y*10 + x

    Asymmetric spatial dimensions (3, 4, 5) ensure any axis swap changes
    the shape, making orientation errors immediately visible.
    """
    T, Z, Y, X = shape
    idx = np.arange(T*Z*Y*X, dtype=np.int32).reshape(shape)
    t_contrib = (idx // (Z*Y*X)) * 1000
    z_contrib = (idx % (Z*Y*X) // (Y*X)) * 100
    y_contrib = (idx % (Y*X) // X) * 10
    x_contrib = idx % X
    return t_contrib + z_contrib + y_contrib + x_contrib


# ── tests ─────────────────────────────────────────────────────────────────────

def test_count():
    """There are exactly 24 proper-rotation signed permutation matrices."""
    matrices = all_orientation_matrices()
    assert len(matrices) == 24, f"Expected 24, got {len(matrices)}"
    # All must be distinct
    for i, a in enumerate(matrices):
        for j, b in enumerate(matrices):
            if i != j:
                assert not np.array_equal(a, b), f"Duplicate at indices {i},{j}"
    print(f"  count: 24 distinct matrices ✓")


def test_output_shape():
    """
    The output shape must reflect the axis permutation in M:
    spatial dims are permuted according to perm = argmax(|M|, axis=1).
    """
    matrices = all_orientation_matrices()
    T, Z, Y, X = 2, 3, 4, 5
    vol = make_volume((T, Z, Y, X))
    spatial = np.array([Z, Y, X])

    for M in matrices:
        M_vol = M.T[::-1, ::-1]
        perm = np.argmax(np.abs(M_vol), axis=1)
        expected_shape = (T, *spatial[perm])
        result = apply_transpose_flip(vol, M)
        assert result.shape == expected_shape, \
            f"Shape mismatch: expected {expected_shape}, got {result.shape}\nM=\n{M}"

    print(f"  output_shape: all 24 matrices ✓")


def test_round_trip():
    """
    Applying M then M⁻¹ must recover the original volume exactly.
    For orthogonal matrices, M⁻¹ = Mᵀ.
    """
    matrices = all_orientation_matrices()
    vol = make_volume()

    for M in matrices:
        M_inv = M.T                                 # inverse of orthogonal matrix
        transformed = apply_transpose_flip(vol, M)
        recovered   = apply_transpose_flip(transformed, M_inv)
        assert np.array_equal(vol, recovered), \
            f"Round-trip failed for M=\n{M}"

    print(f"  round_trip: all 24 matrices ✓")


def test_matches_mat_to_rotations():
    """
    transpose+flip must produce identical results to the existing
    mat_to_rotations approach for every orientation.
    """
    matrices = all_orientation_matrices()
    vol = make_volume()

    for M in matrices:
        result_new = apply_transpose_flip(vol.copy(), M)
        result_ref = _apply_mat_to_rotations(vol.copy(), M)
        assert np.array_equal(result_new, result_ref), \
            f"Mismatch vs mat_to_rotations for M=\n{M}"

    print(f"  matches_mat_to_rotations: all 24 matrices ✓")


def test_known_positions():
    """
    Place a single sentinel voxel and verify it lands at the expected
    position for hand-checked cases.

    Convention: volume shape (T=2, Z=3, Y=4, X=5), indices (t, z, y, x).
    """
    SENTINEL = 9999
    shape = (2, 3, 4, 5)

    cases = [
        # description, M (in DICOM coord order: x,y,z), src (t,z,y,x), expected (t,z,y,x)
        # M rows = (row-dir, col-dir, slice-normal), volume axes = (slice, row, col) = (z, y, x)

        # Identity — no transform
        ("identity",
         np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
         (0, 1, 2, 3), (0, 1, 2, 3)),

        # 180° around Z axis: flips x-dir and y-dir, keeps z
        # M_vol = [[1,0,0],[0,-1,0],[0,0,-1]] → flip Y and X in volume
        # Y=2→4-1-2=1, X=3→5-1-3=1
        ("180° around Z",
         np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]]),
         (0, 1, 2, 3), (0, 1, 1, 1)),

        # 180° around X axis: flips y and z, keeps x
        # M_vol = [[-1,0,0],[0,-1,0],[0,0,1]] → flip Z and Y in volume
        # Z=1→3-1-1=1, Y=2→4-1-2=1
        ("180° around X",
         np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]]),
         (0, 1, 2, 3), (0, 1, 1, 3)),

        # Cyclic permutation: x→y, y→z, z→x
        ("cyclic x→y→z→x",
         np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]]),
         (0, 1, 2, 3), None),  # computed below
    ]

    # For the cyclic case, compute expected position from mat_to_rotations as reference
    vol_ref = np.zeros(shape, dtype=np.int32)
    vol_ref[cases[-1][2]] = SENTINEL
    ref_result = _apply_mat_to_rotations(vol_ref, cases[-1][1])
    cases[-1] = (*cases[-1][:3], tuple(int(x) for x in np.argwhere(ref_result == SENTINEL)[0]))

    for desc, M, src, expected in cases:
        vol = np.zeros(shape, dtype=np.int32)
        vol[src] = SENTINEL
        result = apply_transpose_flip(vol, M)
        assert result[expected] == SENTINEL, (
            f"[{desc}] sentinel not found at {expected}.\n"
            f"M=\n{M}\n"
            f"result shape={result.shape}, result sum={result.sum()}"
        )

    print(f"  known_positions: all {len(cases)} cases ✓")


def test_values_preserved():
    """Every value in the original volume must appear in the transformed volume."""
    matrices = all_orientation_matrices()
    vol = make_volume()
    original_values = np.sort(vol.ravel())

    for M in matrices:
        result = apply_transpose_flip(vol, M)
        assert np.array_equal(np.sort(result.ravel()), original_values), \
            f"Values changed after transform for M=\n{M}"

    print(f"  values_preserved: all 24 matrices ✓")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Testing transpose+flip orientation technique\n")

    tests = [
        test_count,
        test_output_shape,
        test_round_trip,
        test_matches_mat_to_rotations,
        test_known_positions,
        test_values_preserved,
    ]

    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{passed+failed} tests passed")
    raise SystemExit(0 if failed == 0 else 1)
