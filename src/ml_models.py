"""
ml_models.py
Two ML models that power the "intelligence" of the SDN controller:

1. TrafficClassifier (RandomForestClassifier)
   Classifies each flow into voice/video/web/bulk from flow-level features
   (packet size, inter-arrival time, duration, demand). In a real SDN this
   is what would run on features exported by switches via OpenFlow stats.

2. CongestionPredictor (RandomForestRegressor)
   Predicts NEXT-interval utilization of a link from its recent utilization
   history (a small time-series/lag-feature model). The controller uses this
   forecast to steer new flows away from soon-to-be-congested links
   *before* they actually congest - i.e. proactive/adaptive routing instead
   of reactive routing.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.preprocessing import LabelEncoder

FEATURES = ["avg_pkt_size", "avg_iat_ms", "duration_s", "demand_mbps", "n_packets"]


class TrafficClassifier:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=150, max_depth=8, random_state=42)
        self.encoder = LabelEncoder()

    def fit(self, df: pd.DataFrame):
        X = df[FEATURES].values
        y = self.encoder.fit_transform(df["true_class"].values)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)
        report = classification_report(
            y_test, y_pred, target_names=self.encoder.classes_, output_dict=True
        )
        importances = dict(zip(FEATURES, self.model.feature_importances_.tolist()))

        return {
            "accuracy": acc,
            "confusion_matrix": cm.tolist(),
            "labels": self.encoder.classes_.tolist(),
            "report": report,
            "feature_importance": importances,
        }

    def predict(self, df: pd.DataFrame):
        X = df[FEATURES].values
        preds = self.model.predict(X)
        return self.encoder.inverse_transform(preds)


class CongestionPredictor:
    """Predicts next-step link utilization (%) from a short history window."""

    def __init__(self, window=4):
        self.window = window
        self.model = RandomForestRegressor(n_estimators=120, max_depth=6, random_state=42)

    def _make_lag_features(self, series: np.ndarray, exog: np.ndarray = None):
        """exog[i] = extra features known at the *start* of interval i (optional)."""
        X, y = [], []
        for i in range(self.window, len(series)):
            x = series[i - self.window:i]
            if exog is not None:
                x = np.concatenate([x, exog[i]])
            X.append(x)
            y.append(series[i])
        return np.array(X), np.array(y)

    def fit(self, utilization_series: np.ndarray):
        X, y = self._make_lag_features(utilization_series)
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        self.model.fit(X_train, y_train)
        if len(X_test) > 0:
            preds = self.model.predict(X_test)
            mae = float(np.mean(np.abs(preds - y_test)))
        else:
            mae = None
        return {"mae_percent_points": mae}

    def predict_next(self, recent_window: np.ndarray) -> float:
        return float(self.model.predict(recent_window.reshape(1, -1))[0])

    def fit_pooled(self, series_list, exog_list=None, residual_col=None):
        """Train one model on many links' histories at once (offline pre-training).

        residual_col: index of a feature column to use as a baseline forecast;
        the forest then learns only the correction on top of it
        (forecast = X[:, residual_col] + model(X)).
        """
        self.residual_col = residual_col
        X_parts, y_parts = [], []
        if exog_list is None:
            exog_list = [None] * len(series_list)
        for s, ex in zip(series_list, exog_list):
            X, y = self._make_lag_features(np.asarray(s), ex)
            if len(X):
                X_parts.append(X)
                y_parts.append(y)
        X, y = np.vstack(X_parts), np.concatenate(y_parts)
        if residual_col is not None:
            y = y - X[:, residual_col]
        self.model.fit(X, y)
        return self

    def predict_many(self, windows: np.ndarray) -> np.ndarray:
        """windows: (n_links, window [+ exog]) -> next-interval utilization % per link."""
        pred = self.model.predict(windows)
        if getattr(self, "residual_col", None) is not None:
            pred = pred + windows[:, self.residual_col]
        return pred
