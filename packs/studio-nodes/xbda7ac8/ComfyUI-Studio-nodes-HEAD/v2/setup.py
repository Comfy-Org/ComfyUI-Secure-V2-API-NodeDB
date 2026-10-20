from setuptools import setup, find_packages

setup(
    name='ComfyUI-Studio-nodes',
    version='0.1.0',
    description='A set of aspect ratio tools for ComfyUI: resizing, label generation, and markdown export.',
    author='Your Name',
    packages=find_packages(where="custom_nodes"),
    package_dir={"": "custom_nodes"},
    install_requires=[
        "numpy",
        "torch",
        "Pillow"
    ],
    include_package_data=True,
    zip_safe=False,
)
