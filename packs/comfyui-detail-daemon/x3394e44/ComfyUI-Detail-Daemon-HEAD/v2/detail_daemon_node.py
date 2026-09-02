# Based on the concept from https://github.com/muerrilla/sd-webui-detail-daemon

from __future__ import annotations

from io import BytesIO

import numpy as np
import torch
from PIL import Image
from comfy_api.latest import io, sdk

# Upstream imported `comfy.samplers.KSAMPLER`, `folder_paths` and `random` at
# module scope. The schedule math below is this pack's own value and is pure
# numpy, so it crosses unchanged. See SECURE_CONVERSION.md for what happened to
# each node that used the rest.
#
# Note `from io import BytesIO`: upstream did `import io` for the stdlib, and
# `io` is now the V2 schema module. The import statement resolves the stdlib
# module through sys.modules and is unaffected by the local binding.


def _pyplot():
    """Import pyplot explicitly, with a backend that needs no display.

    Upstream set the Agg backend only on macOS, because on a desktop host some
    other import had already chosen a usable backend. A guest is a minimal
    process with no display and no such accident, so the choice is made here
    unconditionally -- that supplies what upstream assumed rather than faking a
    host. Deferred out of module scope so that importing this module to run
    `MultiplySigmas` does not pay for matplotlib.
    """
    import matplotlib

    matplotlib.use("Agg")  # Set non-GUI backend to avoid crashes
    import matplotlib.pyplot as plt

    return plt


# Schedule creation function from https://github.com/muerrilla/sd-webui-detail-daemon
def make_detail_daemon_schedule(
    steps,
    start,
    end,
    bias,
    amount,
    exponent,
    start_offset,
    end_offset,
    fade,
    smooth,
):
    start = min(start, end)
    mid = start + bias * (end - start)
    multipliers = np.zeros(steps)

    start_idx, mid_idx, end_idx = [
        int(round(x * (steps - 1))) for x in [start, mid, end]
    ]

    start_values = np.linspace(0, 1, mid_idx - start_idx + 1)
    if smooth:
        start_values = 0.5 * (1 - np.cos(start_values * np.pi))
    start_values = start_values**exponent
    if start_values.any():
        start_values *= amount - start_offset
        start_values += start_offset

    end_values = np.linspace(1, 0, end_idx - mid_idx + 1)
    if smooth:
        end_values = 0.5 * (1 - np.cos(end_values * np.pi))
    end_values = end_values**exponent
    if end_values.any():
        end_values *= amount - end_offset
        end_values += end_offset

    multipliers[start_idx : mid_idx + 1] = start_values
    multipliers[mid_idx : end_idx + 1] = end_values
    multipliers[:start_idx] = start_offset
    multipliers[end_idx + 1 :] = end_offset
    multipliers *= 1 - fade

    return multipliers


def get_dd_schedule(sigma, sigmas, dd_schedule):
    """Interpolate the pack's detail curve at one model-evaluation sigma."""
    sched_len = len(dd_schedule)
    if (
        sched_len < 2
        or len(sigmas) < 2
        or sigma <= 0
        or not (sigmas[-1] <= sigma <= sigmas[0])
    ):
        return 0.0
    deltas = (sigmas[:-1] - sigma).abs()
    idx = int(deltas.argmin())
    if (
        (idx == 0 and sigma >= sigmas[0])
        or (idx == sched_len - 1 and sigma <= sigmas[-2])
        or deltas[idx] == 0
    ):
        return dd_schedule[idx].item()
    idxlow, idxhigh = (idx, idx - 1) if sigma > sigmas[idx] else (idx + 1, idx)
    nlow, nhigh = sigmas[idxlow], sigmas[idxhigh]
    if nhigh - nlow == 0:
        return dd_schedule[idxlow].item()
    ratio = ((sigma - nlow) / (nhigh - nlow)).clamp(0, 1)
    return torch.lerp(dd_schedule[idxlow], dd_schedule[idxhigh], ratio).item()


