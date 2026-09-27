# Vision evaluation smoke-test results

**Status:** Historical pipeline verification only—superseded by the [full model-selection results](vision-evaluation-results.md).

**Run date:** 19 September 2026  
**Hardware:** Apple M4 Pro, 24 GB unified memory  
**Dataset:** Open Images validation and test subsets, deterministic seed `20260919`, one requested image per each of 27 official food classes  
**Conditions:** Original images plus deterministic dark, bright and Gaussian-blur robustness variants

**Model identifiers:** YOLO-World checkpoint SHA-256 `9b2c17ab6124a913e9b3a5c170617920d91b0f01111a8479da69f00e2cf27792`; Grounding DINO Tiny revision `a2bb814dd30d776dcf7e30523b00659f4f141c71`; Qwen Ollama model ID `fb90415cde1e`; Llama 3.2 Ollama model ID `a80c4f17acd5`.

The purpose of this run was to verify that official annotations, image acquisition, detector adapters, validation-only threshold selection, COCO conversion, metrics and artifact export operate end to end. One image per class is far too small for a defensible model comparison.

## Current smoke results

| Model | Validation-selected threshold | Test mAP@0.50 | Test mAP@0.50:0.95 | Precision@0.50 | Recall@0.50 | NDCG@0.50 | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| YOLO-World v2 | 0.10 | 0.234 | 0.181 | 0.030 | 0.316 | 0.359 | 62.4 ms/image |
| Grounding DINO Tiny | 0.30 | 0.377 | 0.350 | 0.098 | 0.658 | 0.541 | 1,790.9 ms/image |

The low YOLO-World precision is a real smoke-run result rather than a placeholder. At the validation-selected `0.10` threshold, the model returned many false positives when prompted with all 27 target classes. This supports testing higher threshold grids, class prompts and the second detector on the larger frozen subset; it does not by itself justify selecting or rejecting a model.

Grounding DINO scored higher on every accuracy metric in this smoke sample, but its mean CPU latency was approximately 28.7 times YOLO-World's. This is an important product trade-off, not a final conclusion: the full frozen subset and household correction study are still required before choosing the runtime detector.

## Deterministic robustness conditions

| Model | Condition | mAP@0.50 | Recall@0.50 | Mean latency |
|---|---|---:|---:|---:|
| YOLO-World v2 | Dark | 0.166 | 0.263 | 67.9 ms |
| YOLO-World v2 | Bright | 0.245 | 0.342 | 59.0 ms |
| YOLO-World v2 | Gaussian blur | 0.177 | 0.184 | 69.8 ms |
| Grounding DINO Tiny | Dark | 0.421 | 0.658 | 1,779.9 ms |
| Grounding DINO Tiny | Bright | 0.353 | 0.474 | 1,758.5 ms |
| Grounding DINO Tiny | Gaussian blur | 0.315 | 0.526 | 1,733.0 ms |

Brightness and blur conditions preserve image geometry, so the same ground-truth boxes remain valid. The unusual improvement for Grounding DINO on the dark condition is another sign that this 27-image smoke sample has high variance and should not be treated as a final estimate.

## Software checks completed

- Official Open Images class names were validated before image download.
- The initial list exposed six requested names that were not boxable classes under those labels; the vocabulary was corrected before evaluation.
- Both validation and test splits produced 27 images and 27-row per-image attribution files.
- Perfect synthetic predictions produced mAP, precision, recall and NDCG values of `1.0`.
- The photo confirmation integration test correctly measured one addition, one deletion, one rename and user confidence.
- Local Qwen2.5-VL correctly identified mangoes in an Open Images sample. Its first response copied the allowed-unit phrase into the unit field and conflicted with YOLO-World's `apple` label; unit allow-listing and conservative label-evidence merging were added as a direct design iteration.
- The React production build completed successfully.

## Follow-up status

The full 80/20/20-per-class acquisition, both detector adapters, robustness evaluation, transfer-learning run, paired-bootstrap comparison and technical detector selection have now been completed. See [vision-evaluation-results.md](vision-evaluation-results.md). The separate participant study on actual household fridges, pantries and table layouts remains required before making a usability claim.
