import numpy as np

from waveform_analysis import Context, Plugin


class DummyPlugin(Plugin):
    provides = "dummy_data"
    dtype = [("val", "f4")]

    def compute(self, context, run_id):
        import time

        time.sleep(0.1)  # Simulate work
        return np.zeros(10, dtype=self.dtype)


def test_profiler():
    st = Context(storage_dir="./test_profiler_data")
    st.register(DummyPlugin)

    print("Running plugin first time (compute + save)...")
    data = st.get_data("run_001", "dummy_data")
    print(f"Result: {data}")

    print("\nRunning plugin second time (load from cache)...")
    data = st.get_data("run_001", "dummy_data")
    print(f"Result: {data}")
    print("\nProfiling Summary:")
    print(st.profiling_summary)


if __name__ == "__main__":
    test_profiler()
