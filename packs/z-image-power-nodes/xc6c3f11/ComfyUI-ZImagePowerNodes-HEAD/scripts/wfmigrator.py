"""
File    : wfmigrator.py
Purpose : Script to adapt ComfyUI workflows from GGUF to Safetensors
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Apr 2, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import os
import sys
import copy
import json
import argparse
from urllib.parse import urlparse, unquote
from pathlib      import Path
from typing       import Any, TypeAlias
Workflow: TypeAlias = dict[str, Any]
Command : TypeAlias = dict[str, Any]
Node    : TypeAlias = dict[str, Any]

# migration command table,
# converting GGUF loader nodes to safetensor loaders (with FP8 checkpoints)
MIGRATION_TO_FP8 = [{
    "target"         : "UnetLoaderGGUF",
    "action"         : lambda node, cmd: convert_to_unet_loader(node, cmd),
    "checkpoint_url" : "https://huggingface.co/Kijai/Z-Image_comfy_fp8_scaled/resolve/main/z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors",
},{
    "target"         : "CLIPLoaderGGUF",
    "action"         : lambda node, cmd: convert_to_clip_loader(node, cmd),
    "checkpoint_url" : "https://huggingface.co/hhsebsb/qwen3-4b-fp8-scaled/resolve/main/qwen3_4b_fp8_scaled.safetensors",
},{
    "target"              : "Note:REQUIREMENTS",
    "action"              : lambda node, cmd: write_requirements_note(node, cmd),
    "custom_nodes1"       : "Z-Image Power Nodes: https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes",
    # ATTENTION: unlike loaders, these urls are not "../resolve/main/..." but "../blob/main/..."
    "unet_checkpoint_url" : "https://huggingface.co/Kijai/Z-Image_comfy_fp8_scaled/blob/main/z-image-turbo_fp8_scaled_e4m3fn_KJ.safetensors",
    "clip_checkpoint_url" : "https://huggingface.co/hhsebsb/qwen3-4b-fp8-scaled/blob/main/qwen3_4b_fp8_scaled.safetensors",
    "vae_checkpoint_url"  : "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/vae/ae.safetensors",
}]

# migration command table,
# converting GGUF loader nodes to safetensor loaders (with BF16 checkpoints)
MIGRATION_TO_BF16 = [{
    "target"         : "UnetLoaderGGUF",
    "action"         : lambda node, cmd: convert_to_unet_loader(node, cmd),
    "checkpoint_url" : "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
},{
    "target"         : "CLIPLoaderGGUF",
    "action"         : lambda node, cmd: convert_to_clip_loader(node, cmd),
    "checkpoint"     : "qwen_3_4b.safetensors",
    "download_from"  : "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
},{
    "target"             : "Note:REQUIREMENTS",
    "action"             : lambda node, cmd: write_requirements_note(node, cmd),
    "custom_nodes1"      : "Z-Image Power Nodes: https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes",
    # ATTENTION: unlike loaders, these urls are not "../resolve/main/..." but "../blob/main/..."
    "unet_checkpoint_url": "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
    "clip_checkpoint_url": "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/text_encoders/qwen_3_4b.safetensors",
    "vae_checkpoint_url" : "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/vae/ae.safetensors",
}]


# get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ANSI escape codes for colored terminal output
RED      = '\033[91m'
DKRED    = '\033[31m'
YELLOW   = '\033[93m'
DKYELLOW = '\033[33m'
GREEN    = '\033[92m'
CYAN     = '\033[96m'
DKGRAY   = '\033[90m'
RESET    = '\033[0m'

#============================= ERROR MESSAGES ==============================#

def disable_colors():
    global RED, DKRED, YELLOW, DKYELLOW, GREEN, CYAN, DKGRAY, RESET
    RED, DKRED, YELLOW, DKYELLOW, GREEN, CYAN, DKGRAY, RESET = "", "", "", "", "", "", "", ""


def info(message: str, padding: int = 0, file=sys.stderr) -> None:
    """Displays an informational message to the error stream.
    """
    print(f"{" "*padding}{CYAN}\u24d8 {message}{RESET}", file=file)


def warning(message: str, *info_messages: str, padding: int = 0, file=sys.stderr) -> None:
    """Displays a warning message to the standard error stream.
    """
    print(f"{" "*padding}{CYAN}[{YELLOW}WARNING{CYAN}]{DKYELLOW} {message}{RESET}", file=file)
    for info_message in info_messages:
        info(info_message, padding=padding, file=file)


def error(message: str, *info_messages: str, padding: int = 0, file=sys.stderr) -> None:
    """Displays an error message to the standard error stream.
    """
    print(f"{" "*padding}{DKRED}[{RED}ERROR!{DKRED}]{DKYELLOW} {message}{RESET}", file=file)
    for info_message in info_messages:
        info(info_message, padding=padding, file=file)


def fatal_error(message: str, *info_messages: str, padding: int = 0, file=sys.stderr) -> None:
    """Displays a fatal error message to the standard error stream and exits with status code 1.
    """
    error(message, *info_messages, padding=padding, file=file)
    sys.exit(1)


#================================ HELPERS ==================================#

def solve_checkpoint(checkpoint: str | None, checkpoint_url: str | None) -> str | None:
    # if no checkpoint is provided, try to extract it from the URL
    if not isinstance(checkpoint,str) and isinstance(checkpoint_url,str):
        parsed_url = urlparse(checkpoint_url)
        checkpoint = unquote( parsed_url.path ).split('/')[-1]
    return checkpoint


def collect_workflow_files(input_paths: list[Path|str]) -> list[Path]:
    """
    Collects all workflow JSON files from the provided paths.

    Args:
        input_paths: List of paths to process (strings or Path objects).
    Returns:
        List of Path objects representing all found .json workflow files.
    """
    all_files: list[Path] = []

    for element in input_paths:

        # convert each element to `Path` for uniform handling
        if   isinstance(element, str ):  path = Path(element)
        elif isinstance(element, Path):  path = element
        else: raise TypeError(f"Invalid input type: {type(element)}. Expected Path or str.")

        if not path.exists():
            warning(f'Path does not exist: "{path}"')

        # if it's a json file, add it
        elif path.is_file() and path.suffix.lower() == '.json':
                all_files.append(path)

        # if it's a directory, add all .json files in it
        elif path.is_dir():
            all_files.extend( path.rglob('*.json') )

    return all_files


def load_workflow(file_path: Path) -> dict[str, Any] | None:
    """Loads a ComfyUI workflow"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        error(f"Failed to load JSON from {file_path}: {e}")
        return None
    except IOError as e:
        error(f"IO Error reading {file_path}: {e}")
        return None


