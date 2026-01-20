from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="blackduck-heatmap-metrics",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Black Duck scan heatmap metrics analyzer with interactive visualizations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/blackduck-heatmap-metrics",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
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
