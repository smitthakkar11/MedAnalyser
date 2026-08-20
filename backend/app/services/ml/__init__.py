"""Machine-learning services.

MedAnalyser's core intelligence is a locally trained scikit-learn model. No
external or paid AI API is used anywhere in this package.

Training lives outside the application, under `ml/` at the repository root;
this package contains only what is needed to *load* an artifact and run
inference. Feature construction is deliberately shared between the two (see
`condition_prediction.features`) so the vector a model is trained on and the
vector it is served can never diverge.
"""
