"""Setup configuration for bookmark-ai-analyzer."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="bookmark-ai-analyzer",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered analyzer for X/Twitter bookmarks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/bookmark-ai-analyzer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.1",
            "black>=23.7",
            "isort>=5.12",
            "flake8>=6.1",
            "mypy>=1.5",
            "pre-commit>=3.3",
        ],
    },
    entry_points={
        "console_scripts": [
            "bookmark-analyzer=src.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json"],
    },
)