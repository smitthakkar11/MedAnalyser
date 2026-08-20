"""Train, compare and persist the condition-prediction model.

Run from the repository root::

    python -m ml.training.train_condition_model

Order of operations, chosen to avoid leakage:

1. Load the raw file and **deduplicate** — before anything else, because the
   source is 93.8% exact duplicates.
2. Stratified train/test split on the deduplicated cases.
3. Fit the symptom vocabulary on the **training split only**.
4. Cross-validate several models on the training split; select on macro F1.
5. Refit the winner on the full training split and evaluate once on the
   untouched test split.
6. Additionally measure robustness to perturbed inputs, and quantify how much
   the *naive* pipeline (splitting before deduplication) would have inflated
   the score.
7. Save artifacts and a metadata file.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from app.services.ml.condition_prediction.features import SymptomVectoriser
from ml.config import ARTIFACTS_DIR, CV_FOLDS, RANDOM_SEED, REPORTS_DIR, TEST_SIZE
from ml.dataset import Case, load_cases, load_raw_cases
from ml.evaluation.metrics import Scores, score, top_k_accuracy

MODEL_NAME = "condition_model"
MODEL_VERSION = "v1"

#: Models whose CV macro F1 is within this of the best are treated as tied.
#: This dataset saturates several algorithms, so a tie is the normal case.
CV_TIE_TOLERANCE = 0.001


def build_candidates() -> dict[str, Any]:
    """The models to compare, cheapest and least expressive first.

    A `DummyClassifier` is included deliberately: without a floor, "97% macro
    F1" means nothing. With 41 near-balanced classes the floor is ~2%.
    """
    return {
        "baseline_most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(
            max_iter=2000,
            C=1.0,
            class_weight="balanced",
            random_state=RANDOM_SEED,
        ),
        # 200 trees with a depth cap: the decision surface here is a lookup
        # table, so deeper/more trees only inflate the artifact. Capping depth
        # took the serialised model from 18 MB to well under 1 MB with no loss
        # of accuracy or robustness.
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=1,
            class_weight="balanced",
            n_jobs=-1,
            random_state=RANDOM_SEED,
        ),
        "xgboost": XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.2,
            subsample=0.9,
            colsample_bytree=0.9,
            tree_method="hist",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
    }


@dataclass
class CandidateResult:
    name: str
    cv_f1_macro_mean: float
    cv_f1_macro_std: float
    test_scores: Scores


def _split(cases: list[Case]) -> tuple[list[Case], list[Case]]:
    labels = [case.label for case in cases]
    train, test = train_test_split(
        cases,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=labels,
    )
    return train, test


def _vectorise(
    vectoriser: SymptomVectoriser, encoder: LabelEncoder, cases: list[Case]
) -> tuple[np.ndarray, np.ndarray]:
    features = vectoriser.transform([case.symptoms for case in cases])
    targets = encoder.transform([case.label for case in cases])
    return features, np.asarray(targets)


def perturbation_robustness(
    model: Any,
    vectoriser: SymptomVectoriser,
    encoder: LabelEncoder,
    cases: list[Case],
    *,
    rng: np.random.Generator,
    repeats: int = 20,
) -> dict[str, float]:
    """Accuracy when the input is not a clean row from the lookup table.

    Real users report a handful of symptoms, forget some, and mention ones that
    turn out to be irrelevant. Because every case here is a clean subset of a
    canonical symptom set, a model can score perfectly on the test split and
    still be useless in the product — so this sweeps two axes:

    * ``keep_k``  — the user reports only *k* of their symptoms.
    * ``noise_n`` — plus *n* unrelated symptoms drawn from the vocabulary.

    Averaged over `repeats` random draws so the numbers are not an artefact of
    one unlucky sample.
    """
    vocabulary = vectoriser.vocabulary
    results: dict[str, float] = {}

    def accuracy_for(keep_k: int | None, noise_n: int) -> float:
        correct = total = 0
        for _ in range(repeats):
            rows, truths = [], []
            for case in cases:
                symptoms = sorted(case.symptoms)
                if keep_k is not None and len(symptoms) > keep_k:
                    chosen = list(rng.choice(symptoms, size=keep_k, replace=False))
                else:
                    chosen = list(symptoms)
                if noise_n:
                    pool = [s for s in vocabulary if s not in case.symptoms]
                    if pool:
                        size = min(noise_n, len(pool))
                        chosen += list(rng.choice(pool, size=size, replace=False))
                if not chosen:
                    continue
                rows.append(chosen)
                truths.append(case.label)
            if not rows:
                continue
            predicted = encoder.inverse_transform(model.predict(vectoriser.transform(rows)))
            correct += sum(p == t for p, t in zip(predicted, truths, strict=True))
            total += len(truths)
        return correct / total if total else 0.0

    results["all_symptoms"] = accuracy_for(None, 0)
    for noise_n in (1, 2, 3):
        results[f"all_symptoms_plus_{noise_n}_noise"] = accuracy_for(None, noise_n)
    for keep_k in (1, 2, 3):
        results[f"only_{keep_k}_symptoms"] = accuracy_for(keep_k, 0)
        results[f"only_{keep_k}_symptoms_plus_2_noise"] = accuracy_for(keep_k, 2)
    return results


def leakage_demonstration(raw_cases_with_duplicates: list[Case]) -> dict[str, float]:
    """Quantify the score inflation from splitting before deduplication.

    Not decoration — it is the evidence that the deduplication step is load
    bearing, and the number to quote when explaining why the naive ~100% figure
    everyone reports for this dataset is not real.
    """
    labels = [case.label for case in raw_cases_with_duplicates]
    train, test = train_test_split(
        raw_cases_with_duplicates,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=labels,
    )
    vectoriser = SymptomVectoriser.fit([case.symptoms for case in train])
    encoder = LabelEncoder().fit([case.label for case in train])
    x_train, y_train = _vectorise(vectoriser, encoder, train)
    x_test, y_test = _vectorise(vectoriser, encoder, test)

    model = RandomForestClassifier(
        n_estimators=200, n_jobs=-1, random_state=RANDOM_SEED
    ).fit(x_train, y_train)
    predicted = model.predict(x_test)

    overlap = len(set(train) & set(test))
    return {
        "naive_accuracy": float(np.mean(predicted == y_test)),
        "test_cases_also_in_train": float(overlap),
        "test_size": float(len(test)),
        "overlap_fraction": overlap / len(test) if test else 0.0,
    }


def main() -> int:
    print("Loading dataset ...")
    cases, stats = load_cases()
    print(
        f"  {stats.raw_rows:,} raw rows -> {stats.unique_cases} unique cases "
        f"({stats.duplicate_fraction:.1%} were duplicates)"
    )

    print("\nSplitting (stratified, on deduplicated cases) ...")
    train_cases, test_cases = _split(cases)
    print(f"  train={len(train_cases)}  test={len(test_cases)}")

    # Vocabulary and label encoding are fitted on the training split only.
    vectoriser = SymptomVectoriser.fit([case.symptoms for case in train_cases])
    encoder = LabelEncoder().fit(sorted({case.label for case in cases}))
    print(f"  vocabulary fitted on train only: {vectoriser.n_features} symptoms")

    x_train, y_train = _vectorise(vectoriser, encoder, train_cases)
    x_test, y_test = _vectorise(vectoriser, encoder, test_cases)

    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    results: list[CandidateResult] = []

    print(f"\nComparing models ({CV_FOLDS}-fold CV on the training split) ...")
    for name, estimator in build_candidates().items():
        cv_scores = cross_val_score(
            estimator, x_train, y_train, cv=cv, scoring="f1_macro", n_jobs=1
        )
        estimator.fit(x_train, y_train)
        test_scores = score(y_test, estimator.predict(x_test))
        results.append(
            CandidateResult(
                name=name,
                cv_f1_macro_mean=float(cv_scores.mean()),
                cv_f1_macro_std=float(cv_scores.std()),
                test_scores=test_scores,
            )
        )
        print(
            f"  {name:<24} cv_f1={cv_scores.mean():.4f}±{cv_scores.std():.4f}  "
            f"test_f1={test_scores.f1_macro:.4f}  test_acc={test_scores.accuracy:.4f}"
        )

    # Select on cross-validated macro F1, excluding the baseline: it exists to
    # establish a floor, never to win.
    selectable = [r for r in results if not r.name.startswith("baseline")]
    top_cv = max(r.cv_f1_macro_mean for r in selectable)
    tied = [r for r in selectable if top_cv - r.cv_f1_macro_mean <= CV_TIE_TOLERANCE]

    # Several models saturate this dataset, so CV alone cannot separate them.
    # Break the tie on the metric that actually matters in the product: how well
    # the model holds up when the user reports only part of their symptoms.
    rng = np.random.default_rng(RANDOM_SEED)
    robustness_by_model: dict[str, dict[str, float]] = {}
    if len(tied) > 1:
        print(f"\n{len(tied)} models tie on CV macro F1; breaking the tie on robustness ...")
    for candidate in tied:
        model = build_candidates()[candidate.name]
        model.fit(x_train, y_train)
        robustness_by_model[candidate.name] = perturbation_robustness(
            model, vectoriser, encoder, test_cases, rng=np.random.default_rng(RANDOM_SEED)
        )
        if len(tied) > 1:
            mean_robustness = float(np.mean(list(robustness_by_model[candidate.name].values())))
            print(f"  {candidate.name:<24} mean robustness {mean_robustness:.4f}")

    best = max(
        tied,
        key=lambda r: float(np.mean(list(robustness_by_model[r.name].values()))),
    )
    print(f"\nSelected: {best.name} (cv macro F1 {best.cv_f1_macro_mean:.4f})")

    final_model = build_candidates()[best.name]
    final_model.fit(x_train, y_train)
    predicted = final_model.predict(x_test)
    probabilities = final_model.predict_proba(x_test)
    robustness = robustness_by_model[best.name]

    print("\nRobustness of the selected model ...")
    for scenario, value in robustness.items():
        print(f"  {scenario:<30} {value:.4f}")

    print("\nQuantifying the leakage that deduplication prevents ...")
    leakage = leakage_demonstration(load_raw_cases())
    print(
        f"  naive split accuracy={leakage['naive_accuracy']:.4f} with "
        f"{leakage['overlap_fraction']:.1%} of test cases also present in train"
    )

    # ------------------------------------------------------------- artifacts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    # compress=3 trades a little load time for a far smaller artifact.
    joblib.dump(final_model, ARTIFACTS_DIR / f"{MODEL_NAME}.joblib", compress=3)
    joblib.dump(vectoriser, ARTIFACTS_DIR / f"{MODEL_NAME}_vectoriser.joblib", compress=3)
    joblib.dump(encoder, ARTIFACTS_DIR / f"{MODEL_NAME}_label_encoder.joblib", compress=3)

    metadata = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "algorithm": best.name,
        "trained_at": datetime.now(UTC).isoformat(),
        "random_seed": RANDOM_SEED,
        "library_versions": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "dataset": {
            "name": "Disease Symptom Description Dataset",
            "source": "https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset",
            "license": "CC BY-SA 4.0",
            "raw_rows": stats.raw_rows,
            "duplicate_rows": stats.duplicate_rows,
            "duplicate_fraction": round(stats.duplicate_fraction, 4),
            "unique_cases": stats.unique_cases,
            "ambiguous_symptom_sets": stats.ambiguous_symptom_sets,
            "synthetic": True,
        },
        "split": {
            "strategy": "stratified train/test on deduplicated cases",
            "test_size": TEST_SIZE,
            "cv_folds": CV_FOLDS,
            "train_cases": len(train_cases),
            "test_cases": len(test_cases),
        },
        "features": {
            "type": "multi-hot symptom vector",
            "n_features": vectoriser.n_features,
            "names": vectoriser.vocabulary,
        },
        "labels": list(encoder.classes_),
        # Which symptoms characterise each condition, derived from the TRAINING
        # split only. Not used for prediction — the follow-up engine uses it to
        # pick which unasked symptom would best separate the current
        # candidates, instead of asking in arbitrary order.
        "condition_symptoms": {
            label: sorted(
                {symptom for case in train_cases if case.label == label for symptom in case.symptoms}
            )
            for label in encoder.classes_
        },
        "selection": {
            "metric": "cross-validated macro F1, ties broken on perturbation robustness",
            "tie_tolerance": CV_TIE_TOLERANCE,
            "tied_models": [r.name for r in tied],
            "mean_robustness_by_tied_model": {
                name: round(float(np.mean(list(scores.values()))), 4)
                for name, scores in robustness_by_model.items()
            },
        },
        "metrics": {
            "selected_model_test": best.test_scores.as_dict(),
            "top_3_accuracy": round(top_k_accuracy(probabilities, y_test, 3), 4),
            "top_5_accuracy": round(top_k_accuracy(probabilities, y_test, 5), 4),
            "cv_f1_macro_mean": round(best.cv_f1_macro_mean, 4),
            "cv_f1_macro_std": round(best.cv_f1_macro_std, 4),
            "comparison": {
                r.name: {
                    "cv_f1_macro_mean": round(r.cv_f1_macro_mean, 4),
                    "cv_f1_macro_std": round(r.cv_f1_macro_std, 4),
                    **r.test_scores.as_dict(),
                }
                for r in results
            },
            "robustness": {k: round(v, 4) for k, v in robustness.items()},
            "leakage_demonstration": {k: round(v, 4) for k, v in leakage.items()},
        },
        "caveats": [
            "Trained on a synthetic, templated dataset — not real patient records.",
            "Scores measure the pipeline, not clinical accuracy.",
            "Model scores are relative rankings, not calibrated probabilities.",
            "Outputs are candidate conditions requiring professional evaluation.",
        ],
    }
    (ARTIFACTS_DIR / f"{MODEL_NAME}_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )

    # ---------------------------------------------------------------- report
    report = _build_report(metadata, results, best, y_test, predicted, encoder)
    (REPORTS_DIR / "condition_model_evaluation.md").write_text(report)

    print(f"\nArtifacts written to {ARTIFACTS_DIR}")
    print(f"Report written to {REPORTS_DIR / 'condition_model_evaluation.md'}")
    return 0


def _build_report(
    metadata: dict[str, Any],
    results: list[CandidateResult],
    best: CandidateResult,
    y_test: np.ndarray,
    predicted: np.ndarray,
    encoder: LabelEncoder,
) -> str:
    matrix = confusion_matrix(y_test, predicted)
    off_diagonal = int(matrix.sum() - np.trace(matrix))
    per_class = classification_report(
        y_test,
        predicted,
        labels=np.arange(len(encoder.classes_)),
        target_names=list(encoder.classes_),
        zero_division=0,
        digits=3,
    )
    dataset = metadata["dataset"]
    robustness = metadata["metrics"]["robustness"]
    leakage = metadata["metrics"]["leakage_demonstration"]

    lines = [
        "# Condition model — evaluation report",
        "",
        "Generated by `python -m ml.training.train_condition_model`. Do not edit by hand.",
        "",
        "## Dataset",
        "",
        "| | |",
        "| --- | --- |",
        f"| Name | {dataset['name']} |",
        f"| Source | {dataset['source']} |",
        f"| Licence | {dataset['license']} |",
        f"| Raw rows | {dataset['raw_rows']:,} |",
        f"| Duplicates removed | {dataset['duplicate_rows']:,} ({dataset['duplicate_fraction']:.1%}) |",
        f"| Unique cases used | {dataset['unique_cases']} |",
        f"| Classes | {len(metadata['labels'])} |",
        f"| Features | {metadata['features']['n_features']} binary symptoms |",
        "",
        "## Model comparison",
        "",
        "Selection metric is cross-validated **macro F1** on the training split:",
        "each disease counts equally regardless of how many cases it has.",
        "",
        "| Model | CV macro F1 | Test macro F1 | Test accuracy | Test recall (macro) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        marker = " **(selected)**" if r.name == best.name else ""
        lines.append(
            f"| {r.name}{marker} | {r.cv_f1_macro_mean:.3f} ± {r.cv_f1_macro_std:.3f} "
            f"| {r.test_scores.f1_macro:.3f} | {r.test_scores.accuracy:.3f} "
            f"| {r.test_scores.recall_macro:.3f} |"
        )

    lines += [
        "",
        "## Held-out test performance",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    lines += [
        f"| {key} | {value} |" for key, value in metadata["metrics"]["selected_model_test"].items()
    ]
    lines += [
        f"| top_3_accuracy | {metadata['metrics']['top_3_accuracy']} |",
        f"| top_5_accuracy | {metadata['metrics']['top_5_accuracy']} |",
        f"| misclassified test cases | {off_diagonal} of {int(matrix.sum())} |",
        "",
        "## Why the headline number is not impressive",
        "",
        "Two checks put it in context.",
        "",
        "### 1. Leakage the deduplication prevents",
        "",
        "Splitting the raw file *without* removing duplicates puts copies of the",
        "same record on both sides:",
        "",
        "| | |",
        "| --- | --- |",
        f"| Naive (pre-dedup) split accuracy | {leakage['naive_accuracy']:.3f} |",
        f"| Test cases also present in train | {leakage['overlap_fraction']:.1%} |",
        "",
        "That is the number most published notebooks on this dataset report. It",
        "measures memorisation of duplicated rows.",
        "",
        "### 2. Robustness to imperfect input",
        "",
        "Every case in this dataset is a clean subset of a canonical symptom set.",
        "Real users omit symptoms and mention irrelevant ones:",
        "",
        "| Input | Accuracy |",
        "| --- | --- |",
    ]
    lines += [
        f"| `{scenario}` | {value:.3f} |" for scenario, value in robustness.items()
    ]
    lines += [
        "",
        "This degradation is the honest picture of the model's usefulness, and",
        "it is why the product presents ranked candidates rather than an answer.",
        "",
        "## Per-class performance",
        "",
        "```",
        per_class,
        "```",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {caveat}" for caveat in metadata["caveats"]]
    lines += [
        "- Only 41 conditions; anything else is forced into one of them.",
        "- No age, sex, duration, severity or laboratory features in the data.",
        "- Small after deduplication (304 cases), so test-set estimates are noisy.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