def save_workflow(workflow: dict[str, Any], path: Path) -> bool:
    """Saves a ComfyUI workflow as a .json file"""
    try:
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(workflow, file)#, indent=2)
        return True
    except IOError as e:
        error(f'Failed to save workflow to "{path}": {e}')
        return False


#================================ COMMANDS =================================#

def convert_to_unet_loader(gguf_node: Node,
                           params   : Command) -> Node:
    """
    Converts a GGUF UNet loader node to a native comfyui UNETLoader node (safetensors checkpoints).

    Args:
        gguf_node: The original GGUF UNet loader node to be converted.
        params   : Command parameters containing checkpoint and checkpoint_url information.
    Returns:
        A new UNETLoader node with updated properties and values.
    """
    node_type      = "UNETLoader"
    checkpoint     = params.get("checkpoint")
    checkpoint_url = params.get("checkpoint_url")

    checkpoint = solve_checkpoint(checkpoint, checkpoint_url)
    if not checkpoint:
        raise ValueError("`checkpoint` not provided and could not be extracted from `checkpoint_url`")

    node = copy.deepcopy( gguf_node )
    node_properties : dict[str,Any] = {
        "Node name for S&R": node_type,
        "cnr_id"           : "comfy-core",
        "ver"              : "0.3.73",
    }
    if checkpoint_url:
        node_properties["models"] = [{
            "name"     : checkpoint,
            "url"      : checkpoint_url,
            "directory": "diffusion_models",
        }],
    node_values = [
        checkpoint,
        "default",
    ]
    node["type"          ] = node_type
    node["properties"    ] = node_properties
    node["widgets_values"] = node_values
    return node


def convert_to_clip_loader(gguf_node: Node,
                           params   : Command) -> Node:
    """
    Converts a GGUF CLIP loader node to a native comfyui CLIPLoader node (safetensors checkpoints).

    Args:
        gguf_node       : The original GGUF text-encoder (CLIP) loader node to be converted.
        params (Command): Command parameters containing checkpoint and checkpoint_url information.
    Returns:
        A new CLIPLoader node with updated properties and values.
    """
    node_type      = "CLIPLoader"
    checkpoint     = params.get("checkpoint")
    checkpoint_url = params.get("checkpoint_url")

    checkpoint = solve_checkpoint(checkpoint, checkpoint_url)
    if not checkpoint:
        raise ValueError("`checkpoint` not provided and could not be extracted from `checkpoint_url`")

    node = copy.deepcopy( gguf_node )
    node_properties : dict[str,Any] = {
        "Node name for S&R": node_type,
        "cnr_id"           : "comfy-core",
        "ver"              : "0.3.73",
    }
    if checkpoint_url:
        node_properties["models"] = [{
            "name"     : checkpoint,
            "url"      : checkpoint_url,
            "directory": "text_encoders",
        }],
    node_values = [
        checkpoint,
        "lumina2",
        "default",
    ]
    node["type"          ] = node_type
    node["properties"    ] = node_properties
    node["widgets_values"] = node_values
    return node


