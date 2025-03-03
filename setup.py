from setuptools import setup, find_packages

setup(
    name="agentlab",
    version="0.1.0",
    package_dir={"": "src"},  # Tell setuptools that packages are under src/
    packages=find_packages(where="src"),  # Look for packages under src/
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