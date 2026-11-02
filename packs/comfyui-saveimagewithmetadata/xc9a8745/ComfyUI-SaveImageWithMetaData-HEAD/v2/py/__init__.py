# Secure Nodes V2: the original patched execution.PromptExecutor.execute and
# execution.get_input_data here (functools prefix wrappers) to record the running prompt,
# the executor and the saving node's id. A V2 pack cannot patch the host; the save node
# reads the same facts from the broker (graph.execution_metadata), see _v2_capture.py.
