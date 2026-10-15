CONTRACT_SHA256='03fc9931fd8fb58e3fce31501dd8af28a572260f5a3164625d5e482481ecf11c'
import hashlib,json
from pathlib import Path
import torch
def validate_original_state(state,which):
    raw=Path(__file__).with_name('_test_midas_original414_contract.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==CONTRACT_SHA256
    census=json.loads(raw)[which]
    assert isinstance(state,dict) and len(state)==414 and list(state)==[row['key'] for row in census['ordered_tensors']]
    assert hasattr(state,'_metadata')==census['has_metadata_attribute'] and getattr(state,'_metadata',None)==census['metadata']
    total=0
    for row in census['ordered_tensors']:
        value=state[row['key']]
        assert isinstance(value,torch.Tensor) and value.device.type=='cpu' and value.layout==torch.strided and str(value.dtype)==row['dtype'] and list(value.shape)==row['shape']
        size=value.numel()*value.element_size();assert size==row['bytes']
        assert hashlib.sha256(value.detach().contiguous().numpy().tobytes()).hexdigest()==row['sha256']
        total+=size
    assert total==census['tensor_bytes']==489511940
