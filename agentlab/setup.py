from setuptools import setup, find_packages

setup(
    name="agentlab",
    version="0.4.0",
    packages=find_packages(),
    install_requires=[
        'browsergym>=0.13.3',
        'gymnasium',
        'numpy',
        'torch',
        'transformers',
        'accelerate',
        'peft',
        'einops',
    ],
) 