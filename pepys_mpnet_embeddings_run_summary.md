# Diary Embedder — Run Summary

| Field | Value |
|---|---|
| Date | 2026-03-31 |
| Time | 22:35:54 |
| Version | 0.91.1 |

## Invocation

```
.venv/bin/diary-embedder --workers 1 --force
```

## Inputs & Outputs

| Parameter | Value |
|---|---|
| Diary file | `/Users/egs/repos/diary_kg/pepys/pepys_enriched_full.txt` |
| Output cache | `/Users/egs/repos/diary_kg/pepys_mpnet_embeddings.json` |

## Run Parameters

| Parameter | Value |
|---|---|
| Model | `sentence-transformers/all-mpnet-base-v2` |
| Workers | `1` |
| Batch Size | `32` |
| N Sample | `all` |
| Max Chars | `none` |

## Pipeline Statistics

| Metric | Value |
|---|---|
| Entries parsed | 7282 |
| Entries embedded | 7282 |
| Time range | 1660-01-01 → 1669-08-02 |
| Embedding shape | 7282 × 768 float32 |
| Runtime | 48.6s |
