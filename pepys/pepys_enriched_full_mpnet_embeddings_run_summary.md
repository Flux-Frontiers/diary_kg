# Diary Embedder — Run Summary

| Field | Value |
|---|---|
| Date | 2026-03-28 |
| Time | 18:10:24 |
| Version | 0.91.0 |

## Invocation

```
/Users/egs/repos/diary_kg/.venv/bin/diary-transformer embed pepys/pepys_enriched_full.txt --workers 4 --batch-size 32 --force
```

## Inputs & Outputs

| Parameter | Value |
|---|---|
| Diary file | `pepys/pepys_enriched_full.txt` |
| Output cache | `pepys/pepys_enriched_full_mpnet_embeddings.json` |

## Run Parameters

| Parameter | Value |
|---|---|
| Model | `sentence-transformers/all-mpnet-base-v2` |
| Workers | `4` |
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
| Runtime | 33.0s |
