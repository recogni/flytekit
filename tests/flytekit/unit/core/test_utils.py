import functools
import typing
from collections import OrderedDict

import pytest

import flytekit
from flytekit import FlyteContextManager, task
from flytekit.configuration import ImageConfig, SerializationSettings
from flytekit.core.utils import ClassDecorator, _dnsify, timeit, str2bool
from flytekit.tools.translator import get_serializable_task
from tests.flytekit.unit.test_translator import default_img


@pytest.mark.parametrize(
    "input,expected",
    [
        ("test.abc", "test-abc"),
        ("test", "test"),
        ("", ""),
        (".test", "test"),
        ("Test", "test"),
        ("test.", "test"),
        ("test-", "test"),
        ("test$", "test"),
        ("te$t$", "tet"),
        ("t" * 64, f"da4b348ebe-{'t'*52}"),
    ],
)
def test_dnsify(input, expected):
    assert _dnsify(input) == expected


def test_timeit():
    ctx = FlyteContextManager.current_context()
    ctx.user_space_params._decks = []

    from flytekit.deck import DeckField

    with timeit("Set disable_deck to False"):
        kwargs = {}
        kwargs["disable_deck"] = False
        kwargs["deck_fields"] = (DeckField.TIMELINE.value,)

    ctx = FlyteContextManager.current_context()
    time_info_list = ctx.user_space_params.timeline_deck.time_info
    names = [time_info["Name"] for time_info in time_info_list]
    # check if timeit works for flytekit level code
    assert "Set disable_deck to False" in names

    @task(**kwargs)
    def t1() -> int:
        @timeit("Download data")
        def download_data():
            return "1"

        data = download_data()

        with timeit("Convert string to int"):
            return int(data)

    t1()

    time_info_list = flytekit.current_context().timeline_deck.time_info
    names = [time_info["Name"] for time_info in time_info_list]

    # check if timeit works for user level code
    assert "Download data" in names
    assert "Convert string to int" in names


def test_class_decorator():
    class my_decorator(ClassDecorator):
        def __init__(self, func=None, *, foo="baz"):
            self.foo = foo
            super().__init__(func, foo=foo)

        def execute(self, *args, **kwargs):
            return self.task_function(*args, **kwargs)

        def get_extra_config(self):
            return {"foo": self.foo}

    @task
    @my_decorator(foo="bar")
    def t() -> str:
        return "hello world"

    ss = SerializationSettings(
        project="project",
        domain="domain",
        version="version",
        env={"FOO": "baz"},
        image_config=ImageConfig(default_image=default_img, images=[default_img]),
    )

    assert t() == "hello world"
    assert t.get_config(settings=ss) == {}

    ts = get_serializable_task(OrderedDict(), ss, t)
    assert ts.template.config == {"foo": "bar"}

    @task
    @my_decorator
    def t() -> str:
        return "hello world"

    ts = get_serializable_task(OrderedDict(), ss, t)
    assert ts.template.config == {"foo": "baz"}


def test_class_decorator_keeps_assigned_annotations():
    class my_decorator(ClassDecorator):
        def execute(self, *args, **kwargs):
            return self.task_function(*args, **kwargs)

        def get_extra_config(self):
            return {}

    def f(a: int) -> str:
        return str(a)

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    wrapper.__annotations__ = {**wrapper.__annotations__, "b": typing.Optional[str]}

    decorated = my_decorator(wrapper)
    assert typing.get_type_hints(decorated) == {"a": int, "b": typing.Optional[str], "return": str}


def test_str_2_bool():
    assert str2bool("true")
    assert not str2bool("false")
    assert str2bool("True")
    assert str2bool("t")
    assert not str2bool("f")
    assert str2bool("1")
