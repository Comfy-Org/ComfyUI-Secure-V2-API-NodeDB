"""Original NLF model behavior; no substitute predictor or hosted algorithm."""
import logging
import torch
log=logging.getLogger(__name__)
device=torch.device('cpu')
offload_device=torch.device('cpu')

def check_jit_script_function():
    if torch.jit.script.__name__ != 'script':
        module = torch.jit.script.__module__
        qualname = getattr(torch.jit.script, '__qualname__', 'unknown')
        code_file = None
        try:
            code_file = torch.jit.script.__code__.co_filename
            code_line = torch.jit.script.__code__.co_firstlineno
            log.warning(f'torch.jit.script has been modified by another custom node.\n  Function name: {torch.jit.script.__name__}\n  Module: {module}\n  Qualified name: {qualname}\n  Defined in: {code_file}:{code_line}\nThis may cause issues with the NLF model.')
        except Exception:
            log.warning('--------------------------------')
            log.warning(f'torch.jit.script function is: {torch.jit.script.__name__} from module {module}, this has been modified by another custom node. This may cause issues with the NLF model.')
            log.warning('--------------------------------')

def construct_nlf_from_stream(stream, warmup=True):
    model = torch.jit.load(stream).eval()
    if warmup:
        log.info('Warming up NLF model...')
        dummy_input = torch.zeros(1, 3, 256, 256, device=device)
        jit_profiling_prev_state = torch._C._jit_set_profiling_executor(True)
        try:
            for _ in range(2):
                _ = model.detect_smpl_batched(dummy_input)
        finally:
            torch._C._jit_set_profiling_executor(jit_profiling_prev_state)
        log.info('NLF model warmed up')
    model = model.to(offload_device)
    return model

def predict_nlf_original(model, images, per_batch=-1):
    check_jit_script_function()
    model = model.to(device)
    num_images = images.shape[0]
    if per_batch == -1:
        batch_size = num_images
    else:
        batch_size = per_batch
    all_boxes = []
    all_joints3d_nonparam = []
    for i in range(0, num_images, batch_size):
        end_idx = min(i + batch_size, num_images)
        batch_images = images[i:end_idx]
        jit_profiling_prev_state = torch._C._jit_set_profiling_executor(True)
        try:
            pred = model.detect_smpl_batched(batch_images.permute(0, 3, 1, 2).to(device))
        finally:
            torch._C._jit_set_profiling_executor(jit_profiling_prev_state)
        if 'boxes' in pred:
            all_boxes.extend(pred['boxes'])
        if 'joints3d_nonparam' in pred:
            all_joints3d_nonparam.extend(pred['joints3d_nonparam'])
    model = model.to(offload_device)
    all_boxes = [box.to(offload_device) for box in all_boxes]
    all_joints3d_nonparam = [joints.to(offload_device) for joints in all_joints3d_nonparam]
    pose_results = {'joints3d_nonparam': [all_joints3d_nonparam]}
    formatted_boxes = []
    for box in all_boxes:
        if box.numel() == 0 or box.shape[0] == 0:
            formatted_boxes.append([0.0, 0.0, 0.0, 0.0])
        else:
            bbox_values = box[0, :4].cpu().tolist()
            formatted_boxes.append(bbox_values)
    return (pose_results, formatted_boxes)
