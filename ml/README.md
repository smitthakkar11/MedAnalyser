# MedAnalyser — machine learning

The core intelligence of MedAnalyser is a **locally trained scikit-learn model**.
No external, hosted or paid AI API is called anywhere in the pipeline.

```
Public dataset → clean & deduplicate → split → fit vocabulary on train only
              → compare models → select → evaluate → save artifacts
              → FastAPI loads artifacts once → inference
```

Training happens here, offline. The API never trains; it only loads artifacts.

---

## Dataset card

| | |
| --- | --- |
| **Name** | Disease Symptom Description Dataset |
| **Source** | <https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset> |
| **Licence** | CC BY-SA 4.0 |
| **Files** | `dataset.csv`, `Symptom-severity.csv`, `symptom_Description.csv`, `symptom_precaution.csv` |
| **Raw rows** | 4,920 |
| **Unique cases after deduplication** | **304** |
| **Target** | Disease — 41 classes |
| **Features** | 131 binary symptoms |
| **Committed to git?** | No — fetched by `python -m ml.ingest`, checksums recorded in `data/raw/checksums.json` |

### Why it was chosen

It is the only openly-licensed public dataset that matches MedAnalyser's core
task: *a set of reported symptoms → a candidate condition*. The UCI repository
has better-provenanced clinical data, but every medical dataset there is
single-condition (heart disease, diabetes, one dermatology panel), which cannot
support a general symptom intake. The companion severity, description and
precaution files also feed later phases — question ordering and the knowledge
base — without introducing another source.

### What is wrong with it — read this before trusting any metric

This dataset is **synthetic and templated**, and the analysis in
[`reports/eda.md`](reports/eda.md) shows exactly how:

| Finding | Value | Consequence |
| --- | --- | --- |
| Rows per disease | exactly 120, for all 41 | Generated, not sampled |
| Exact duplicate rows | 4,616 of 4,920 (**93.8%**) | A naive split leaks |
| Unique cases | 304 | The real dataset is tiny |
| Symptom sets mapping to >1 disease | **0** | Labels are a pure function of features |

The distinct symptom sets for a disease are the leave-one-out subsets of one
canonical set. The data is, in effect, a **deterministic lookup table**. Any
model able to represent a lookup table scores near-perfectly on it, which is why
published notebooks on this dataset routinely report ~100% accuracy and why that
figure is meaningless.

It also contains no age, sex, duration, episode severity or laboratory values,
so the model cannot use them however clinically useful they would be.

**Conclusion: this model demonstrates a correctly built ML pipeline. It is not
clinically validated and must never be presented as a diagnosis.**

---

## How leakage is prevented

The order of operations is deliberate:

1. **Deduplicate first.** Before any split. Splitting the raw file puts copies
   of the same record on both sides.
2. **Stratified split** on the deduplicated cases (80/20), so every disease
   appears in both.
3. **Fit the vocabulary on the training split only.** Building it from the full
   dataset would leak the test split's feature space.
4. **Cross-validate on the training split** for model selection; the test split
   is touched exactly once, at the end.

Training quantifies what step 1 buys. Splitting *before* deduplication leaves
around a quarter of test cases also present in training and yields 1.000
accuracy — the inflated number, reproduced deliberately so it can be compared
against the honest one.

There are no patient identifiers, so a patient-level (grouped) split is not
applicable; the case-level deduplication is the equivalent safeguard here.

---

## Model selection

Four candidates, plus a floor:

| Model | Role |
| --- | --- |
| `DummyClassifier(most_frequent)` | Baseline. With 41 near-balanced classes the floor is ~2% macro F1 — without it, "1.00" means nothing. |
| Logistic Regression | Linear baseline, `class_weight="balanced"`. |
| Random Forest | Non-linear, gives feature importances for explanation. |
| XGBoost | Gradient boosting. |

Selection metric is **cross-validated macro F1**, not accuracy: macro weights
each disease equally, so a model that ignores rare classes is penalised.

Because the dataset saturates several algorithms, logistic regression and random
forest **tie at 1.000**. The tie is broken on the metric that actually matters
in the product — *perturbation robustness*, below — which random forest wins.

