"""Dependency-light COCO-style metrics used by the detector comparison."""

from __future__ import annotations

import math
from collections import defaultdict


def iou(box_a: list[float], box_b: list[float]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def intersection_over_prediction_area(
    prediction_box: list[float], group_box: list[float]
) -> float:
    """COCO-style overlap used to ignore detections inside group regions."""
    px, py, pw, ph = prediction_box
    gx, gy, gw, gh = group_box
    left = max(px, gx)
    top = max(py, gy)
    right = min(px + pw, gx + gw)
    bottom = min(py + ph, gy + gh)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    prediction_area = pw * ph
    return intersection / prediction_area if prediction_area > 0 else 0.0


def average_precision(recalls: list[float], precisions: list[float]) -> float:
    """101-point interpolated AP, matching the modern COCO convention."""
    if not recalls:
        return 0.0
    return sum(
        max((precision for recall, precision in zip(recalls, precisions) if recall >= level), default=0.0)
        for level in (index / 100 for index in range(101))
    ) / 101


def evaluate_at_iou(
    ground_truth: list[dict],
    predictions: list[dict],
    category_ids: list[int],
    iou_threshold: float,
) -> dict:
    ground_truth_by_key: dict[tuple[int, int], list[dict]] = defaultdict(list)
    group_truth_by_key: dict[tuple[int, int], list[dict]] = defaultdict(list)
    predictions_by_category: dict[int, list[dict]] = defaultdict(list)
    for item in ground_truth:
        target = (
            group_truth_by_key if item.get("iscrowd", 0) else ground_truth_by_key
        )
        target[(item["image_id"], item["category_id"])].append(item)
    for item in predictions:
        predictions_by_category[item["category_id"]].append(item)

    aps: list[float] = []
    total_tp = total_fp = total_gt = 0
    per_class: dict[int, dict] = {}
    for category_id in category_ids:
        class_predictions = sorted(
            predictions_by_category[category_id], key=lambda item: item["score"], reverse=True
        )
        matched: dict[tuple[int, int], set[int]] = defaultdict(set)
        gt_count = sum(
            len(items)
            for (image_id, class_id), items in ground_truth_by_key.items()
            if class_id == category_id
        )
        tp_flags: list[int] = []
        fp_flags: list[int] = []
        for prediction in class_predictions:
            key = (prediction["image_id"], category_id)
            candidates = ground_truth_by_key.get(key, [])
            best_index = -1
            best_iou = 0.0
            for index, target in enumerate(candidates):
                if index in matched[key]:
                    continue
                overlap = iou(prediction["bbox"], target["bbox"])
                if overlap > best_iou:
                    best_iou = overlap
                    best_index = index
            if best_index >= 0 and best_iou >= iou_threshold:
                matched[key].add(best_index)
                tp_flags.append(1)
                fp_flags.append(0)
            elif any(
                intersection_over_prediction_area(
                    prediction["bbox"], group["bbox"]
                )
                >= iou_threshold
                for group in group_truth_by_key.get(key, [])
            ):
                # A group box does not give individual object locations. COCO
                # convention ignores detections contained by that region.
                continue
            else:
                tp_flags.append(0)
                fp_flags.append(1)

        cumulative_tp = 0
        cumulative_fp = 0
        recalls: list[float] = []
        precisions: list[float] = []
        for tp, fp in zip(tp_flags, fp_flags):
            cumulative_tp += tp
            cumulative_fp += fp
            recalls.append(cumulative_tp / gt_count if gt_count else 0.0)
            precisions.append(cumulative_tp / max(1, cumulative_tp + cumulative_fp))
        ap = average_precision(recalls, precisions) if gt_count else 0.0
        if gt_count:
            aps.append(ap)
        class_precision = cumulative_tp / max(1, cumulative_tp + cumulative_fp)
        class_recall = cumulative_tp / gt_count if gt_count else 0.0
        per_class[category_id] = {
            "ap": ap,
            "precision": class_precision,
            "recall": class_recall,
            "ground_truth": gt_count,
            "predictions": len(class_predictions),
        }
        total_tp += cumulative_tp
        total_fp += cumulative_fp
        total_gt += gt_count

    precision = total_tp / max(1, total_tp + total_fp)
    recall = total_tp / max(1, total_gt)
    return {
        "map": sum(aps) / len(aps) if aps else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(1e-12, precision + recall),
        "per_class": per_class,
    }


def ndcg_by_image(ground_truth: list[dict], predictions: list[dict], threshold: float = 0.5) -> float:
    """Rank detections per image; a correct class-and-box match has relevance 1."""
    gt_by_image: dict[int, list[dict]] = defaultdict(list)
    groups_by_image: dict[int, list[dict]] = defaultdict(list)
    pred_by_image: dict[int, list[dict]] = defaultdict(list)
    for item in ground_truth:
        target = groups_by_image if item.get("iscrowd", 0) else gt_by_image
        target[item["image_id"]].append(item)
    for item in predictions:
        pred_by_image[item["image_id"]].append(item)

    scores: list[float] = []
    for image_id, targets in gt_by_image.items():
        matched: set[int] = set()
        relevance: list[int] = []
        for prediction in sorted(pred_by_image[image_id], key=lambda item: item["score"], reverse=True):
            best_index = -1
            best_overlap = 0.0
            for index, target in enumerate(targets):
                if index in matched or target["category_id"] != prediction["category_id"]:
                    continue
                overlap = iou(target["bbox"], prediction["bbox"])
                if overlap > best_overlap:
                    best_index, best_overlap = index, overlap
            relevant = int(best_index >= 0 and best_overlap >= threshold)
            if not relevant and any(
                group["category_id"] == prediction["category_id"]
                and intersection_over_prediction_area(
                    prediction["bbox"], group["bbox"]
                )
                >= threshold
                for group in groups_by_image.get(image_id, [])
            ):
                continue
            relevance.append(relevant)
            if relevant:
                matched.add(best_index)
        dcg = sum(value / math.log2(index + 2) for index, value in enumerate(relevance))
        ideal_length = min(len(targets), len(relevance))
        ideal = sum(1 / math.log2(index + 2) for index in range(ideal_length))
        scores.append(dcg / ideal if ideal else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def confusion_matrix(
    ground_truth: list[dict],
    predictions: list[dict],
    category_ids: list[int],
    threshold: float = 0.5,
) -> tuple[list[str], list[list[int]]]:
    """Rows are actual labels; columns are predicted labels; last is background."""
    indexes = {category_id: index for index, category_id in enumerate(category_ids)}
    background = len(category_ids)
    matrix = [[0 for _ in range(background + 1)] for _ in range(background + 1)]
    gt_by_image: dict[int, list[dict]] = defaultdict(list)
    groups_by_image: dict[int, list[dict]] = defaultdict(list)
    pred_by_image: dict[int, list[dict]] = defaultdict(list)
    for item in ground_truth:
        target = groups_by_image if item.get("iscrowd", 0) else gt_by_image
        target[item["image_id"]].append(item)
    for item in predictions:
        pred_by_image[item["image_id"]].append(item)

    for image_id in set(gt_by_image) | set(pred_by_image):
        targets = gt_by_image[image_id]
        matched_targets: set[int] = set()
        for prediction in sorted(pred_by_image[image_id], key=lambda item: item["score"], reverse=True):
            best_index = -1
            best_overlap = 0.0
            for index, target in enumerate(targets):
                if index in matched_targets:
                    continue
                overlap = iou(target["bbox"], prediction["bbox"])
                if overlap > best_overlap:
                    best_index, best_overlap = index, overlap
            predicted_index = indexes[prediction["category_id"]]
            if best_index >= 0 and best_overlap >= threshold:
                matched_targets.add(best_index)
                actual_index = indexes[targets[best_index]["category_id"]]
                matrix[actual_index][predicted_index] += 1
            elif any(
                group["category_id"] == prediction["category_id"]
                and intersection_over_prediction_area(
                    prediction["bbox"], group["bbox"]
                )
                >= threshold
                for group in groups_by_image.get(image_id, [])
            ):
                continue
            else:
                matrix[background][predicted_index] += 1
        for index, target in enumerate(targets):
            if index not in matched_targets:
                matrix[indexes[target["category_id"]]][background] += 1
    return [str(category_id) for category_id in category_ids] + ["background"], matrix


def full_metrics(dataset: dict, predictions: list[dict]) -> dict:
    category_ids = [category["id"] for category in dataset["categories"]]
    thresholds = [round(0.5 + index * 0.05, 2) for index in range(10)]
    by_threshold = {
        str(threshold): evaluate_at_iou(
            dataset["annotations"], predictions, category_ids, threshold
        )
        for threshold in thresholds
    }
    at_50 = by_threshold["0.5"]
    labels, matrix = confusion_matrix(dataset["annotations"], predictions, category_ids)
    return {
        "map_50": at_50["map"],
        "map_50_95": sum(result["map"] for result in by_threshold.values()) / len(thresholds),
        "precision_50": at_50["precision"],
        "recall_50": at_50["recall"],
        "f1_50": at_50["f1"],
        "ndcg_50": ndcg_by_image(dataset["annotations"], predictions),
        "per_class_50": at_50["per_class"],
        "confusion_labels": labels,
        "confusion_matrix": matrix,
    }
