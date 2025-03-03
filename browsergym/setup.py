from setuptools import setup, find_packages

setup(
    name="browsergym",
    version="0.13.3",  # Match your current version from the screenshot
    packages=find_packages(),
    install_requires=[
        'playwright>=1.20.0',
        'gymnasium>=0.26.0',
        'numpy>=1.21.0',
        'pillow>=8.0.0',
    ],
)