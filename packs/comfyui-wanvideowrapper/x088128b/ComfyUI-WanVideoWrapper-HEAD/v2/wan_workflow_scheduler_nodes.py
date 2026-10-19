"""Staged original scheduler sockets backed by reconstructable solver recipes.

The original sigma figure (formerly a PromptServer progress-text push) is rendered with the same matplotlib
calls on an explicit Agg canvas and returned as the node's own UI image through the SDK output API.
"""
import logging

from comfy_api.latest import io, sdk
from .wan_workflow_scheduler_runtime import produce_scheduler, scheduler_list


def _inputs():
    return [io.Combo.Input('scheduler', options=scheduler_list, default='unipc'),
            io.Int.Input('steps', default=30, min=1, tooltip='Number of steps for the scheduler'),
            io.Float.Input('shift', default=5.0, min=0.0, max=1000.0, step=0.01),
            io.Int.Input('start_step', default=0, min=0, tooltip='Starting step for the scheduler'),
            io.Int.Input('end_step', default=-1, min=-1, tooltip='Ending step for the scheduler'),
            io.Custom('SIGMAS').Input('sigmas', optional=True),
            io.Boolean.Input('enhance_hf', optional=True, default=False, tooltip='Enhanced high-frequency denoising schedule')]


def _sigmas_figure_png(sample_scheduler, start_idx, end_idx):
    """The original WanVideoScheduler sigma figure (vendored nodes_sampler.py WanVideoScheduler.process plot block),
    unique_id-independent, drawn with the same calls on an explicit Agg canvas (matplotlib.figure.Figure + FigureCanvasAgg
    instead of pyplot global state). Returns the PNG bytes, or None when plotting fails (the original logs and continues)."""
    try:
        from io import BytesIO
        import numpy as np
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        # Plot sigmas and save to a buffer
        sigmas_np = sample_scheduler.full_sigmas.cpu().numpy()
        if not np.isclose(sigmas_np[-1], 0.0, atol=1e-6):
            sigmas_np = np.append(sigmas_np, 0.0)
        buf = BytesIO()
        fig = Figure(facecolor='#353535')
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor('#353535')  # Set axes background color
        x_values = range(0, len(sigmas_np))
        ax.plot(x_values, sigmas_np)
        # Annotate each sigma value
        ax.scatter(x_values, sigmas_np, color='white', s=20, zorder=3)  # Small dots at each sigma
        for x, y in zip(x_values, sigmas_np):
            # Show all annotations if few steps, or just show split step annotations
            show_annotation = len(sigmas_np) <= 10
            is_split_step = (start_idx > 0 and x == start_idx) or (end_idx != -1 and x == end_idx + 1)

            if show_annotation or is_split_step:
                color = 'orange'
                if is_split_step:
                    color = 'yellow'
                ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points", xytext=(10, 1), ha='center', color=color, fontsize=12)
        ax.set_xticks(x_values)
        ax.set_title("Sigmas", color='white')           # Title font color
        ax.set_xlabel("Step", color='white')            # X label font color
        ax.set_ylabel("Sigma Value", color='white')     # Y label font color
        ax.tick_params(axis='x', colors='white', labelsize=10)        # X tick color
        ax.tick_params(axis='y', colors='white', labelsize=10)        # Y tick color
        # Add split point if end_step is defined
        end_idx += 1
        if end_idx != -1 and 0 <= end_idx < len(sigmas_np) - 1:
            ax.axvline(end_idx, color='red', linestyle='--', linewidth=2, label='end_step split')
        # Add split point if start_step is defined
        if start_idx > 0 and 0 <= start_idx < len(sigmas_np):
            ax.axvline(start_idx, color='green', linestyle='--', linewidth=2, label='start_step split')
        if (end_idx != -1 and 0 <= end_idx < len(sigmas_np)) or (start_idx > 0 and 0 <= start_idx < len(sigmas_np)):
            handles, labels = ax.get_legend_handles_labels()
            if labels:
                ax.legend()
        # Draw shaded range
        range_start_idx = start_idx if start_idx > 0 else 0
        range_end_idx = end_idx if end_idx > 0 and end_idx < len(sigmas_np) else len(sigmas_np) - 1
        if range_start_idx < range_end_idx:
            ax.axvspan(range_start_idx, range_end_idx, color='lightblue', alpha=0.1, label='Sampled Range')


        fig.tight_layout()
        fig.savefig(buf, format='png')
        return buf.getvalue()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to render sigmas plot: {e}")
        return None


async def _sigmas_ui(actual):
    """The node's own UI image: PNG -> RGBA IMAGE tensor -> ImageRef -> ctx.output.save_images."""
    try:
        png = _sigmas_figure_png(actual['sample_scheduler'], actual['start_idx'], actual['end_idx'])
        if png is None:
            return None
        from io import BytesIO
        import numpy as np
        import torch
        from PIL import Image
        rgba = np.array(Image.open(BytesIO(png)).convert('RGBA'))
        image = torch.from_numpy(rgba).to(torch.float32).div(255.0).unsqueeze(0)
        ref = await sdk.ImageRef.from_value(image)
        saved = await sdk.ctx().output.save_images(ref, filename_prefix='WanVideoScheduler_sigmas', save_metadata=False)
        return {'images': saved['images']}
    except Exception as error:
        logging.getLogger(__name__).error(f"Failed to send sigmas plot: {error}")
        return None


class WanVideoScheduler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoScheduler', display_name='WanVideo Scheduler', category='WanVideoWrapper',
            is_experimental=True, inputs=_inputs(),
            outputs=[io.Custom('SIGMAS').Output(display_name='sigmas'),
                     io.Int.Output(display_name='steps'), io.Float.Output(display_name='shift'),
                     io.Combo.Output(display_name='scheduler', options=scheduler_list),
                     io.Int.Output(display_name='start_step'), io.Int.Output(display_name='end_step')])

    @classmethod
    async def execute(cls, scheduler, steps, start_step, end_step, shift, sigmas=None, enhance_hf=False):
        legacy, actual = produce_scheduler(scheduler, steps, start_step, end_step, shift, sigmas, enhance_hf)
        return io.NodeOutput(*legacy, ui=await _sigmas_ui(actual))


class WanVideoSchedulerv2(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw', 'output')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSchedulerv2', display_name='WanVideo Scheduler v2', category='WanVideoWrapper',
            is_experimental=True, inputs=_inputs(),
            outputs=[io.Custom('WANVIDEOSCHEDULER').Output(display_name='scheduler')])

    @classmethod
    async def execute(cls, scheduler, steps, start_step, end_step, shift, sigmas=None, enhance_hf=False):
        legacy, actual = produce_scheduler(scheduler, steps, start_step, end_step, shift, sigmas, enhance_hf)
        return io.NodeOutput(legacy[3], ui=await _sigmas_ui(actual))


NODE_CLASS_MAPPINGS = {'WanVideoScheduler': WanVideoScheduler,
                       'WanVideoSchedulerv2': WanVideoSchedulerv2}
