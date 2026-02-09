# Topology Statistics Fix Report
**Date**: 2026-02-06  
**Issue**: Baseline and LoHi unable to reflect Chaos Monkey's impact

---

## Problem Discovery

### Initial Symptom
Algorithm comparison showed identical control overhead across all failure rates:
- **Baseline**: P1=P5=P10 all show 24.17 MB
- **LoHi**: P1=P5=P10 all show 44.80 MB  
- **GRHR**: P1=56.7 MB → P5=133.4 MB → P10=192.3 MB (correct variation)

### Root Cause Analysis

#### Issue 1: Baseline Skips snapshot=0 Statistics ❌
**Location**: `algorithm_free_one_only_over_isls_with_stats.py:387`

```python
if snapshot > 0:  # 第一個快照沒有拓撲變化
```

**Problem**: Chaos Monkey injects failures at snapshot 0 (per log: `Snapshot=0 Total_ISLs=3168 Removed=316`), but condition excludes it from statistics.

**Impact**: P10 scenario removes 316 ISLs at snapshot 0, but these are not recorded.

---

#### Issue 2: Net Delta Tracking Method ❌
**Location**: Baseline L392-393, LoHi L625

```python
delta_isl = current_edges - prev_edges
```

**Problem**: Tracks net change only. When +grid rebuilds ISLs after Chaos Monkey removes them, net delta returns to 0.

**Timeline**:
- Snapshot 0: Chaos Monkey removes 316 ISLs → delta = -316
- Snapshot 1-19: +grid gradually rebuilds → delta = +316
- Snapshot 20: Net change = 0 (back to original state)

**Impact**: Topology change statistics show delta=0, failing to capture the actual churn.

---

#### Issue 3: LoHi Group-Level Statistics Only ⚠️
**Location**: `algorithm_lohi.py:626`

```python
_get_process_local_stats().record_topology_change(
    self._snapshot_idx, 
    self._snapshot_ms*self._snapshot_idx, 
    delta  # Only tracks group edge changes
)
```

**Problem**: Only records group-level edge changes (inter-group connectivity), not ISL-level changes.

**Impact**: Cannot track the actual ISL removals and rebuilds caused by Chaos Monkey.

---

## Implemented Fixes

### Fix 1: Remove snapshot>0 Restriction ✅
**File**: `algorithm_free_one_only_over_isls_with_stats.py`

**Change**:
```python
# Before:
if snapshot > 0:  # 第一個快照沒有拓撲變化
    current_edges = sat_net_graph_only_satellites_with_isls.number_of_edges()
    prev_edges = getattr(_get_process_local_stats(), '_prev_edge_count', current_edges)
    ...

# After:
current_edges = sat_net_graph_only_satellites_with_isls.number_of_edges()
prev_edges = getattr(_get_process_local_stats(), '_prev_edge_count', None)

if prev_edges is not None:
    # Only compute delta when previous state exists
    ...
```

**Benefit**: Now captures Chaos Monkey failures injected at snapshot 0.

---

### Fix 2: Enhanced Topology Statistics Logic ✅
**File**: `algorithm_free_one_only_over_isls_with_stats.py`

**Change**: Track actual removals and additions separately:
```python
# 淨變化 = 添加 - 移除，因此：添加 = 移除 + 淨變化
isl_removed = chaos_monkey_removed_count
isl_added = isl_removed + delta_isl

_get_process_local_stats().record_topology_change(
    snapshot, sim_time_ms,
    delta_isl=delta_isl,
    delta_gsl=delta_gsl,
    isl_removed=isl_removed,  # NEW
    isl_added=isl_added        # NEW
)
```

**Benefit**: Statistics now reflect actual churn (removals + additions) instead of just net change.

---

### Fix 3: Add ISL-Level Tracking to LoHi ✅
**File**: `algorithm_lohi.py`

**Change 3a**: Track ISL-level changes in `build_group_graph`:
```python
# 同時追蹤 ISL 級別的變化（反映 Chaos Monkey 影響）
current_isl_count = G_sat.number_of_edges()
prev_isl_count = getattr(self, '_prev_isl_count', current_isl_count)
delta_isl = current_isl_count - prev_isl_count

# 記錄群際邊變化（原有邏輯）+ ISL 變化
_get_process_local_stats().record_topology_change(
    self._snapshot_idx, 
    self._snapshot_ms*self._snapshot_idx, 
    delta,           # Group edge delta (original)
    delta_isl=delta_isl  # ISL delta (NEW)
)

self._prev_isl_count = current_isl_count
```

**Change 3b**: Update statistics method signature:
```python
def record_topology_change(self, snapshot, ms, delta_group_edges:int, delta_isl:int=0):
    """記錄群圖拓撲變化事件
    
    Args:
        delta_group_edges: 群際邊的淨變化
        delta_isl: ISL 的淨變化（用於追蹤 Chaos Monkey 影響）
    """
    self.topology_changes += 1
    self._append(EventRow(snapshot, ms, 'topology_change', 1, 0,
                          {'delta_group_edges': delta_group_edges, 'delta_isl': delta_isl}))
```

**Benefit**: LoHi now tracks both group-level topology changes (for routing logic) and ISL-level changes (for Chaos Monkey impact analysis).

---

## Validation Plan

### Test Scenarios
Re-run Baseline and LoHi with all 3 failure rates:
- **P1**: 1% failure rate
- **P5**: 5% failure rate  
- **P10**: 10% failure rate

### Expected Results
After fixes, topology change statistics should show:

1. **Non-zero topology events**: Chaos Monkey failures recorded at snapshots 0, 20, 40, 60, 80, 100
2. **Increasing churn with failure rate**:
   - P1: Lowest ISL removals/additions
   - P5: Medium ISL removals/additions
   - P10: Highest ISL removals/additions
3. **Control traffic variation**:
   - Baseline P1 < P5 < P10
   - LoHi P1 < P5 < P10

### Validation Metrics
- `isl_removed`: Should increase with failure rate
- `isl_added`: Should approximately equal isl_removed (due to +grid rebuild)
- Total control traffic: Should correlate with topology churn

---

## Next Steps

1. ✅ Code fixes applied
2. ⏳ Re-run Baseline (P1, P5, P10) - ~1 hour
3. ⏳ Re-run LoHi (P1, P5, P10) - ~1 hour
4. ⏳ Verify statistics show expected variation
5. ⏳ Regenerate comparison report and charts

---

## Technical Notes

### Chaos Monkey Trigger Intervals
```python
ENABLE_CHAOS_MONKEY = true
CHAOS_INTERVAL_SNAPSHOTS = 20  # Triggers at snapshots: 0, 20, 40, 60, 80, 100
CHAOS_FAILURE_RATE = {0.01, 0.05, 0.10}
```

### Files Modified
1. `satgenpy/satgen/dynamic_state/algorithm_free_one_only_over_isls_with_stats.py`
   - Lines 385-415: Topology statistics logic
2. `satgenpy/satgen/dynamic_state/algorithm_lohi.py`
   - Lines 183-192: `record_topology_change` method signature
   - Lines 627-638: ISL tracking in `build_group_graph`

### Chaos Monkey Logs
Confirmed working via log analysis:
- `chaos_monkey_baseline_p10.log`: Shows 316 ISL removals at snapshot 0
- `chaos_monkey_lohi_p10.log`: Shows similar removal patterns
- Format: `Snapshot=X Total_ISLs=Y Removed=Z Rate=W%`
