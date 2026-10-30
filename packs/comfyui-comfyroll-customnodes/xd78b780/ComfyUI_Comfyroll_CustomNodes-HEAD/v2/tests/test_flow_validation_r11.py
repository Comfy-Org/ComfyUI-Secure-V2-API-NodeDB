"""Real public Core validation must surface Flow's explicit refusal."""
import asyncio
import inspect
from _current_sdk_test_support import module
W=module('secure_output_writers')
def test_flow_validator_names_an_always_present_widget():
    assert list(inspect.signature(W.CR_OutputFlowFrames.validate_inputs).parameters)==['filename_prefix']
    assert W.CR_OutputFlowFrames.validate_inputs(filename_prefix='CR')==W.PENDING
def test_actual_core_reports_flow_custom_validation_error(monkeypatch):
    import execution
    import nodes
    node='R11Flow';cls=W.CR_OutputFlowFrames;cls.GET_SCHEMA()
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS,node,cls)
    prompt={'1':{'class_type':node,'inputs':{'output_folder':'','current_image':None,'filename_prefix':'CR','current_frame':0}}}
    valid,errors,_=asyncio.run(execution.validate_inputs('r11',prompt,'1',{}))
    assert valid is False
    matches=[e for e in errors if e['type']=='custom_validation_failed' and e['extra_info']['input_name']=='filename_prefix']
    assert matches and W.PENDING in matches[0]['details']
