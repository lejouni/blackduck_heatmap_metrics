from setuptools import setup, find_packages
import os
import re

# Read version from __init__.py
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "blackduck_metrics", "__init__.py"), "r", encoding="utf-8") as f:
    version_match = re.search(r'^__version__\s*=\s*["\']([^"\']*)["\']', f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="blackduck-heatmap-metrics",
    version=version,
    author="Jouni Lehto",
    author_email="lehto.jouni@gmail.com",
    description="Black Duck scan heatmap metrics analyzer with interactive visualizations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/lejouni/blackduck-heatmap-metrics",
    license="MIT",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pandas>=2.0.0",
        "jinja2>=3.1.0",
        "plotly>=5.18.0",
        "tqdm>=4.65.0",
        "blackduck>=1.0.0",
        "requests>=2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "bdmetrics=blackduck_metrics.cli:main",
        ],
    },
    package_data={
        "blackduck_metrics": ["templates/*.html"],
    },
    include_package_data=True,
)
