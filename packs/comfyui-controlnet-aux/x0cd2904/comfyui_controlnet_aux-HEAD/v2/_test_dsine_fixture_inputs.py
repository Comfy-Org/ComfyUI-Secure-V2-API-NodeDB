import torch
def base_fixture(case):
    y,x=torch.meshgrid(torch.arange(64),torch.arange(64),indexing='ij')
    if case=='checker_rgb64':
        checker=((x//8+y//8)%2).to(torch.float32)
        return torch.stack((checker,1-checker,((3*x+5*y)%256).to(torch.float32)/255),dim=-1)[None]
    if case=='fp16_rgba_batch2':
        r=((3*x+5*y)%256).to(torch.float32)/255
        g=x.to(torch.float32)/63
        b=y.to(torch.float32)/63
        alpha=((x+y)%4).to(torch.float32)/3
        frame=torch.stack((r,g,b,alpha),dim=-1)
        return torch.stack((frame,torch.flip(frame,dims=(0,1))),dim=0).to(torch.float16)
    raise AssertionError('unknown native NormalBAE fixture')

def retained_bae_fixture(case):
    import torch
    if case=='gray64':return base_fixture('checker_rgb64')[...,:1]
    if case=='checker128':return base_fixture('checker_rgb64')
    if case=='fp16_rgba_batch2_128':return base_fixture('fp16_rgba_batch2')
    if case=='rectangular96x64':return torch.linspace(0,1,96*64*3).reshape(1,96,64,3)
    if case=='rgba_float32_64':return base_fixture('fp16_rgba_batch2')[0:1].float()
    if case=='default512_gray':return base_fixture('checker_rgb64')[...,:1]
    raise AssertionError('unknown distinct BAE native fixture')

def fixture(case):
    import torch
    if case=='gray64':return retained_bae_fixture('gray64')
    if case=='checker128':return retained_bae_fixture('checker128')
    if case=='fp16_rgba_batch2':return retained_bae_fixture('fp16_rgba_batch2_128')
    if case=='rectangular96x64':return retained_bae_fixture('rectangular96x64')
    if case=='rgba_float32_64':return retained_bae_fixture('rgba_float32_64')
    if case=='default512_gray':return retained_bae_fixture('default512_gray')
    raise AssertionError('Unknown distinct DSINE fixture')
