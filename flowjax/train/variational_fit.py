"""Basic training script for fitting a flow using variational inference."""

from collections.abc import Callable
from typing import Any

import equinox as eqx
import jax.random as jr
import optax
from jax import Array
from tqdm import tqdm

from flowjax.distributions import AbstractDistribution
from flowjax.train.train_utils import step

PyTree = Any


def fit_to_variational_target(
    key: Array,
    dist: AbstractDistribution,
    loss_fn: Callable,
    *,
    steps: int = 100,
    learning_rate: float = 5e-4,
    optimizer: optax.GradientTransformation | None = None,
    filter_spec: Callable | PyTree = eqx.is_inexact_array,
    return_best: bool = True,
    show_progress: bool = True,
) -> tuple[AbstractDistribution, list]:
    """Train a distribution (e.g. a flow) by variational inference.

    Args:
        key: Jax PRNGKey.
        dist: Distribution object, trainable parameters are found using
            equinox.is_inexact_array.
        loss_fn: The loss function to optimize (e.g. the ElboLoss).
        steps: The number of training steps to run. Defaults to 100.
        learning_rate: Learning rate. Defaults to 5e-4.
        optimizer: Optax optimizer. If provided, this overrides the default Adam
            optimizer, and the learning_rate is ignored. Defaults to None.
        filter_spec: Equinox `filter_spec` for specifying trainable parameters. Either
            a callable `leaf -> bool`, or a PyTree with prefix structure matching `dist`
            with True/False values. Defaults to eqx.is_inexact_array.
        return_best: Whether the result should use the parameters where the minimum loss
            was reached (when True), or the parameters after the last update (when
            False). Defaults to True.
        show_progress: Whether to show progress bar. Defaults to True.

    Returns:
        A tuple containing the trained distribution and the losses.
    """
    if optimizer is None:
        optimizer = optax.adam(learning_rate)

    params, static = eqx.partition(dist, filter_spec)
    opt_state = optimizer.init(params)

    losses = []

    best_params = params
    keys = tqdm(jr.split(key, steps), disable=not show_progress)

    for key in keys:
        params, opt_state, loss = step(
            params,
            static,
            key,
            optimizer=optimizer,
            opt_state=opt_state,
            loss_fn=loss_fn,
        )
        losses.append(loss.item())
        keys.set_postfix({"loss": loss.item()})
        if loss.item() == min(losses):
            best_params = params
    params = best_params if return_best else params
    return eqx.combine(params, static), losses