def write_requirements_note(original_node: Node,
                            params       : Command) -> Node:
    """
    Write a requirements note containing custom nodes and model prerequisites.

    Args:
        original_node: The original note node to be modified with the requirements.
        params       : Command parameters containing checkpoint URLs and custom nodes information.
    Returns:
        A new note node with the requirements written.
    """
    unet_checkpoint_url = params.get("unet_checkpoint_url")
    unet_checkpoint     = solve_checkpoint( params.get("unet_checkpoint"), unet_checkpoint_url )
    clip_checkpoint_url = params.get("clip_checkpoint_url")
    clip_checkpoint     = solve_checkpoint( params.get("clip_checkpoint"), clip_checkpoint_url )
    vae_checkpoint_url  = params.get("vae_checkpoint_url")
    vae_checkpoint      = solve_checkpoint( params.get("vae_checkpoint"), vae_checkpoint_url )

    if not unet_checkpoint or not unet_checkpoint_url:
        raise ValueError("`unet_checkpoint` or `unet_checkpoint_url` not provided")
    if not clip_checkpoint or not clip_checkpoint_url:
        raise ValueError("`clip_checkpoint` or `clip_checkpoint_url` not provided")
    if not vae_checkpoint or not vae_checkpoint_url:
        raise ValueError("`vae_checkpoint` or `vae_checkpoint_url` not provided")

    # try to build the custom_nodes string reading one by one the parameters custom_nodex<N>
    custom_nodes: str = ""
    for i in range(10):
        custom_nodes_i = params.get(f"custom_nodes{i}" if i>0 else "custom_nodes")
        if isinstance(custom_nodes_i, str):
            custom_nodes += f"  * {custom_nodes_i}\n"
    custom_nodes = custom_nodes.rstrip("\n")

    text=\
f"""
## Workflow Prerequisites ##

This workflow requires the following custom nodes, which can be obtained via ComfyUI-Manager:

{custom_nodes}

 Additionally, ensure you have the following 3 models downloaded and placed in their respective
 directories within your ComfyUI installation:

  {unet_checkpoint}
    * Download: {unet_checkpoint_url}
    * Local Directory: `ComfyUI/models/diffusion_models/`

  {clip_checkpoint}
    * Download: {clip_checkpoint_url}
    * Local Directory: `ComfyUI/models/text_encoders/`

  {vae_checkpoint}
    * Download: {vae_checkpoint_url}
    * Local Directory: `Comfyui/models/vae/`

## More Info ##

- https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
- https://civitai.com/models/2322533/z-image-power-nodes

Created by Martin Rizzo
  GitHub : https://github.com/martin-rizzo
  CivitAI: https://civitai.com/user/Photographer
  Reddit : https://www.reddit.com/user/FotografoVirtual
"""
    node = copy.deepcopy( original_node )
    node["widgets_values"] = [ text ]
    return node


#=============================== MIGRATION =================================#

def migrate_workflow_file(path    : Path | str,
                          commands: list[dict[str,Any]],
                          *,
                          output_suffix: str               = "-OUT",
                          output_dir   : Path | str | None = None,
                          ) -> tuple[bool, int]:
    """
    Migrates a ComfyUI workflow from GGUF to Safetensors loaders.

    Args:
        path      : Path to the input ComfyUI workflow JSON file.
        commands  : List of migration commands to apply.
        suffix    : Suffix to append to the output filename. Defaults to "-OUT".
        output_dir: Directory to save the output file. Defaults to current working directory.
    Returns:
        A tuple containing a boolean indicating whether the migration was successful,
        and an integer indicating the number of changes made during migration.
    """

    # convert to Path objects
    if isinstance(path, str):
        path = Path(path)
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    # if suffix is empty then raise an error
    output_suffix = output_suffix.strip()
    if not output_suffix:
        raise ValueError("output suffix cannot be empty because it would overwrite the original file")

    # if output_dir is none then use the working dir
    if not output_dir:
        output_dir = Path.cwd()

    # load the ComfyUI workflow from file and migrate it
    workflow = load_workflow(path)
    if not workflow:
        return False, 0
    workflow, number_of_changes = migrate_workflow( workflow, commands=commands )
    if not workflow:
        return False, 0

    # build the output path with the file name and add suffix and ".json"
    workflow_filename = path.stem  #< "workflow.json" -> "workflow"
    output_path       = output_dir / f"{workflow_filename}{output_suffix}.json"
    success = save_workflow(workflow, output_path)
    return success, number_of_changes


