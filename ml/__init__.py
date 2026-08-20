"""Offline machine-learning workspace for MedAnalyser.

Training, evaluation and data preparation live here, deliberately outside the
FastAPI application: the API never trains, it only loads artifacts. Feature
construction is imported from `app.services.ml` so training and serving share
one implementation.
"""
