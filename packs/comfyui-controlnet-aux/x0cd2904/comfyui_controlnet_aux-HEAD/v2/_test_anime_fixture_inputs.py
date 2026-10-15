import torch
def fixture(case):
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
