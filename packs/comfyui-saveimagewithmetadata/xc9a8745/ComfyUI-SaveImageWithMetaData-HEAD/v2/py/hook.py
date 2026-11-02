# Secure Nodes V2: the original set these globals from executor hooks (pre_execute and
# pre_get_input_data, installed by py/__init__.py). A V2 node cannot patch the executor;
# _v2_capture.bind_snapshot fills them from the broker's execution metadata, under
# _v2_capture.SAVE_LOCK, before the capture code runs.
current_prompt = {}
current_extra_data = {}
prompt_executer = None
current_save_image_node_id = -1
