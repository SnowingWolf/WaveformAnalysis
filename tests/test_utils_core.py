import numpy as np
import pytest
import time
from waveform_analysis.core.utils import (
    Profiler, OneTimeGenerator, exporter, 
    get_plugins_from_context, get_plugin_dtype, get_plugin_title
)

def test_profiler():
    p = Profiler()
    with p.timeit("test"):
        time.sleep(0.01)
    
    assert p.counts["test"] == 1
    assert p.durations["test"] >= 0.01
    
    summary = p.summary()
    assert "test" in summary
    
    p.reset()
    assert p.counts["test"] == 0
    
    # Test decorator
    @p.profile("decorated")
    def func():
        time.sleep(0.01)
    
    func()
    assert p.counts["decorated"] == 1
    
    # Test decorator without key
    @p.profile()
    def func2():
        pass
    func2()
    assert p.counts["func2"] == 1

def test_one_time_generator():
    def gen():
        yield 1
        yield 2
    
    otg = OneTimeGenerator(gen(), name="test_gen")
    it = iter(otg)
    assert next(it) == 1
    assert next(it) == 2
    
    with pytest.raises(StopIteration):
        next(it)
    
    # Try to iterate again
    with pytest.raises(RuntimeError, match="already been consumed"):
        for x in otg:
            pass

def test_exporter():
    # Test export_self=True
    export_s, all_s = exporter(export_self=True)
    assert "exporter" in all_s
    
    export, __all__ = exporter()
    
    @export
    class MyClass:
        pass
    
    @export(name="MyFunc")
    def func():
        pass
    
    # Test @export(name=...) as decorator factory
    factory = export()
    @factory
    def func3():
        pass
    
    CONST = export(42, name="CONST")
    
    assert "MyClass" in __all__
    assert "MyFunc" in __all__
    assert "func3" in __all__
    assert "CONST" in __all__
    assert CONST == 42
    
    # Test error when no name provided for constant
    with pytest.raises(ValueError, match="it has no __name__"):
        export(123)

def test_visualization_utils():
    class MockPlugin:
        provides = "test_data"
        dtype = "float64"
        name = "Test Plugin"
    
    class MockContext:
        def __init__(self):
            self._plugins = {"test": MockPlugin()}
    
    ctx = MockContext()
    plugins = get_plugins_from_context(ctx)
    assert "test" in plugins
    
    assert get_plugins_from_context(None) == {}
    
    # Test get_plugin_dtype
    assert get_plugin_dtype("raw_files", {}) == "List[List[str]]"
    assert get_plugin_dtype("waveforms", {}) == "List[np.ndarray]"
    assert get_plugin_dtype("test", plugins) == "float64"
    assert get_plugin_dtype("unknown", plugins) == "Unknown"
    
    # Test get_plugin_title
    assert get_plugin_title("test", {}, plugins) == "Test Plugin"
    assert get_plugin_title("unknown", {"plugin_class": "UnknownClass"}, {}) == "UnknownClass"
    assert get_plugin_title("unknown", {}, {}) == "unknown"

    # Test plugin with different name attributes
    class NamePlugin:
        plugin_name = "PluginName"
    assert get_plugin_title("name_p", {}, {"name_p": NamePlugin()}) == "PluginName"
    
    class DisplayPlugin:
        display_name = "DisplayName"
    assert get_plugin_title("disp_p", {}, {"disp_p": DisplayPlugin()}) == "DisplayName"
    
    class ClassNamePlugin:
        pass
    assert get_plugin_title("class_p", {}, {"class_p": ClassNamePlugin()}) == "ClassNamePlugin"
