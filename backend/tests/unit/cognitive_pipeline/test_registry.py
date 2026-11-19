"""The generic registry — lookup, duplicate handling, and the overwrite flag."""

import pytest
from app.services.cognitive_pipeline.registry import Registry


class TestRegistry:
    def test_register_and_get(self):
        registry = Registry[str]()
        registry.register("greeting", "Hello")
        assert registry.get("greeting") == "Hello"

    def test_get_missing_raises_key_error(self):
        registry = Registry[int]()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_register_duplicate_raises_key_error(self):
        registry = Registry[str]()
        registry.register("key", "first")
        with pytest.raises(KeyError, match="already registered"):
            registry.register("key", "second")

    def test_register_duplicate_with_overwrite(self):
        registry = Registry[str]()
        registry.register("key", "first")
        registry.register("key", "second", overwrite=True)
        assert registry.get("key") == "second"

    def test_list_empty(self):
        registry = Registry[int]()
        assert registry.list() == []

    def test_list_returns_sorted_names(self):
        registry = Registry[str]()
        registry.register("z", "last")
        registry.register("a", "first")
        registry.register("m", "middle")
        assert registry.list() == ["a", "m", "z"]

    def test_unregister(self):
        registry = Registry[str]()
        registry.register("key", "value")
        assert "key" in registry
        registry.unregister("key")
        assert "key" not in registry

    def test_unregister_nonexistent_does_not_raise(self):
        registry = Registry[str]()
        registry.unregister("nonexistent")  # should not raise

    def test_contains(self):
        registry = Registry[str]()
        registry.register("present", "value")
        assert "present" in registry
        assert "absent" not in registry

    def test_len(self):
        registry = Registry[str]()
        assert len(registry) == 0
        registry.register("a", "1")
        registry.register("b", "2")
        assert len(registry) == 2

    def test_typed_registry(self):
        """Verify that the generic type is enforced at runtime."""
        registry = Registry[int]()
        registry.register("one", 1)
        registry.register("two", 2)
        assert registry.get("one") + registry.get("two") == 3