Current results are in [`reports/condition_model_evaluation.md`](reports/condition_model_evaluation.md).

### Robustness: the number worth quoting

Every case in the dataset is a clean subset of a canonical symptom set. Real
users report a few symptoms, forget others and mention irrelevant ones. Training
therefore sweeps that, averaged over 20 random draws:

| Input | Accuracy |
| --- | --- |
| All symptoms | ~1.00 |
| All symptoms + 3 unrelated | ~0.97 |
| Only 3 symptoms | ~0.79 |
| Only 2 symptoms | ~0.56 |
| Only 1 symptom | ~0.39 |
| Only 3 symptoms + 2 unrelated | ~0.53 |

This is the honest picture. It is also a product requirement in disguise: the
model needs most of a symptom set to be useful, which is precisely why the
assessment flow asks follow-up questions rather than predicting from the first
thing a user types. `MIN_INFORMATIVE_SYMPTOMS` in the inference service is set
from these measurements, not guessed.

---

## Class imbalance

After deduplication, classes hold 5–10 cases each — mild imbalance. Handled with
stratified splitting, `class_weight="balanced"`, and macro-averaged metrics.

Resampling was considered and **rejected**: SMOTE interpolates between neighbours
in feature space, which for binary symptom vectors invents symptom combinations
no one reported, and doing that to an already-synthetic dataset adds noise rather
than information.

---

## Layout

```
ml/
├── config.py        # paths, seed, split sizes
├── ingest.py        # download + checksum the raw dataset
├── dataset.py       # load, clean, deduplicate
├── eda.py           # writes reports/eda.md
├── training/        # train_condition_model.py
├── evaluation/      # metric helpers
├── artifacts/       # model.joblib, vectoriser, label encoder, metadata.json
├── reports/         # generated EDA and evaluation reports
└── data/raw/        # downloaded dataset (gitignored)
```

Production inference lives in `backend/app/services/ml/condition_prediction/`.
**Feature construction is shared**: `features.py` is imported by both the
training script and the API, so the vector a model is fitted on cannot drift
from the one it is served — the most common cause of silent train/serve skew.

---

## Reproducing

From the repository root, with the backend virtualenv active:

```bash
pip install -e "backend[ml]"          # pandas, xgboost, certifi
python -m ml.ingest                   # download + checksum (~30 KB)
python -m ml.eda                      # writes reports/eda.md
python -m ml.training.train_condition_model
```

Training takes well under a minute on a laptop and is fully seeded
(`RANDOM_SEED = 42`), so results are reproducible.

XGBoost needs OpenMP on macOS: `brew install libomp`.

### Artifacts

| File | Purpose |
| --- | --- |
| `condition_model.joblib` | The fitted estimator (~400 KB, compressed) |
| `condition_model_vectoriser.joblib` | Symptom vocabulary and multi-hot encoder |
| `condition_model_label_encoder.joblib` | Disease label encoding |
| `condition_model_metadata.json` | Version, dataset, split, features, all metrics, caveats |

`.joblib` files are gitignored — they are build outputs and are pickle-format,
so they are tied to the scikit-learn version that produced them. The metadata
and reports **are** committed, so the evaluation can be reviewed without
retraining.

---

## Limitations

- Synthetic data; not real patient records; not clinically validated.
- 304 unique cases across 41 classes — small, so test estimates are noisy.
- Only 41 conditions. Anything outside them is forced into one of the 41; the
  model has no "I don't know" class.
- No age, sex, duration, severity or laboratory features.
- Scores are relative model outputs, **not calibrated probabilities**. No
  calibration has been performed or validated.
- The symptom vocabulary is fixed at 131 tokens; free-text synonym mapping
  ("high temperature" → `high_fever`) is not yet implemented.

### Planned

- Real clinical datasets (UCI heart disease, dermatology, thyroid) for
  lab-value components, evaluated separately rather than concatenated into a
  fake multimodal model.
- Rule-based NLP for synonym mapping, so free text reaches the vocabulary.
- Probability calibration, if and only if it can be validated.