def migrate_workflow(workflow: Workflow | None,
                     commands: list[Command]
                     ) -> tuple[Workflow | None, int]:
    """
    Applies a list of commands to specific nodes within a workflow dictionary.

    Args:
        workflow : The workflow dictionary to modify.
        commands : List of command specifying target node types and actions.
    Returns:
        A tuple containing a modified workflow dictionary and the number of changes made.
        If any errors occur during migration, the function returns (`None`, 0)
    """
    if not isinstance(workflow, dict):
        return None, 0

    # get the node list from the workflow
    workflow = copy.deepcopy( workflow )
    nodes : list[dict] = workflow.get('nodes', [])
    if not isinstance(nodes, list):
        return None, 0

    # iterate over each node in the workflow and run the commands on it
    number_of_changes = 0
    for i, node in enumerate(nodes):

        # get the node type
        node_type : str = node.get('type',"")
        node_title: str = node.get('title',"")
        if not isinstance(node_type,str) or len(node_type)==0:
            continue

        # run the commands on the node
        for cmd in commands:
            target = cmd.get('target')
            if not isinstance(target,str):
                continue

            target_type, _, target_title = target.partition(':')
            if target_type == node_type and (not target_title or target_title == node_title):
                nodes[i] = cmd["action"](nodes[i], cmd)
                number_of_changes += 1

    return workflow, number_of_changes


#===========================================================================#
#////////////////////////////////// MAIN /////////////////////////////////#
#===========================================================================#

def main(args=None, parent_script=None):
    """
    Main entry point for the script.

    This script processes a list of ComfyUI workflow JSON files, convering
    the GGUF loder nodes to Safetensors loaders. It accepts file paths or
    directory paths. If a directory is provided, it processes all .json files
    within it.

    Args:
        args          : An optional list of arguments to parse. Default is None, 
                        which will use the command line arguments.
        parent_script : The name of the calling script if any. Used for
                        customizing help output.
    """
    prog = None
    if parent_script:
        prog = parent_script + " " + os.path.basename(__file__).split('.')[0]

    # set up argument parser for the script
    parser = argparse.ArgumentParser(
        prog            = prog,
        description     = "Migrate ComfyUI workflows from GGUF loaders to Safetensors loaders.",
        formatter_class = argparse.RawTextHelpFormatter,
    )

    parser.add_argument('workflow_files', nargs='+', metavar='FILE'            , help="One or more workflow JSON files or directories containing them.")
    parser.add_argument('--no-color'    , action='store_true'                  , help="Disable colored output.")
    parser.add_argument('--output-dir'  , type=str, default=None, metavar='DIR', help="Directory to save migrated workflow files.")
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument('--fp8' , action='store_const', const='fp8' , dest='format', help="Use FP8 format for Safetensors loaders.")
    format_group.add_argument('--bf16', action='store_const', const='bf16', dest='format', help="Use BF16 format for Safetensors loaders.")
    args = parser.parse_args(args=args)

    # if the user requested to disable colors, call disable_colors()
    if args.no_color:
        disable_colors()

    # process input paths: resolve directories and collect all JSON files
    all_workflow_files = collect_workflow_files(args.workflow_files)

    # print the list of files to be processed
    info(f"Found {len(all_workflow_files)} workflow files to process:")
    for f in all_workflow_files:
        info(f"  - {f}")

    if args.format == "fp8":
        migration_commands = MIGRATION_TO_FP8
        output_suffix      = "_FP8"
    elif args.format == "bf16":
        migration_commands = MIGRATION_TO_BF16
        output_suffix      = "_BF16"
    else:
        fatal_error(f"Invalid format specified. Valid options are '--fp8' or '--bf16'")

    # process each file
    success_count      = 0
    fail_count         = 0
    for file_path in all_workflow_files:
#        try:
            # run the migration process on the file
            success, number_of_changes = \
                migrate_workflow_file(file_path,
                                      commands      = migration_commands,
                                      output_suffix = output_suffix,
                                      output_dir    = args.output_dir
                                      )
            if success:
                success_count += 1
                info(f"Successfully processed: {file_path} with {number_of_changes} changes.")
            else:
                fail_count += 1
                info(f"Failed to process: {file_path}")
        # except Exception as e:
        #     fail_count += 1
        #     warning(f"Unexpected error processing {file_path}: {e}")

    # print summary
    info(f"\nProcessing complete.")
    info(f"Successful: {success_count}")
    info(f"Failed: {fail_count}")


if __name__ == "__main__":
    main()
