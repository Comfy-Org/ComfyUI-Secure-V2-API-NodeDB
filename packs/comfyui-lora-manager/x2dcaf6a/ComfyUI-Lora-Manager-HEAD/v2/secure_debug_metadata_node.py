"""Original Debug Metadata UI behavior using actual owning execution metadata."""
import logging

from comfy_api.latest import io, sdk

from .native_metadata import metadata_processor
from .secure_remaining_schemas import debug_metadata_schema
from .snapshot_metadata import from_snapshot

logger = logging.getLogger(__name__)
# The owned SDK is the real collector authority. Its mandatory read replaces
# legacy environment-selected startup hooks; never return standalone {}.
metadata_processor.standalone_mode = False


class DebugMetadataLM(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('graph.metadata',)

    @classmethod
    def define_schema(cls):
        return debug_metadata_schema()

    @classmethod
    async def execute(cls, images, **kwargs):
        del images, kwargs
        try:
            snapshot = await sdk.current_context().graph.execution_metadata(include_observations=True)
            metadata = from_snapshot(snapshot)
            value = metadata_processor.MetadataProcessor.to_dict(metadata, snapshot['node_id'])
            return io.NodeOutput(ui={'metadata': [value]})
        except Exception as error:
            logger.error(f'Error processing metadata: {error}')
            return io.NodeOutput(ui={'metadata': [{'error': str(error)}]})
