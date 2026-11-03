"""V2 subset of upstream sigmas.py (057a913e): "Sigmas Resample" (sigmas_interpolate) and the small
network its "model" mode trains, copied verbatim in upstream order; VENDOR.json records each one's source
lines and sha256. The imports below are upstream's own statements for the names these definitions use
(vendor_res4lyf.py proves that every global name resolves as upstream). scipy is imported at module level
upstream; only the unreachable interpolate_sigma_schedule_constrained method uses it."""
import torch
import numpy as np
from scipy.interpolate import CubicSpline
import torch.nn.functional as F
import torch.optim as optim

from torch import Tensor, nn


class SimpleInterpolator(nn.Module):
    def __init__(self):
        super(SimpleInterpolator, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(1, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        return self.net(x)


def train_interpolator(model, sigma_schedule, steps, epochs=5000, lr=0.01):
    with torch.inference_mode(False):
        model = SimpleInterpolator()
        sigma_schedule = sigma_schedule.clone()

        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        
        x_train = torch.linspace(0, 1, steps=steps).unsqueeze(1)
        y_train = sigma_schedule.unsqueeze(1)

        # disable inference mode for training
        model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()

            # fwd pass
            outputs = model(x_train)
            loss = criterion(outputs, y_train)
            loss.backward()
            optimizer.step()

    return model


def interpolate_sigma_schedule_model(sigma_schedule, target_steps):
    model = SimpleInterpolator()
    sigma_schedule = sigma_schedule.float().detach()

    # train on original sigma schedule
    trained_model = train_interpolator(model, sigma_schedule, len(sigma_schedule))

    # generate target steps for interpolation
    x_interpolated = torch.linspace(0, 1, target_steps).unsqueeze(1)

    # inference w/o gradients
    trained_model.eval()
    with torch.no_grad():
        interpolated_sigma = trained_model(x_interpolated).squeeze()

    return interpolated_sigma


class sigmas_interpolate:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "sigmas_in": ("SIGMAS", {"forceInput": True}),
                "output_length": ("INT", {"default": 0, "min": 0,"max": 10000,"step": 1}),
                "mode": (["linear", "nearest", "polynomial", "exponential", "power", "model"],),
                "order": ("INT", {"default": 8, "min": 1,"max": 64,"step": 1}),
                "rescale_after": ("BOOLEAN", {"default": True, "tooltip": "Rescale the output to the original min/max range after interpolation."}),
            }
        }

    FUNCTION = "main"
    RETURN_TYPES = ("SIGMAS",)
    RETURN_NAMES = ("sigmas",)
    CATEGORY = "RES4LYF/sigmas"
    DESCRIPTION = "Interpolate the sigmas schedule to a new length clamping the start and end values."

    def interpolate_sigma_schedule_poly(self, sigma_schedule, target_steps):
        order = self.order
        sigma_schedule_np = sigma_schedule.cpu().numpy()

        # orig steps (assuming even spacing)
        original_steps = np.linspace(0, 1, len(sigma_schedule_np))

        # fit polynomial of the given order
        coefficients = np.polyfit(original_steps, sigma_schedule_np, deg=order)

        # generate new steps where we want to interpolate the data
        target_steps_np = np.linspace(0, 1, target_steps)

        # eval polynomial at new steps
        interpolated_sigma_np = np.polyval(coefficients, target_steps_np)

        interpolated_sigma = torch.tensor(interpolated_sigma_np, device=sigma_schedule.device, dtype=sigma_schedule.dtype)
        return interpolated_sigma

    def interpolate_sigma_schedule_constrained(self, sigma_schedule, target_steps):
        sigma_schedule_np = sigma_schedule.cpu().numpy()

        # orig steps
        original_steps = np.linspace(0, 1, len(sigma_schedule_np))

        # target steps for interpolation
        target_steps_np = np.linspace(0, 1, target_steps)

        # fit cubic spline with fixed start and end values
        cs = CubicSpline(original_steps, sigma_schedule_np, bc_type=((1, 0.0), (1, 0.0)))

        # eval spline at the target steps
        interpolated_sigma_np = cs(target_steps_np)

        interpolated_sigma = torch.tensor(interpolated_sigma_np, device=sigma_schedule.device, dtype=sigma_schedule.dtype)

        return interpolated_sigma
    
    def interpolate_sigma_schedule_exp(self, sigma_schedule, target_steps):
        # transform to log space
        log_sigma_schedule = torch.log(sigma_schedule)

        # define the original and target step ranges
        original_steps = torch.linspace(0, 1, steps=len(sigma_schedule))
        target_steps = torch.linspace(0, 1, steps=target_steps)

        # interpolate in log space
        interpolated_log_sigma = F.interpolate(
            log_sigma_schedule.unsqueeze(0).unsqueeze(0),  # Add fake batch and channel dimensions
            size=target_steps.shape[0],
            mode='linear',
            align_corners=True
        ).squeeze()

        # transform back to exponential space
        interpolated_sigma_schedule = torch.exp(interpolated_log_sigma)

        return interpolated_sigma_schedule
    
    def interpolate_sigma_schedule_power(self, sigma_schedule, target_steps):
        sigma_schedule_np = sigma_schedule.cpu().numpy()
        original_steps = np.linspace(1, len(sigma_schedule_np), len(sigma_schedule_np))

        # power regression using a log-log transformation
        log_x = np.log(original_steps)
        log_y = np.log(sigma_schedule_np)

        # linear regression on log-log data
        coefficients = np.polyfit(log_x, log_y, deg=1)  # degree 1 for linear fit in log-log space
        a = np.exp(coefficients[1])  # a = "b" = intercept (exp because of the log transform)
        b = coefficients[0]  # b = "m" = slope

        target_steps_np = np.linspace(1, len(sigma_schedule_np), target_steps)

        # power law prediction: y = a * x^b
        interpolated_sigma_np = a * (target_steps_np ** b)

        interpolated_sigma = torch.tensor(interpolated_sigma_np, device=sigma_schedule.device, dtype=sigma_schedule.dtype)

        return interpolated_sigma
            
    def interpolate_sigma_schedule_linear(self, sigma_schedule, target_steps):
        return F.interpolate(sigma_schedule.unsqueeze(0).unsqueeze(0), target_steps, mode='linear').squeeze(0).squeeze(0)

    def interpolate_sigma_schedule_nearest(self, sigma_schedule, target_steps):
        return F.interpolate(sigma_schedule.unsqueeze(0).unsqueeze(0), target_steps, mode='nearest').squeeze(0).squeeze(0)    
    
    def interpolate_nearest_neighbor(self, sigma_schedule, target_steps):
        original_steps = torch.linspace(0, 1, steps=len(sigma_schedule))
        target_steps = torch.linspace(0, 1, steps=target_steps)

        # interpolate original -> target steps using nearest neighbor
        indices = torch.searchsorted(original_steps, target_steps)
        indices = torch.clamp(indices, 0, len(sigma_schedule) - 1)  # clamp indices to valid range

        # set nearest neighbor via indices
        interpolated_sigma = sigma_schedule[indices]

        return interpolated_sigma


    def main(self, sigmas_in, output_length, mode, order, rescale_after=True):

        self.order = order

        sigmas_in = sigmas_in.clone().to(sigmas_in.dtype)
        start = sigmas_in[0]
        end = sigmas_in[-1]

        if   mode == "linear": 
            interpolate = self.interpolate_sigma_schedule_linear
        if   mode == "nearest": 
            interpolate = self.interpolate_nearest_neighbor
        elif mode == "polynomial":
            interpolate = self.interpolate_sigma_schedule_poly
        elif mode == "exponential":
            interpolate = self.interpolate_sigma_schedule_exp
        elif mode == "power":
            interpolate = self.interpolate_sigma_schedule_power
        elif mode == "model":
            with torch.inference_mode(False):
                interpolate = interpolate_sigma_schedule_model

        sigmas_interp = interpolate(sigmas_in, output_length)
        if rescale_after:
            sigmas_interp = ((sigmas_interp - sigmas_interp.min()) * (start - end)) / (sigmas_interp.max() - sigmas_interp.min()) + end
        return (sigmas_interp,)
