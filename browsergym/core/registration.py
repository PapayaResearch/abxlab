from functools import partial
from typing import Type

import gymnasium as gym

from .env import BrowserEnv
from .task import AbstractBrowserTask


class frozen_partial:
    """
    Freeze some keyword arguments of a function.

    """

    def __init__(self, func, **frozen_kwargs):
        self.func = func
        self.frozen_kwargs = frozen_kwargs

    def __call__(self, *args, **kwargs):
        # check overlap between kwargs and frozen_kwargs
        clashing_kwargs = set(self.frozen_kwargs) & set(kwargs)  # key set intersection
        if clashing_kwargs:
            raise ValueError(f"Illegal attempt to override frozen parameters {clashing_kwargs}.")
        # merge the two dicts
        kwargs = kwargs | self.frozen_kwargs

        return self.func(*args, **kwargs)


def register_task(
    id: str,
    task_class: Type[AbstractBrowserTask],
    task_kwargs: dict = {},
    default_task_kwargs: dict = {},
    nondeterministic: bool = True,
    *args,
    **kwargs,
):
    """
    Registers a browser task as a gym environment with its unique id.

    Args:
        id: the id of the task to register (will be prepended by "browsergym/").
        task_class: the task class to register.
        task_kwargs: frozen task arguments (can not be overloaded at environment creation time).
        task_kwargs_default: default task arguments (can be overloaded at environment creation time).
        nondeterministic: whether the task cannot be guaranteed deterministic transitions.
        *args: additional sequential arguments for either the gym or the browsergym environment.
        *kwargs: additional keyword arguments for either the gym or the browsergym environment.
    """
    if task_kwargs and default_task_kwargs:
        clashing_kwargs = set(task_kwargs) & set(default_task_kwargs)
        if clashing_kwargs:
            raise ValueError(
                f"Illegal attempt to register Browsergym environment {id} with both frozen and default values for task parameters {clashing_kwargs}."
            )

    # Special handling for nudging arena tasks
    if id.startswith("nudgingarena."):
        print(f"Registering nudging arena task with config: {task_kwargs}")
        # For nudging arena tasks, don't use any frozen parameters
        gym.register(
            id=f"browsergym/{id}",
            entry_point=lambda *env_args, **env_kwargs: BrowserEnv(
                task_entrypoint=task_class,  # Pass the class directly
                task_kwargs=task_kwargs,
                *env_args,
                **env_kwargs
            ),
            nondeterministic=nondeterministic,
            *args,
            **kwargs,
        )
    else:
        # Standard task registration with frozen task_kwargs
        task_entrypoint = task_class
        task_entrypoint = frozen_partial(task_class, **task_kwargs)
        task_entrypoint = partial(task_entrypoint, **default_task_kwargs)
        
        gym.register(
            id=f"browsergym/{id}",
            entry_point=lambda *env_args, **env_kwargs: BrowserEnv(
                task_entrypoint=task_entrypoint,
                task_kwargs={},  # Empty dict for non-nudging tasks
                *env_args,
                **env_kwargs
            ),
            nondeterministic=nondeterministic,
            *args,
            **kwargs,
        )

    print(f"Registered task {id} with kwargs {task_kwargs}")