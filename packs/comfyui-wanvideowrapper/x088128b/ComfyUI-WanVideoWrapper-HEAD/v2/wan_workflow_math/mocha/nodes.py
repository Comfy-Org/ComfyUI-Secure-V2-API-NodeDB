"""Original mathematical helpers only; no V1 node classes/host globals."""
import torch
from ... import wan_workflow_cpu as mm

def rope_params_mocha(max_seq_len, dim, theta=10000, L_test=25, k=0, start=0):
    assert dim % 2 == 0
    exponents = torch.arange(0, dim, 2, dtype=torch.float64).div(dim)
    inv_theta_pow = 1.0 / torch.pow(theta, exponents)
    
    if k > 0:
        print(f"RifleX: Using {k}th freq")
        inv_theta_pow[k-1] = 0.9 * 2 * torch.pi / L_test
        
    freqs = torch.outer(torch.arange(start, max_seq_len), inv_theta_pow)
    freqs = torch.polar(torch.ones_like(freqs), freqs)
    return freqs


@torch.autocast(device_type=mm.get_autocast_device(mm.get_torch_device()), enabled=False)
def rope_apply_mocha(x, grid_sizes, freqs):
    n, c = x.size(2), x.size(3) // 2

    split_size_1 = c - 2 * (c // 3)
    split_size_2 = c // 3
    split_size_3 = c // 3
    freqs_0, freqs_1, freqs_2 = freqs.split([split_size_1, split_size_2, split_size_3], dim=1)

    batch_size = grid_sizes.size(0)
    outputs = []
    
    for i in range(batch_size):
        f, h, w = grid_sizes[i].tolist()
        seq_len = f * h * w

        x_i = torch.view_as_complex(x[i, :seq_len].reshape(seq_len, n, -1, 2))

        sf = (f - 2) // 2

        freq0_start, freq0_end = 1, 1 + sf
        freq1_start, freq1_end = 1, 1 + h
        freq2_start, freq2_end = 1, 1 + w
        
        repeat_freqs = torch.cat([
            freqs_0[freq0_start:freq0_end].view(sf, 1, 1, -1).expand(sf, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(sf, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(sf, h, w, -1)
        ], dim=-1)

        mask_freqs = torch.cat([
            freqs_0[1:2].view(1, 1, 1, -1).expand(1, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(1, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(1, h, w, -1)
        ], dim=-1)

        img_freqs = torch.cat([
            freqs_0[0:1].view(1, 1, 1, -1).expand(1, h, w, -1),
            freqs_1[freq1_start:freq1_end].view(1, h, 1, -1).expand(1, h, w, -1),
            freqs_2[freq2_start:freq2_end].view(1, 1, w, -1).expand(1, h, w, -1)
        ], dim=-1)
    
        if f == 2 * sf + 2:
            freqs_i = torch.cat([repeat_freqs, repeat_freqs, mask_freqs, img_freqs], dim=0)
        else:
            bias_freqs = torch.cat([
                freqs_0[0:1].view(1, 1, 1, -1).expand(1, h, w, -1),
                freqs_1[(h+1):(2*h+1)].view(1, h, 1, -1).expand(1, h, w, -1),
                freqs_2[(w+1):(2*w+1)].view(1, 1, w, -1).expand(1, h, w, -1)
            ], dim=-1)
            freqs_i = torch.cat([repeat_freqs, repeat_freqs, mask_freqs, img_freqs, bias_freqs], dim=0)
        
        freqs_i = freqs_i.reshape(f * h * w, 1, -1).to(x.device)
        
        # Apply rotary embedding
        x_i = torch.view_as_real(x_i * freqs_i).flatten(2)
        x_i = torch.cat([x_i, x[i, seq_len:]], dim=0)

        outputs.append(x_i)
    
    return torch.stack(outputs).to(x.dtype)