def _sampler_inputs(include_sigmas=False):
    inputs = [io.Sampler.Input("sampler")]
    if include_sigmas:
        inputs.append(io.Sigmas.Input("sigmas", extra_dict={"forceInput": True}))
    inputs.extend([
        io.Float.Input(
            "detail_amount", default=0.1, min=-5.0, max=5.0, step=0.01),
        io.Float.Input("start", default=0.2, min=0.0, max=1.0, step=0.01),
        io.Float.Input("end", default=0.8, min=0.0, max=1.0, step=0.01),
        io.Float.Input("bias", default=0.5, min=0.0, max=1.0, step=0.01),
        io.Float.Input(
            "exponent", default=1.0, min=0.0, max=10.0, step=0.05),
        io.Float.Input(
            "start_offset", default=0.0, min=-1.0, max=1.0, step=0.01),
        io.Float.Input(
            "end_offset", default=0.0, min=-1.0, max=1.0, step=0.01),
        io.Float.Input("fade", default=0.0, min=0.0, max=1.0, step=0.05),
        io.Boolean.Input("smooth", default=True),
        io.Float.Input(
            "cfg_scale_override",
            default=0.0,
            min=0.0,
            max=100.0,
            step=0.5,
            round=0.01,
            tooltip=(
                "0 uses the sampler's CFG scale; another value overrides it."
            ),
        ),
    ])
    return inputs


class DetailDaemonSamplerNode(io.ComfyNode):
    """Wrap a sampler; only the pack's sigma curve runs in the sandbox."""

    SDK_REFS = True
    SDK_PERMISSIONS = ("closures",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DetailDaemonSamplerNode",
            display_name="Detail Daemon Sampler",
            category="sampling/custom_sampling/samplers",
            description=(
                "Adjusts the sigma passed to each model evaluation while the "
                "selected sampler otherwise runs unchanged."
            ),
            inputs=_sampler_inputs(),
            outputs=[io.Sampler.Output()],
        )

    @classmethod
    async def execute(
        cls, sampler, detail_amount, start, end, bias, exponent,
        start_offset, end_offset, fade, smooth, cfg_scale_override,
    ) -> io.NodeOutput:
        # Every value closed over here is pack-plane scalar state. The host
        # supplies current sigma + sampler schedule + auto CFG explicitly.
        settings = (
            float(start), float(end), float(bias), float(detail_amount),
            float(exponent), float(start_offset), float(end_offset),
            float(fade), bool(smooth), float(cfg_scale_override),
        )

        def adjust_sigma(sigma, sigmas, cfg, start_sigma, end_sigma):
            del start_sigma, end_sigma
            (
                start_value, end_value, bias_value, amount_value,
                exponent_value, start_offset_value, end_offset_value,
                fade_value, smooth_value, override,
            ) = settings
            sigmas_cpu = sigmas.detach().clone().cpu()
            sigma_float = float(sigma.max().detach().cpu())
            sigma_max = float(sigmas_cpu[0])
            sigma_min = float(sigmas_cpu[-1]) + 1e-05
            if not sigma_min <= sigma_float <= sigma_max:
                return sigma
            schedule = torch.tensor(
                make_detail_daemon_schedule(
                    len(sigmas_cpu) - 1,
                    start_value,
                    end_value,
                    bias_value,
                    amount_value,
                    exponent_value,
                    start_offset_value,
                    end_offset_value,
                    fade_value,
                    smooth_value,
                ),
                dtype=torch.float32,
                device="cpu",
            )
            adjustment = get_dd_schedule(
                sigma_float, sigmas_cpu, schedule) * 0.1
            cfg_value = override if override > 0 else float(cfg)
            return sigma * max(1e-06, 1.0 - adjustment * cfg_value)

        closure = await sdk.ctx().closures.retain(
            "model_sigma", adjust_sigma)
        return io.NodeOutput(await closure.wrap_sampler(sampler))


class DetailDaemonSamplerGUINode(DetailDaemonSamplerNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DetailDaemonSamplerGUINode",
            display_name="Detail Daemon Sampler GUI",
            category="sampling/custom_sampling/samplers",
            description=(
                "Detail Daemon sampler with an interactive schedule graph."
            ),
            inputs=_sampler_inputs(include_sigmas=True),
            outputs=[
                io.Sampler.Output(display_name="sampler"),
                io.Sigmas.Output(display_name="sigmas"),
            ],
        )

    @classmethod
    async def execute(cls, sampler, sigmas, **kwargs) -> io.NodeOutput:
        wrapped = await super().execute(sampler=sampler, **kwargs)
        return io.NodeOutput(wrapped.result[0], sigmas)


class LyingSigmaSamplerNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("closures",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LyingSigmaSampler",
            display_name="Lying Sigma Sampler",
            category="sampling/custom_sampling",
            inputs=[
                io.Sampler.Input("sampler"),
                io.Float.Input(
                    "dishonesty_factor",
                    default=-0.05,
                    min=-0.999,
                    step=0.01,
                    tooltip=(
                        "Multiplier for sigmas passed to the model. -0.05 "
                        "reduces sigma by 5%."
                    ),
                ),
                io.Float.Input(
                    "start_percent", optional=True, default=0.1,
                    min=0.0, max=1.0, step=0.01),
                io.Float.Input(
                    "end_percent", optional=True, default=0.9,
                    min=0.0, max=1.0, step=0.01),
            ],
            outputs=[io.Sampler.Output()],
        )

    @classmethod
    async def execute(
        cls, sampler, dishonesty_factor,
        start_percent=0.0, end_percent=1.0,
    ) -> io.NodeOutput:
        factor = float(dishonesty_factor)

        def adjust_sigma(sigma, sigmas, cfg, start_sigma, end_sigma):
            del sigmas, cfg
            current = float(sigma.max().detach().cpu())
            if end_sigma <= current <= start_sigma:
                return sigma * (1.0 + factor)
            return sigma

        closure = await sdk.ctx().closures.retain(
            "model_sigma", adjust_sigma)
        return io.NodeOutput(await closure.wrap_sampler(
            sampler,
            start_percent=float(start_percent),
            end_percent=float(end_percent),
        ))


