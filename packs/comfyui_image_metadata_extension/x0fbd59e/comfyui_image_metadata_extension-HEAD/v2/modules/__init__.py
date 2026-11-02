# Secure Nodes V2: the original monkeypatched execution.PromptExecutor.execute and
# execution.get_input_data here. Executor state is read through the broker instead
# (graph.execution_metadata; see _v2_capture.py), so nothing is patched at import.
