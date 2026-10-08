from typing_extensions import override

from comfy_api.latest import io
import torch


class ForwardAnyNode(io.ComfyNode):
	"""
	ForwardingNode
	A simple pass-through node that returns its single input unchanged.

	Inputs:
	- value: any type accepted by ComfyUI inputs (Image, Latent, Float, Int, Sigmas, etc.)

	Outputs:
	- value: same as input
	"""
	@classmethod
	def define_schema(cls) -> io.Schema:
		return io.Schema(
			node_id="ForwardAnyImmacTools",
			display_name="Forward Any",
			category="Example",
			inputs=[
				io.AnyType.Input("value",display_name="->"),
			],
			outputs=[
				io.AnyType.Output(display_name="->"),
			],
		)

	@classmethod
	def check_lazy_status(cls, value):
		return []

	@classmethod
	def execute(cls, value) -> io.NodeOutput:
		# Pass-through: simply return the input as output
		return io.NodeOutput(value)


class ForwardConditioningNode(io.ComfyNode):
	"""
	ConditioningForwardingNode
	A pass-through node specifically for Conditioning types.

	Inputs:
	- conditioning: Conditioning input

	Outputs:
	- conditioning: same Conditioning output
	"""
	@classmethod
	def define_schema(cls) -> io.Schema:
		return io.Schema(
			node_id="ForwardConditioningImmacTools",
			display_name="Forward Conditioning",
			category="Example",
			inputs=[
				io.Conditioning.Input("conditioning", display_name="->"),
			],
			outputs=[
				io.Conditioning.Output(display_name="->"),
			],
		)

	@classmethod
	def check_lazy_status(cls, conditioning):
		return []

	@classmethod
	def execute(cls, conditioning) -> io.NodeOutput:
		# Pass-through: simply return the conditioning as output
		return io.NodeOutput(conditioning)


class ForwardModelNode(io.ComfyNode):
	"""
	ModelForwardingNode
	A pass-through node specifically for Model types.

	Inputs:
	- model: Model input

	Outputs:
	- model: same Model output
	"""
	@classmethod
	def define_schema(cls) -> io.Schema:
		return io.Schema(
			node_id="ForwardModelImmacTools",
			display_name="Forward Model",
			category="Example",
			inputs=[
				io.Model.Input("model", display_name="->"),
			],
			outputs=[
				io.Model.Output(display_name="->"),
			],
		)

	@classmethod
	def check_lazy_status(cls, model):
		return []

	@classmethod
	def execute(cls, model) -> io.NodeOutput:
		# Pass-through: simply return the model as output
		return io.NodeOutput(model)