class DetailDaemonGraphSigmasNode(io.ComfyNode):
    # The plot itself is unchanged: `plot_schedule` below is upstream's, byte
    # for byte. Only the two host reaches around it moved.
    #
    # Upstream hand-rolled the save -- `folder_paths.get_temp_directory()`, a
    # random prefix, `get_save_image_path`, `image.save(...)` -- and returned a
    # `type: "temp"` UI image. `ctx.ui.preview_images` IS that operation: it
    # writes into the same temp directory and returns the same
    # `{"images": [{filename, subfolder, type: "temp"}]}` payload, so the
    # preview stays transient exactly as before. (`ctx.output.save_images`
    # would have been the wrong choice -- it writes to the OUTPUT folder, and a
    # preview node built on it would litter the user's outputs every run.)
    #
    # Note what the node never needed: the sigma VALUES. Upstream cloned the
    # tensor, scaled it in a loop, and then discarded the result -- only
    # `len(sigmas)` ever reached the output. `SigmasRef.steps()` is exactly
    # `len(sigmas) - 1`, so no schedule tensor crosses the boundary at all.
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw", "ui")

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="DetailDaemonGraphSigmasNode",
            display_name="Detail Daemon Graph Sigmas",
            category="sampling/custom_sampling/sigmas",
            is_output_node=True,
            inputs=[
                io.Sigmas.Input("sigmas", extra_dict={"forceInput": True}),
                io.Float.Input(
                    "detail_amount", default=0.1, min=-5.0, max=5.0, step=0.01
                ),
                io.Float.Input("start", default=0.2, min=0.0, max=1.0, step=0.01),
                io.Float.Input("end", default=0.8, min=0.0, max=1.0, step=0.01),
                io.Float.Input("bias", default=0.5, min=0.0, max=1.0, step=0.01),
                io.Float.Input("exponent", default=1.0, min=0.0, max=10.0, step=0.05),
                io.Float.Input(
                    "start_offset", default=0.0, min=-1.0, max=1.0, step=0.01
                ),
                io.Float.Input("end_offset", default=0.0, min=-1.0, max=1.0, step=0.01),
                io.Float.Input("fade", default=0.0, min=0.0, max=1.0, step=0.05),
                io.Boolean.Input("smooth", default=True),
                io.Float.Input(
                    "cfg_scale",
                    default=1.0,
                    min=0.0,
                    max=100.0,
                    step=0.5,
                    round=0.01,
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(
        cls,
        sigmas,
        detail_amount,
        start,
        end,
        bias,
        exponent,
        start_offset,
        end_offset,
        fade,
        smooth,
        cfg_scale,
    ) -> io.NodeOutput:
        # Derive the number of steps from the length of sigmas minus 1 (ignore
        # the final sigma). `steps()` IS `len(sigmas) - 1`.
        steps = await sigmas.steps()  # 21 sigmas, 20 steps
        actual_steps = steps

        # Create the schedule using the number of steps
        schedule = make_detail_daemon_schedule(
            actual_steps,
            start,
            end,
            bias,
            detail_amount,
            exponent,
            start_offset,
            end_offset,
            fade,
            smooth,
        )

        # Debugging: print schedule and sigmas lengths to verify alignment
        print(
            f"Number of sigmas: {steps + 1}, Number of schedule steps: {len(schedule)}",
        )

        # Iterate over the sigmas, except for the last one (which we assume is 0
        # and leave untouched). Upstream scaled a cloned tensor here and then
        # dropped it on the floor -- the adjusted sigmas never reached the
        # return value -- so only the trace it printed survived into behaviour.
        for idx in range(steps):
            multiplier = schedule[idx] * 0.1

            # Debugging: print each index and sigma to track what's being adjusted
            print(f"Adjusting sigma at index {idx} with multiplier {multiplier}")

        # Create the plot for visualization
        image = cls.plot_schedule(schedule)

        # Save temp image
        pixels = (
            torch.from_numpy(np.asarray(image.convert("RGB")).copy())
            .float()
            .div(255.0)
            .unsqueeze(0)
        )
        return io.NodeOutput(
            ui=await sdk.ctx().ui.preview_images(
                await sdk.ImageRef._from_raw(pixels),
            ),
        )

    @staticmethod
    def plot_schedule(schedule) -> Image:
        plt = _pyplot()
        plt.figure(figsize=(6, 4))  # Adjusted width
        plt.plot(schedule, label="Sigma Adjustment Curve")
        plt.xlabel("Steps")
        plt.ylabel("Multiplier (*10)")
        plt.title("Detail Adjustment Schedule")
        plt.legend()
        plt.grid(True)
        plt.xticks(range(len(schedule)))
        plt.ylim(-1, 1)

        # Use tight_layout or subplots_adjust
        plt.tight_layout()
        # Or manually adjust if needed:
        # plt.subplots_adjust(left=0.2)

        buf = BytesIO()
        plt.savefig(buf, format="PNG")
        plt.close()
        buf.seek(0)
        image = Image.open(buf)
        return image


# MultiplySigmas Node
class MultiplySigmas(io.ComfyNode):
    # SIGMAS crosses as an opaque `SigmasRef`: it has no `raw()`, so the
    # schedule is read one bounded scalar at a time through `value_at`, which is
    # what that op exists for. Schedules are at most 10001 entries and in
    # practice a few dozen.
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="MultiplySigmas",
            display_name="Multiply Sigmas (stateless)",
            category="sampling/custom_sampling/sigmas",
            inputs=[
                io.Sigmas.Input("sigmas", extra_dict={"forceInput": True}),
                io.Float.Input("factor", default=1, min=0, max=100, step=0.001),
                io.Float.Input("start", default=0, min=0, max=1, step=0.001),
                io.Float.Input("end", default=1, min=0, max=1, step=0.001),
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(cls, sigmas, factor, start, end) -> io.NodeOutput:
        # Read the schedule out rather than cloning it; the node is stateless
        # either way and the input tensor is never touched.
        total_sigmas = await sigmas.steps() + 1
        values = [await sigmas.value_at(index) for index in range(total_sigmas)]

        start_idx = int(start * total_sigmas)
        end_idx = int(end * total_sigmas)

        for i in range(start_idx, end_idx):
            values[i] *= factor

        out = torch.tensor(values, dtype=torch.float32)
        return io.NodeOutput(await sdk.TensorRef._from_raw(out))


NODE_CLASS_MAPPINGS = {
    "DetailDaemonSamplerNode": DetailDaemonSamplerNode,
    "DetailDaemonSamplerGUINode": DetailDaemonSamplerGUINode,
    "DetailDaemonGraphSigmasNode": DetailDaemonGraphSigmasNode,
    "MultiplySigmas": MultiplySigmas,
    "LyingSigmaSampler": LyingSigmaSamplerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DetailDaemonSamplerNode": "Detail Daemon Sampler",
    "DetailDaemonSamplerGUINode": "Detail Daemon Sampler GUI",
    "DetailDaemonGraphSigmasNode": "Detail Daemon Graph Sigmas",
    "MultiplySigmas": "Multiply Sigmas (stateless)",
    "LyingSigmaSampler": "Lying Sigma Sampler",
}
