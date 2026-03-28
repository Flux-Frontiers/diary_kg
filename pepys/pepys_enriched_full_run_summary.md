# Diary Transformer — Run Summary

| Field | Value |
|---|---|
| Date | 2026-03-27 |
| Time | 22:36:54 |
| Version | 0.1.0 |

## Invocation

```
/Users/egs/repos/diary_kg/.venv/bin/diary-transformer transform pepys/pepys_clean.txt pepys/pepys_enriched_full.txt --topics-file pepys/pepys_only_topics.yaml --restart --batch-size 0
```

## Inputs & Outputs

| Parameter | Value |
|---|---|
| Input file | `pepys/pepys_clean.txt` |
| Output file | `pepys/pepys_enriched_full.txt` |

## Run Parameters

| Parameter | Value |
|---|---|
| Batch Size | `0` |
| Chunk Size | `512` |
| Max Chunks Per Entry | `3` |
| Chunking Strategy | `sentence_group` |
| Seed | `None` |

## Pipeline Statistics

| Metric | Value |
|---|---|
| Entries parsed | 3355 |
| Entries selected | 3355 |
| Entries generated | 7282 |
| Time range | 1660-01-01 → 1669-08-02 |
| Runtime | 246.0s |
