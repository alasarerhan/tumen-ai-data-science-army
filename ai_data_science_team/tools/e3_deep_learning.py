"""e3_deep_learning.

Deterministic deep-learning training tools supporting **E3 — Deep
Learning (Tabular / Time Series)** (spec
``docs/specs/E3-deep-learning.md``).

Implements the ``engine=dl`` dispatch for the E1 multi-engine
trainer with pure PyTorch.  TabNet and TFT adapters are referenced
but not bundled because pytorch-tabnet and pytorch-forecasting
are not in the platform's runtime requirements.  Adding them is a
one-line ``import`` change.

Public surface
--------------

* :func:`detect_device` — pick cuda → mps → cpu.
* :func:`build_mlp_classifier(n_features, n_classes, hidden, dropout)`
  — pure-PyTorch MLP module factory.
* :func:`build_lstm_forecaster(n_features, hidden, layers, horizon)`
  — LSTM regressor factory for time-series.
* :func:`train_mlp_classifier` — fit a MLP with early stopping +
  ReduceLROnPlateau; returns dict with loss curve + meta.
* :func:`train_lstm_forecaster` — fit LSTM forecaster on a
  supervised (X, y) tensor pair.
* :func:`E3_DEEP_LEARNING_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
    _TORCH_AVAILABLE = True
except Exception:  # pragma: no cover
    _TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------


def detect_device(prefer: Optional[str] = None) -> str:
    """Return one of ``"cuda"``, ``"mps"``, ``"cpu"`` based on availability.

    If ``prefer`` is given and available, that wins.  Otherwise
    cuda → mps → cpu.
    """
    if not _TORCH_AVAILABLE:
        return "cpu"
    if prefer == "cuda" and torch.cuda.is_available():
        return "cuda"
    if prefer == "mps" and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------


if _TORCH_AVAILABLE:

    class _MLP(nn.Module):
        def __init__(self, n_features: int, n_classes: int, hidden: Sequence[int], dropout: float):
            super().__init__()
            layers: List[nn.Module] = []
            prev = n_features
            for h in hidden:
                layers.append(nn.Linear(prev, h))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
                prev = h
            layers.append(nn.Linear(prev, n_classes))
            self.net = nn.Sequential(*layers)

        def forward(self, x):
            return self.net(x)

    class _LSTMRegressor(nn.Module):
        def __init__(self, n_features: int, hidden: int, layers: int, horizon: int):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_features,
                hidden_size=hidden,
                num_layers=layers,
                batch_first=True,
            )
            self.head = nn.Linear(hidden, horizon)

        def forward(self, x):
            # x: (B, T, F)
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :])

    class _LSTMClassifier(nn.Module):
        def __init__(self, n_features: int, hidden: int, layers: int, n_classes: int):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_features,
                hidden_size=hidden,
                num_layers=layers,
                batch_first=True,
            )
            self.head = nn.Linear(hidden, n_classes)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :])

else:  # pragma: no cover
    _MLP = None  # type: ignore
    _LSTMRegressor = None  # type: ignore
    _LSTMClassifier = None  # type: ignore


def build_mlp_classifier(
    n_features: int,
    n_classes: int,
    hidden: Sequence[int] = (128, 64),
    dropout: float = 0.2,
) -> Any:
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed; cannot build MLP")
    return _MLP(n_features, n_classes, hidden, dropout)


def build_mlp_regressor(
    n_features: int,
    hidden: Sequence[int] = (128, 64),
    dropout: float = 0.2,
) -> Any:
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed; cannot build MLP")
    return _MLP(n_features, 1, hidden, dropout)


def build_lstm_forecaster(
    n_features: int,
    hidden: int = 64,
    layers: int = 1,
    horizon: int = 1,
) -> Any:
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed; cannot build LSTM")
    return _LSTMRegressor(n_features, hidden, layers, horizon)


def build_lstm_classifier(
    n_features: int,
    n_classes: int,
    hidden: int = 64,
    layers: int = 1,
) -> Any:
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed; cannot build LSTM")
    return _LSTMClassifier(n_features, hidden, layers, n_classes)


# ---------------------------------------------------------------------------
# Training loops
# ---------------------------------------------------------------------------


def _torch_seed(seed: int) -> None:
    if _TORCH_AVAILABLE:
        torch.manual_seed(seed)
        np.random.seed(seed)


def _make_optimizer(model, lr: float, weight_decay: float):
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed")
    return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)


def _make_scheduler(optimizer, factor: float, patience: int):
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed")
    return torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=factor, patience=patience
    )


def train_mlp_classifier(
    X: np.ndarray,
    y: np.ndarray,
    *,
    hidden: Sequence[int] = (128, 64),
    dropout: float = 0.2,
    epochs: int = 50,
    batch_size: int = 32,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    early_stopping_patience: int = 5,
    lr_factor: float = 0.5,
    lr_patience: int = 3,
    val_split: float = 0.2,
    seed: int = 0,
    device: Optional[str] = None,
    task_type: str = "classification",
    verbose: bool = False,
) -> Dict[str, Any]:
    """Train an MLP classifier (or regressor) with early stopping.

    Returns a dict with ``model``, ``loss_curve`` (per-epoch
    train/val loss), ``metric_curve`` (val accuracy or val MSE
    for regressors), and a ``meta`` block.
    """
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed")
    if X.ndim != 2:
        raise ValueError("X must be 2-D")
    if y.shape[0] != X.shape[0]:
        raise ValueError("X and y must have the same number of rows")

    _torch_seed(seed)
    dev = detect_device(device)
    dev_obj = torch.device(dev)

    if task_type == "classification":
        classes, y_int = np.unique(y, return_inverse=True)
        n_classes = len(classes)
        target_is_class = True
    elif task_type == "regression":
        n_classes = 1
        target_is_class = False
        y_int = y.astype(np.float32)
    else:
        raise ValueError(f"Unknown task_type: {task_type!r}")

    # Train/val split
    n = X.shape[0]
    idx = np.arange(n)
    rng = np.random.RandomState(seed)
    rng.shuffle(idx)
    n_val = max(int(round(n * val_split)), 1)
    val_idx = idx[:n_val]
    tr_idx = idx[n_val:]
    X_tr = X[tr_idx].astype(np.float32)
    y_tr = y_int[tr_idx]
    X_va = X[val_idx].astype(np.float32)
    y_va = y_int[val_idx]

    model = build_mlp_classifier(X.shape[1], n_classes, hidden, dropout).to(dev_obj)
    optim = _make_optimizer(model, lr, weight_decay)
    sched = _make_scheduler(optim, lr_factor, lr_patience)

    tr_loader = DataLoader(
        TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr)),
        batch_size=batch_size,
        shuffle=True,
    )
    va_X = torch.from_numpy(X_va).to(dev_obj)
    va_y = torch.from_numpy(y_va).to(dev_obj)

    loss_curve: List[Dict[str, float]] = []
    best_val: float = float("inf")
    best_state: Optional[Dict[str, Any]] = None
    bad = 0

    for epoch in range(epochs):
        model.train()
        train_loss_sum = 0.0
        n_batches = 0
        for xb, yb in tr_loader:
            xb = xb.to(dev_obj)
            yb = yb.to(dev_obj)
            optim.zero_grad()
            logits = model(xb)
            if target_is_class:
                loss = F.cross_entropy(logits, yb.long())
            else:
                loss = F.mse_loss(logits.squeeze(-1), yb.float())
            loss.backward()
            optim.step()
            train_loss_sum += float(loss.item())
            n_batches += 1
        train_loss = train_loss_sum / max(n_batches, 1)

        model.eval()
        with torch.no_grad():
            vlog = model(va_X)
            if target_is_class:
                v_loss = float(F.cross_entropy(vlog, va_y.long()).item())
                v_pred = vlog.argmax(dim=-1)
                v_acc = float((v_pred == va_y).float().mean().item())
                v_metric = v_acc
            else:
                v_loss = float(F.mse_loss(vlog.squeeze(-1), va_y.float()).item())
                v_metric = v_loss  # MSE for regressors.
        sched.step(v_loss)
        loss_curve.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": float(train_loss),
                "val_loss": float(v_loss),
                "val_metric": float(v_metric),
            }
        )
        if v_loss < best_val - 1e-6:
            best_val = v_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
        if verbose:
            print(
                f"epoch {epoch+1}/{epochs} train_loss={train_loss:.4f} "
                f"val_loss={v_loss:.4f} val_metric={v_metric:.4f}"
            )
        if bad >= early_stopping_patience:
            if verbose:
                print(f"early stop at epoch {epoch+1}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    return {
        "model": model,
        "device": dev,
        "loss_curve": loss_curve,
        "metric_curve": [p["val_metric"] for p in loss_curve],
        "best_val_loss": float(best_val),
        "n_epochs_run": len(loss_curve),
        "early_stopped": bad >= early_stopping_patience,
        "meta": {
            "architecture": "mlp",
            "task_type": task_type,
            "n_classes": int(n_classes) if target_is_class else 0,
            "hidden": list(hidden),
            "dropout": float(dropout),
            "lr": float(lr),
            "batch_size": int(batch_size),
            "weight_decay": float(weight_decay),
            "n_features": int(X.shape[1]),
            "val_split": float(val_split),
        },
    }


def train_lstm_forecaster(
    X: np.ndarray,
    y: np.ndarray,
    *,
    hidden: int = 64,
    layers: int = 1,
    horizon: int = 1,
    epochs: int = 30,
    batch_size: int = 32,
    lr: float = 1e-3,
    early_stopping_patience: int = 5,
    seed: int = 0,
    device: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Train an LSTM forecaster on (X, y) where X is (B, T, F)."""
    if not _TORCH_AVAILABLE:
        raise RuntimeError("PyTorch not installed")
    if X.ndim != 3:
        raise ValueError("X must be 3-D (samples, timesteps, features)")

    _torch_seed(seed)
    dev = detect_device(device)
    dev_obj = torch.device(dev)

    n = X.shape[0]
    idx = np.arange(n)
    rng = np.random.RandomState(seed)
    rng.shuffle(idx)
    n_val = max(int(round(n * 0.2)), 1)
    val_idx = idx[:n_val]
    tr_idx = idx[n_val:]

    X_tr = torch.from_numpy(X[tr_idx].astype(np.float32)).to(dev_obj)
    y_tr = torch.from_numpy(y[tr_idx].astype(np.float32)).to(dev_obj)
    X_va = torch.from_numpy(X[val_idx].astype(np.float32)).to(dev_obj)
    y_va = torch.from_numpy(y[val_idx].astype(np.float32)).to(dev_obj)

    model = build_lstm_forecaster(X.shape[2], hidden, layers, horizon).to(dev_obj)
    optim = _make_optimizer(model, lr, 1e-4)
    sched = _make_scheduler(optim, 0.5, 3)

    tr_loader = DataLoader(
        TensorDataset(X_tr, y_tr), batch_size=batch_size, shuffle=True
    )
    loss_curve: List[Dict[str, float]] = []
    best_val = float("inf")
    best_state: Optional[Dict[str, Any]] = None
    bad = 0

    for epoch in range(epochs):
        model.train()
        total = 0.0
        n_b = 0
        for xb, yb in tr_loader:
            optim.zero_grad()
            pred = model(xb)
            loss = F.mse_loss(pred, yb)
            loss.backward()
            optim.step()
            total += float(loss.item())
            n_b += 1
        train_loss = total / max(n_b, 1)
        model.eval()
        with torch.no_grad():
            v_pred = model(X_va)
            v_loss = float(F.mse_loss(v_pred, y_va).item())
        sched.step(v_loss)
        loss_curve.append(
            {
                "epoch": float(epoch + 1),
                "train_loss": float(train_loss),
                "val_loss": float(v_loss),
                "val_metric": float(v_loss),
            }
        )
        if v_loss < best_val - 1e-6:
            best_val = v_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
        if verbose:
            print(f"epoch {epoch+1}/{epochs} val_mse={v_loss:.4f}")
        if bad >= early_stopping_patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return {
        "model": model,
        "device": dev,
        "loss_curve": loss_curve,
        "metric_curve": [p["val_metric"] for p in loss_curve],
        "best_val_loss": float(best_val),
        "n_epochs_run": len(loss_curve),
        "early_stopped": bad >= early_stopping_patience,
        "meta": {
            "architecture": "lstm",
            "hidden": int(hidden),
            "layers": int(layers),
            "horizon": int(horizon),
        },
    }


__all__ = [
    "detect_device",
    "build_mlp_classifier",
    "build_mlp_regressor",
    "build_lstm_forecaster",
    "build_lstm_classifier",
    "train_mlp_classifier",
    "train_lstm_forecaster",
    "E3_DEEP_LEARNING_TOOL_NAMES",
]


E3_DEEP_LEARNING_TOOL_NAMES = [
    "e3_detect_device",
    "e3_train_mlp",
    "e3_train_lstm",
    "e3_build_mlp",
    "e3_build_lstm",
]
