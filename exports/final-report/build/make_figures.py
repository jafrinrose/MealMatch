"""Charts and diagrams for the MealMatch final report.

Every number comes from the project documentation (docs/*.md); nothing is estimated here.
Run with a Python that has matplotlib and Pillow:  python make_figures.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

DEEP, MINT, LIME, AMBER, CORAL, SAGE, CREAM, GREY, LAV = (
    "#0c3a35", "#1f9e80", "#b9e05a", "#e8a93a", "#e0654a", "#dcebd6", "#fbf6e9", "#8a9a93", "#8f7ad8",
)
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 11, "figure.dpi": 100, "savefig.dpi": 220,
    "axes.edgecolor": "#55635d", "axes.labelcolor": "#26332f", "xtick.color": "#26332f", "ytick.color": "#26332f",
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def bar_labels(ax, bars, fmt="{:.2f}", pad=0.01, size=8):
    for bar in bars:
        value = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, value + pad, fmt.format(value), ha="center", va="bottom", fontsize=size)


# ---------------------------------------------------------------- charts

def chart_detector():
    metrics = ["mAP@0.50", "Precision", "Recall", "F1", "NDCG@0.50"]
    models = {
        "YOLO-World v2 (zero-shot)": [0.057, 0.088, 0.092, 0.090, 0.165],
        "Grounding DINO Tiny (zero-shot)": [0.181, 0.193, 0.232, 0.211, 0.356],
        "YOLO-World v2 (fine-tuned)": [0.244, 0.399, 0.288, 0.335, 0.461],
    }
    latency = [31.2, 571.7, 24.7]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.8), gridspec_kw={"width_ratios": [3.2, 1.2]})
    width = 0.26
    for i, (name, values) in enumerate(models.items()):
        bars = ax.bar([x + (i - 1) * width for x in range(len(metrics))], values, width, label=name, color=[GREY, LAV, MINT][i])
        bar_labels(ax, bars, size=7)
    ax.set_xticks(range(len(metrics)), metrics)
    ax.set_ylim(0, 0.55)
    ax.set_ylabel("Score on untouched test split")
    ax.set_title("Open Images food subset (530 test images, 27 classes)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    bars = ax2.bar(["YOLO\nzero-shot", "G-DINO\nzero-shot", "YOLO\nfine-tuned"], latency, color=[GREY, LAV, MINT])
    ax2.tick_params(axis="x", labelsize=7.5)
    ax2.set_yscale("log")
    ax2.set_ylabel("Mean latency per image (ms, log)")
    ax2.set_title("Latency (M4 Pro)")
    for bar, value in zip(bars, latency):
        ax2.text(bar.get_x() + bar.get_width() / 2, value * 1.1, f"{value:g} ms", ha="center", fontsize=8)
    ax2.set_ylim(10, 2000)
    save(fig, "chart_detector_benchmark")


def chart_qwen():
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.3, 1.3, 1]})
    labels = ["Precision", "Recall", "F1"]
    sets = [
        ("Household frozen test\n(35 images × 3 runs)", [0.334, 0.163, 0.219], [0.252, 0.254, 0.253]),
        ("Open Images check\n(50 images, closed vocabulary)", [0.833, 0.273, 0.411], [0.900, 0.818, 0.857]),
    ]
    for ax, (title, small, large) in zip(axes[:2], sets):
        b1 = ax.bar([x - 0.18 for x in range(3)], small, 0.36, label="Qwen2.5-VL 3B", color=MINT)
        b2 = ax.bar([x + 0.18 for x in range(3)], large, 0.36, label="Qwen2.5-VL 7B", color=LAV)
        bar_labels(ax, b1, size=7)
        bar_labels(ax, b2, size=7)
        ax.set_xticks(range(3), labels)
        ax.set_ylim(0, 1.0)
        ax.set_title(title, fontsize=9.5)
    axes[0].legend(frameon=False, fontsize=8)
    ax = axes[2]
    ax.axis("off")
    rows = [["", "3B", "7B"], ["Failures", "0 / 105", "7 / 105 (6.7%)"], ["Median latency", "7.2 s", "44.7 s"],
            ["p95 latency", "137.8 s", "≈300 s"], ["Repeatability", "0.679", "0.657"], ["Gate (≤5% failures)", "pass", "fail"]]
    table = ax.table(cellText=rows, loc="center", cellLoc="center", colWidths=[0.44, 0.24, 0.36])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.45)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#c9d6cf")
        if r == 0:
            cell.set_facecolor(SAGE)
            cell.set_text_props(weight="bold")
        if r == 5 and c == 2:
            cell.set_facecolor("#f8d9d2")
        if r == 5 and c == 1:
            cell.set_facecolor("#dff3e8")
    ax.set_title("Household gate", fontsize=9.5)
    save(fig, "chart_qwen_selection")


def chart_photo_iteration():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.8))
    pipes = ["Old pipeline\n(3 runs/image)", "New: whole photo", "New: with close-ups"]
    p = [0.334, 0.387, 0.225]
    r = [0.163, 0.218, 0.317]
    f = [0.219, 0.279, 0.263]
    ci = [None, (0.212, 0.334), (0.199, 0.311)]
    x = range(3)
    ax.bar([i - 0.25 for i in x], p, 0.25, label="Precision", color=LAV)
    ax.bar([i for i in x], r, 0.25, label="Recall", color=AMBER)
    bars = ax.bar([i + 0.25 for i in x], f, 0.25, label="F1", color=MINT)
    for i, bounds in enumerate(ci):
        if bounds:
            ax.errorbar(i + 0.25, f[i], yerr=[[f[i] - bounds[0]], [bounds[1] - f[i]]], color=DEEP, capsize=3, lw=1)
    bar_labels(ax, bars, size=7)
    ax.set_xticks(list(x), pipes)
    ax.set_ylim(0, 0.5)
    ax.set_title("Frozen household test (35 images)")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    scenes = ["Refrigerator\n(11)", "Shelf\n(9)", "Pantry\n(9)", "Grocery\ntable (3)", "Drawer/\nother (3)"]
    old = [0.233, 0.278, 0.152, 0.086, 0.033]
    whole = [0.254, 0.286, 0.152, 0.235, 0.050]
    close = [0.317, 0.357, 0.239, 0.370, 0.200]
    x = range(len(scenes))
    ax2.bar([i - 0.25 for i in x], old, 0.25, label="Old", color=GREY)
    ax2.bar([i for i in x], whole, 0.25, label="Whole photo", color=MINT)
    ax2.bar([i + 0.25 for i in x], close, 0.25, label="With close-ups", color=AMBER)
    ax2.set_xticks(list(x), scenes)
    ax2.set_ylabel("Recall")
    ax2.set_ylim(0, 0.45)
    ax2.set_title("Recall by scene type")
    ax2.legend(frameon=False, fontsize=8)
    save(fig, "chart_photo_pipeline_iteration")


def chart_round2_scenes():
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    scenes = ["Test 1: controlled\n8 items, 3 runs", "Test 2: refrigerator\n15 items", "Test 3: grocery table\n15 items"]
    p, r, f = [1.00, 0.82, 0.78], [0.67, 0.60, 0.47], [0.80, 0.69, 0.58]
    x = range(3)
    b = [ax.bar([i - 0.25 for i in x], p, 0.25, label="Precision", color=LAV),
         ax.bar([i for i in x], r, 0.25, label="Recall", color=AMBER),
         ax.bar([i + 0.25 for i in x], f, 0.25, label="F1", color=MINT)]
    for bars in b:
        bar_labels(ax, bars, size=7)
    ax.axhline(0.85, color=LAV, ls="--", lw=1)
    ax.axhline(0.80, color=AMBER, ls="--", lw=1)
    ax.text(2.45, 0.86, "precision target 0.85", fontsize=7, color=LAV, ha="right")
    ax.text(2.45, 0.755, "recall target 0.80", fontsize=7, color="#b67a17", ha="right")
    ax.set_xticks(list(x), scenes)
    ax.set_ylim(0, 1.12)
    ax.set_title("Round 2 photographs before the pipeline iteration (upload to results: 4–5 s, 35 s, 14 s)")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper right", bbox_to_anchor=(1, 1.02))
    save(fig, "chart_round2_scenes")


def chart_text_models():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [2.2, 1]})
    tasks = ["Recipe", "Receipt", "Substitution", "Cooking", "Macro"]
    data = {"Llama 3.2 3B": [1.000, 1.000, 0.938, 0.838, 0.944], "Qwen2.5 3B": [1.000, 0.964, 0.875, 1.000, 0.960],
            "Phi-3.5 Mini 3.8B": [0.642, 0.700, 0.475, 1.000, 0.704]}
    for i, (name, values) in enumerate(data.items()):
        bars = ax.bar([x + (i - 1) * 0.26 for x in range(5)], values, 0.26, label=name, color=[MINT, LAV, GREY][i])
        bar_labels(ax, bars, size=6.5)
    ax.set_xticks(range(5), tasks)
    ax.set_ylim(0, 1.18)
    ax.set_title("Frozen MealMatch text benchmark (18 cases per model)")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    names = ["Llama 3.2 3B", "Qwen2.5 3B", "Phi-3.5 3.8B"]
    structured = [100, 100, 35.7]
    safety = [100, 100, 80.0]
    ax2.bar([i - 0.18 for i in range(3)], structured, 0.36, label="Structured output valid", color=MINT)
    ax2.bar([i + 0.18 for i in range(3)], safety, 0.36, label="Diet/allergy constraint safety", color=AMBER)
    ax2.axhline(90, color=CORAL, ls="--", lw=1)
    ax2.text(2.5, 91.5, "90% gate", fontsize=7, color=CORAL, ha="right")
    ax2.set_xticks(range(3), names, fontsize=8)
    ax2.set_ylim(0, 118)
    ax2.set_ylabel("%")
    ax2.set_title("Eligibility gates")
    ax2.legend(frameon=False, fontsize=7, loc="upper right")
    save(fig, "chart_text_models")


def chart_asr():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.6))
    stage_a = ["tiny.en", "base.en", "small.en"]
    clean_a, noisy_a = [88.9, 96.3, 98.1], [75.9, 87.0, 92.6]
    ax.bar([i - 0.18 for i in range(3)], clean_a, 0.36, label="Clean intent", color=MINT)
    ax.bar([i + 0.18 for i in range(3)], noisy_a, 0.36, label="Noisy intent (10 dB SNR)", color=AMBER)
    ax.axhline(95, color=MINT, ls="--", lw=1)
    ax.axhline(85, color="#b67a17", ls="--", lw=1)
    ax.set_xticks(range(3), [f"Whisper {s}\nWER {w}" for s, w in zip(stage_a, [0.102, 0.059, 0.046])])
    ax.set_ylim(0, 110)
    ax.set_ylabel("Intent accuracy (%)")
    ax.set_title("Stage A: Whisper capacity screen (108 clips each)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    stage_b = ["Whisper small.en", "Distil-Whisper\nsmall.en", "wav2vec 2.0\nBase 960h"]
    clean_b, noisy_b, lat = [98.1, 92.6, 64.8], [92.6, 81.5, 31.5], [1045, 922, 59]
    ax2.bar([i - 0.18 for i in range(3)], clean_b, 0.36, label="Clean intent", color=MINT)
    ax2.bar([i + 0.18 for i in range(3)], noisy_b, 0.36, label="Noisy intent", color=AMBER)
    ax2.axhline(95, color=MINT, ls="--", lw=1)
    ax2.axhline(85, color="#b67a17", ls="--", lw=1)
    for i, value in enumerate(lat):
        ax2.text(i, 103, f"median {value:,} ms", ha="center", fontsize=7.5, color=DEEP)
    ax2.set_xticks(range(3), stage_b)
    ax2.set_ylim(0, 110)
    ax2.set_title("Stage B: cross-family comparison (same manifest)")
    save(fig, "chart_asr_selection")


def chart_participant_photo():
    ids = [f"P{i:02d}" for i in range(1, 11)]
    times = [30, 17.5, 27.5, 12.5, 35, 20, 25, 13.5, 35, 22.5]
    ease = [7, 8, 7, 9, 6, 9, 7.5, 9, 5, 8]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.5), gridspec_kw={"width_ratios": [1.6, 1]})
    ax.bar(ids, times, color=GREY, label="Round 2 sessions (reported, midpoint of ranges)")
    ax.axhline(23.75, color=DEEP, ls="--", lw=1)
    ax.text(9.4, 24.6, "median 23.75 s", fontsize=7.5, ha="right", color=DEEP)
    ax.bar(["R1", "R2", "R3"], [5, 4, 5], color=MINT, label="Re-test runs R1–R3 after the photo iteration (measured)")
    ax.set_ylabel("Photo analysis time (s)")
    ax.set_title("Photo analysis time: participants vs post-iteration runs")
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    ax.tick_params(axis="x", labelsize=7.5)
    ax2.bar(ids, ease, color=AMBER)
    ax2.axhline(7.55, color=DEEP, ls="--", lw=1)
    ax2.text(9.4, 7.75, "mean 7.55", fontsize=7.5, ha="right", color=DEEP)
    ax2.set_ylim(0, 10.5)
    ax2.set_ylabel("Ease of upload and review (/10)")
    ax2.set_title("Photograph workflow ease (n = 10)")
    ax2.tick_params(axis="x", labelsize=7)
    save(fig, "chart_participant_photo")


def chart_text_ratings():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.4), gridspec_kw={"width_ratios": [1.4, 1]})
    features = ["AI recipe\ngenerator", "Substitutions", "Cooking\nassistant"]
    useful, ease = [4.35, 3.86, 4.71], [4.81, 5.00, 4.93]
    nu, ne = [8, 7, 7], [8, 8, 7]
    b1 = ax.bar([i - 0.18 for i in range(3)], useful, 0.36, label="Usefulness", color=MINT)
    b2 = ax.bar([i + 0.18 for i in range(3)], ease, 0.36, label="Ease", color=AMBER)
    for bars, ns in ((b1, nu), (b2, ne)):
        for bar, n in zip(bars, ns):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, f"{bar.get_height():.2f}\n(n={n})", ha="center", fontsize=7)
    ax.set_xticks(range(3), features)
    ax.set_ylim(0, 5.9)
    ax.set_ylabel("Mean rating (/5)")
    ax.set_title("Text features, 9 participants\n(n shown; missing ratings not imputed)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    times = [1.4, 1.8, 2.0, 1.6, 2.1, 2.4, 1.2, 2.8, 3.0, 1.7]
    labels = ["next", "repeat", "time", "back", "current", "help", "stop", "question", "question", "statement"]
    ax2.bar(range(10), times, color=[MINT] * 7 + [LAV] * 3)
    ax2.set_xticks(range(10), labels, rotation=45, ha="right", fontsize=7.5)
    ax2.axhline(2.0, color=DEEP, ls="--", lw=1)
    ax2.text(9.4, 2.08, "mean 2.00 s", fontsize=7.5, ha="right", color=DEEP)
    ax2.set_ylabel("Response time (s)")
    ax2.set_title("Hands-free: 10 retained attempts\n(70/70 core commands in tally)")
    save(fig, "chart_text_and_voice_ratings")


def chart_memory():
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    labels = ["Photo model\nqwen2.5vl:3b", "Text model\nllama3.2:3b", "Both loaded", "Recipe-photo model\nFLUX.2 Klein (removed)"]
    values = [4.6, 2.6, 7.1, 5.7]
    bars = ax.barh(labels, values, color=[MINT, LAV, DEEP, CORAL])
    for bar, value in zip(bars, values):
        ax.text(value + 0.1, bar.get_y() + bar.get_height() / 2, f"{value} GB", va="center", fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 8.4)
    ax.set_xlabel("Memory reported by Ollama 0.30.10 on the reference M4 Pro (GB)")
    ax.set_title("Local model memory")
    save(fig, "chart_memory")


def chart_rescue_curve():
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10, 3.2))
    days = list(range(0, 6))
    weights = [(5 + 1 - d) / 6 for d in days]
    ax.bar(days, weights, color=AMBER)
    for d, w in zip(days, weights):
        ax.text(d, w + 0.02, f"{w:.2f}", ha="center", fontsize=8)
    ax.set_xlabel("Days until expiry")
    ax.set_ylabel("Urgency weight w(d)")
    ax.set_title("w(d) = (6 − d) / 6 inside the 0–5 day window")
    ax.set_ylim(0, 1.15)
    total = [i / 10 for i in range(0, 61)]
    ax2.plot(total, [1 - math.exp(-t / 1.5) for t in total], color=MINT, lw=2)
    ax2.set_xlabel("Σ w(d) over use-soon foods the recipe uses")
    ax2.set_ylabel("Rescue score")
    ax2.set_title("rescue = 1 − exp(−Σw / 1.5)")
    ax2.set_ylim(0, 1.05)
    for t in (1, 2, 3):
        ax2.plot(t, 1 - math.exp(-t / 1.5), "o", color=DEEP, ms=4)
        ax2.text(t + 0.1, 1 - math.exp(-t / 1.5) - 0.07, f"{1 - math.exp(-t / 1.5):.2f}", fontsize=7.5)
    save(fig, "chart_rescue_score")


def chart_receipts():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    receipts = ["Participant's real\nreceipt (13 rows)", "Market, rendered\n(13 rows)", "Wholesale, rendered\n(11 rows)", "Holdout, written\nafter tuning (12 rows)"]
    final = [1.0, 1.0, 1.0, 1.0]
    ax.bar(range(4), final, 0.55, color=MINT, label="Final line-based pipeline")
    ax.bar([3], [8 / 12], 0.55, color=AMBER, label="Holdout, first unchanged run (8/12)")
    ax.set_xticks(range(4), receipts, fontsize=8)
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("Rows correct on confirmation page")
    ax.set_title("Receipt iteration 2: 49 expected rows, 11 non-food products all removed")
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    save(fig, "chart_receipts")


# ---------------------------------------------------------------- diagrams

def box(ax, x, y, w, h, text, fc=CREAM, ec=DEEP, size=8.5, weight="normal", color="#17231f", radius=0.02):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.006,rounding_size={radius}", fc=fc, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, weight=weight, color=color, wrap=True)


def arrow(ax, x1, y1, x2, y2, color=DEEP, style="-|>", lw=1.1, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=10, color=color, lw=lw, linestyle=ls))


def diagram_architecture():
    fig, ax = plt.subplots(figsize=(11, 6.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    layers = [(0.83, 0.14, "Presentation\n(React 19,\nTypeScript, Vite)", "#eef6ea"), (0.58, 0.2, "Application / API\n(FastAPI,\nPython 3.11)", "#fdf3e1"),
              (0.25, 0.28, "AI and domain services\n(all local)", "#f3eefc"), (0.03, 0.17, "Data", "#e9f2f5")]
    for y, h, label, color in layers:
        ax.add_patch(FancyBboxPatch((0.005, y), 0.99, h, boxstyle="round,pad=0.004,rounding_size=0.015", fc=color, ec="#c9d6cf", lw=0.8))
        ax.text(0.015, y + h / 2, label, fontsize=7.6, weight="bold", va="center", color=DEEP)
    for i, name in enumerate(["Opening film\n+ tour", "Home", "Pantry +\nshopping", "Recipes +\nAI ideas", "Recipe detail\n+ swaps", "Cooking mode\n+ hands-free", "Assistant", "Settings"]):
        box(ax, 0.2 + i * 0.099, 0.85, 0.09, 0.08, name, fc="white", size=6.8)
    routes = ["/pantry\n/verify-ingredients", "/upload-receipt\n/upload-image (stream)", "/recipes /recommend\n/ai-recipes", "/recipes/{id}/substitutes", "/cooking-session\n/transcribe-audio", "/assistant\n/home-insights"]
    for i, name in enumerate(routes):
        box(ax, 0.2 + i * 0.132, 0.605, 0.124, 0.1, name, fc="white", size=6.5)
    ax.text(0.6, 0.748, "JSON over HTTP (Vite proxy /api)  ·  photo results streamed as NDJSON", ha="center", fontsize=7.2, color=GREY)
    arrow(ax, 0.6, 0.845, 0.6, 0.71)
    services = [
        ("Tesseract OCR\n+ receipt_parsing.py\n(lines, quantities,\nabbreviations)", 0.03),
        ("Llama 3.2 3B\n(Ollama)\nrecipes, receipt names,\nswaps, answers", 0.195),
        ("Qwen2.5-VL 3B\n(Ollama)\nphoto → ingredients,\nstreamed + salvaged", 0.36),
        ("Whisper small.en\n(faster-whisper)\nspeech → text", 0.525),
        ("MiniLM + FAISS\nsemantic retrieval\n+ ingredient matching", 0.69),
        ("Deterministic guards\ndiet/allergy rules, taste\nchecks, poultry safety,\nvoice intents, units", 0.855),
    ]
    for i, (text, _) in enumerate(services):
        box(ax, 0.2 + i * 0.132, 0.29, 0.124, 0.17, text, fc="white", size=6.3)
    for x in (0.33, 0.46, 0.59, 0.72, 0.85):
        arrow(ax, x, 0.6, x, 0.465, color=GREY)
    box(ax, 0.2, 0.06, 0.34, 0.1, "SQLite (SQLAlchemy)\nusers, preferences, pantry, recipes,\ncooking sessions, shopping list, scan records", fc="white", size=7)
    box(ax, 0.6, 0.06, 0.34, 0.1, "Local model cache (pinned versions)\nOllama digests · Whisper · MiniLM\nsetup_models.py --check", fc="white", size=7)
    arrow(ax, 0.262, 0.6, 0.262, 0.165, color=DEEP, ls="--")
    ax.text(0.19, 0.225, "only user-confirmed\nitems are written", fontsize=6.8, color=DEEP, ha="right")
    ax.text(0.5, 0.005, "Photos, receipts and audio are processed in memory or deleted straight after inference.", ha="center", fontsize=7.5, color=GREY)
    save(fig, "diagram_architecture")


def diagram_journey():
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.01, 0.62, 0.13, 0.22, "Opening film\n“Open the fridge”\n(once per session)", fc="#1a2b27", color="white", size=8)
    box(ax, 0.17, 0.62, 0.12, 0.22, "“See how it works”\ntour (10 steps,\nonce per session)", fc=LIME, size=8)
    arrow(ax, 0.14, 0.73, 0.17, 0.73)
    tabs = [("Home", "use-soon foods,\nimpact, suggestions"), ("Pantry", "search, categories,\nexpiry, shopping list"), ("Recipes", "search, filters,\nAI ideas, diet divider"), ("Assistant", "pantry-aware chat,\n→ recipe cards"), ("Settings", "diet, allergies,\ncuisines, theme")]
    for i, (name, text) in enumerate(tabs):
        x = 0.33 + i * 0.134
        box(ax, x, 0.62, 0.125, 0.22, f"{name}\n\n{text}", fc=SAGE if i % 2 == 0 else CREAM, size=7.5)
    arrow(ax, 0.29, 0.73, 0.33, 0.73)
    box(ax, 0.33, 0.22, 0.2, 0.2, "Add food sheet\nManual · Receipt · Photo\n→ confirm, edit, add missed", fc="white", size=7.5)
    box(ax, 0.6, 0.22, 0.17, 0.2, "Recipe detail\ningredients (have/missing),\nper-ingredient swaps,\nadd missing to list", fc="white", size=7.5)
    box(ax, 0.82, 0.22, 0.17, 0.2, "Cooking mode\nstep cards, timer,\n“Hey Mimi” hands-free,\nMeal is ready → pantry", fc="white", size=7.5)
    arrow(ax, 0.39, 0.62, 0.43, 0.42)
    arrow(ax, 0.63, 0.62, 0.66, 0.42)
    arrow(ax, 0.77, 0.32, 0.82, 0.32)
    arrow(ax, 0.49, 0.62, 0.68, 0.42, color=GREY, ls="--")
    ax.text(0.33, 0.12, "Use soon → Recipes filtered to that food", fontsize=7.5, color=GREY)
    ax.text(0.6, 0.12, "Back returns to the same scroll position; AI ideas persist", fontsize=7.5, color=GREY)
    save(fig, "diagram_user_journey")


def diagram_acquisition():
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    rows = [
        (0.72, "Receipt\nphoto", ["Upright, greyscale,\nstretch, upscale", "Tesseract OCR", "Code: product lines,\ncounts, sizes,\nabbreviation hints", "Llama names each\nnumbered line\n(JSON schema)", "Name guard +\nnon-food list +\nmerge rows"]),
        (0.42, "Pantry /\nfridge\nphoto", ["Resize to 1,600 px,\ndelete file", "Qwen2.5-VL 3B,\nstreamed", "Salvage complete\nitems, stop loops", "Clean names, map\nunits, drop vague\n/ non-food", "Optional\n“Look closer”\n(4 close-ups)"]),
    ]
    for y, label, steps in rows:
        box(ax, 0.012, y, 0.09, 0.18, label, fc=LIME, size=7.6, weight="bold")
        for i, step in enumerate(steps):
            box(ax, 0.13 + i * 0.12, y, 0.105, 0.18, step, fc="white", size=6.8)
            start = 0.102 if i == 0 else 0.13 + (i - 1) * 0.12 + 0.105
            arrow(ax, start, y + 0.09, 0.13 + i * 0.12, y + 0.09)
    box(ax, 0.012, 0.12, 0.09, 0.18, "Manual\nentry", fc=LIME, size=7.6, weight="bold")
    box(ax, 0.13, 0.12, 0.465, 0.18, "Name, quantity (stepper or typed), unit, category,\nexpiry (estimated from the category if left blank)", fc="white", size=7.2)
    box(ax, 0.745, 0.3, 0.11, 0.5, "Human\nconfirmation\n\nedit · delete ·\nrename · add\nmissed · set\nexpiry · rate\nconfidence", fc="#fde9e4", ec=CORAL, size=7.2, weight="bold")
    box(ax, 0.885, 0.38, 0.105, 0.34, "Pantry\n(SQLite)\n\n+ scan record:\nadditions,\ndeletions,\ntimes", fc=SAGE, size=7.2)
    arrow(ax, 0.715, 0.81, 0.745, 0.72)
    arrow(ax, 0.715, 0.51, 0.745, 0.51)
    ax.plot([0.595, 0.937], [0.21, 0.21], color=GREY, lw=1.1, ls="--")
    arrow(ax, 0.937, 0.21, 0.937, 0.38, color=GREY, ls="--")
    arrow(ax, 0.855, 0.55, 0.885, 0.55)
    ax.text(0.45, 0.02, "AI proposes → the user decides → only confirmed items reach the pantry that every recommendation reads", ha="center", fontsize=8, color=DEEP, weight="bold")
    save(fig, "diagram_acquisition")


def diagram_recommendation():
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.012, 0.55, 0.11, 0.3, "Confirmed pantry\n(names, amounts,\nexpiry dates)", fc=SAGE, size=7.2)
    box(ax, 0.012, 0.08, 0.11, 0.26, "Settings\ndiets · allergies ·\ncuisines · time", fc=SAGE, size=7.2)
    box(ax, 0.16, 0.6, 0.15, 0.25, "Ingredient matching\nanalyse(): head food,\nidentity, variety,\nderived product", fc="white", size=7.2)
    box(ax, 0.16, 0.25, 0.15, 0.25, "MiniLM embeddings\n+ FAISS (L2) top-k\nsemantic candidates", fc="white", size=7.2)
    box(ax, 0.35, 0.4, 0.15, 0.32, "Safety filters\nallergy conflict → removed\ndiet conflict → listed\nlast, labelled", fc="#fde9e4", ec=CORAL, size=7.2)
    box(ax, 0.54, 0.4, 0.2, 0.32, "Score\nrescue = 1 − exp(−Σw/1.5)\nfinal = 0.50·rescue + 0.40·match\n+ 0.06·cuisine + 0.04·time\n(0.90·match if nothing is due)", fc="white", size=7)
    box(ax, 0.78, 0.4, 0.21, 0.32, "Lexicographic sort\n1 fits the diet\n2 uses use-soon food\n3 score, rescue, match,\ncount, cuisine, semantic", fc=LIME, size=7.2)
    for (x1, y1, x2, y2) in [(0.12, 0.7, 0.16, 0.72), (0.12, 0.62, 0.16, 0.38), (0.31, 0.72, 0.35, 0.6), (0.31, 0.38, 0.35, 0.5), (0.5, 0.56, 0.54, 0.56), (0.74, 0.56, 0.78, 0.56)]:
        arrow(ax, x1, y1, x2, y2)
    ax.plot([0.122, 0.425], [0.2, 0.2], color=DEEP, lw=1.1)
    arrow(ax, 0.425, 0.2, 0.425, 0.4)
    ax.text(0.45, 0.2, "Cards show pantry match %, have/missing counts, “Uses X before it expires” and any diet conflict.", ha="left", va="center", fontsize=7.4, color=DEEP)
    save(fig, "diagram_recommendation")


def diagram_ai_recipe():
    fig, ax = plt.subplots(figsize=(11, 4.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    steps = [
        ("Request\n“sweet dish with\nwhat I have”", LIME),
        ("Read intent\ntaste: sweet\npantry-only: yes\nnamed foods/dishes", "white"),
        ("Choose pantry offer\nreference-dish overlap,\nor urgent sweet foods\n+ dessert basics", "white"),
        ("Llama 3.2 3B\nrecipe JSON\n(taste, pantry-only,\navoid-titles in prompt)", "white"),
        ("Checks\nschema, ≥5 ingredients,\ndiet/allergy, taste,\ntitle foods, repeats,\nto-buy, unrelated foods", "#fde9e4"),
        ("Save or reuse\nsame-dish recipe;\nshow idea card", SAGE),
    ]
    for i, (text, colour) in enumerate(steps):
        box(ax, 0.012 + i * 0.164, 0.42, 0.148, 0.42, text, fc=colour, size=7.1)
        if i:
            arrow(ax, 0.012 + (i - 1) * 0.164 + 0.148, 0.63, 0.012 + i * 0.164, 0.63)
    ax.add_patch(FancyArrowPatch((0.74, 0.41), (0.57, 0.41), connectionstyle="arc3,rad=-0.45", arrowstyle="-|>", mutation_scale=11, color=CORAL, lw=1.3))
    ax.text(0.655, 0.12, "failed check → its reason is added to the prompt;\nup to 3 attempts (soft checks keep a fallback)", ha="center", fontsize=7.5, color=CORAL)
    ax.text(0.5, -0.02, "Three variations (classic, quicker, different take) are requested in turn; a failed idea no longer stops the next.", ha="center", fontsize=7.8, color=DEEP)
    save(fig, "diagram_ai_recipe_loop")


def diagram_erd():
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    tables = {
        "users": (0.42, 0.72, ["id PK", "name"]),
        "user_preferences": (0.02, 0.63, ["id PK", "user_id FK", "dietary_restrictions", "allergies", "disliked_ingredients", "preferred_cuisines", "max_cooking_time", "skill_level"]),
        "pantry_items": (0.22, 0.36, ["id PK", "user_id FK", "ingredient", "quantity", "expiry_date", "expiry_estimated", "category"]),
        "vision_scans": (0.02, 0.02, ["scan_id", "user_id FK", "inference/confirmation ms", "initial/final items", "additions, deletions, renames", "user_confidence", "pass_log"]),
        "recipes": (0.64, 0.33, ["id PK", "title, cuisine, difficulty", "ingredients, ingredient_details", "instructions, step_details", "prep/cooking time, servings", "source (TheMealDB/AI)", "image_url"]),
        "cooking_sessions": (0.42, 0.05, ["id PK", "user_id FK", "recipe_id FK", "servings, started_at, ready_at", "current_step, status", "pantry_snapshot"]),
        "cooking_messages": (0.8, 0.02, ["id PK", "session_id FK", "role, content"]),
        "shopping_list_items": (0.82, 0.66, ["id PK", "user_id FK", "recipe_id FK", "ingredient, quantity", "checked"]),
        "saved_recipes · ratings": (0.62, 0.8, ["user_id", "recipe_id / ingredient", "rating"]),
    }
    centres = {}
    for name, (x, y, fields) in tables.items():
        h = 0.045 + 0.034 * len(fields)
        ax.add_patch(FancyBboxPatch((x, y), 0.17, h, boxstyle="round,pad=0.004,rounding_size=0.01", fc="white", ec=DEEP, lw=1))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.045), 0.17, 0.045, boxstyle="round,pad=0.004,rounding_size=0.01", fc=SAGE, ec=DEEP, lw=1))
        ax.text(x + 0.085, y + h - 0.0225, name, ha="center", va="center", fontsize=7.4, weight="bold")
        for i, field in enumerate(fields):
            ax.text(x + 0.008, y + h - 0.06 - i * 0.034, field, fontsize=6.6, va="center")
        centres[name] = (x + 0.085, y + h / 2)
    links = [("users", "user_preferences", "1 : 1"), ("users", "pantry_items", "1 : M"), ("users", "cooking_sessions", "1 : M"), ("users", "shopping_list_items", "1 : M"),
             ("users", "saved_recipes · ratings", "1 : M"), ("recipes", "cooking_sessions", "1 : M"), ("cooking_sessions", "cooking_messages", "1 : M"),
             ("pantry_items", "vision_scans", "confirmed from"), ("recipes", "shopping_list_items", "0..1 : M")]
    for a, b, label in links:
        (x1, y1), (x2, y2) = centres[a], centres[b]
        ax.plot([x1, x2], [y1, y2], color=GREY, lw=0.8, zorder=0)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, label, fontsize=6.5, color=DEEP, ha="center", bbox=dict(fc="white", ec="none", pad=0.5))
    save(fig, "diagram_erd")


def diagram_timeline():
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.set_xlim(-2, 94)
    ax.set_ylim(0, 1)
    ax.axis("off")
    # day 0 = 29 June 2026
    events = [  # (day, label x, date, text, above?, colour)
        (0, 4, "29 Jun", "Version 1 prototype\nmock detection, HITL,\nFAISS hybrid, Ollama\n(Decisions 1–10)", True, GREY),
        (26, 26, "late Jul", "Preliminary report\n(receipt OCR +\nLLM parsing)", False, GREY),
        (72, 58, "9–12 Sep", "Version 2: five-screen\napp, cooking sessions,\nTheMealDB, 3 models\n(D11–23)", True, LAV),
        (81, 62, "19–24 Sep", "Model selection:\ndetectors → Qwen 3B,\nWhisper small.en,\nLlama 3.2 3B (D25–33)", False, MINT),
        (87, 80, "24–27 Sep", "Round 1 (n=1),\nRound 2 (n=10);\nreceipt + photo\niterations (D34–36)", True, AMBER),
        (91, 86, "28 Sep", "Version 3 (green):\niterations 2–4,\nfridge film, tour\n(D37–47)", False, CORAL),
    ]
    ax.plot([0, 92], [0.5, 0.5], color=DEEP, lw=2)
    for day, lx, date, text, above, colour in events:
        ty = 0.8 if above else 0.2
        ax.plot([day, lx], [0.5, ty + (-0.12 if above else 0.12)], color=colour, lw=1)
        ax.plot(day, 0.5, "o", color=colour, ms=9, mec=DEEP, zorder=3)
        ax.text(lx, ty, f"{date}\n{text}", ha="center", va="center", fontsize=7.2, bbox=dict(fc="white", ec=colour, boxstyle="round,pad=0.3"))
    ax.text(46, 0.55, "Jul–Aug: expansion to the full application (draft Figure 6)", ha="center", fontsize=7.2, color=GREY)
    save(fig, "diagram_timeline")


if __name__ == "__main__":
    for make in (chart_detector, chart_qwen, chart_photo_iteration, chart_round2_scenes, chart_text_models, chart_asr,
                 chart_participant_photo, chart_text_ratings, chart_memory, chart_rescue_curve, chart_receipts,
                 diagram_architecture, diagram_journey, diagram_acquisition, diagram_recommendation, diagram_ai_recipe,
                 diagram_erd, diagram_timeline):
        make()
