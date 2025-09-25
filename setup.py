#!/usr/bin/env python3
"""
ConfigWatcher setup script for package distribution.
"""

from setuptools import setup, find_packages
import sys
import os

# Ensure we're running on a supported Python version
if sys.version_info < (3, 7):
    sys.exit('ConfigWatcher requires Python 3.7 or higher')

# Read the README file
def read_readme():
    """Read README.md for long description."""
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "ConfigWatcher: Configuration Hot-Reload System"

# Read version from config_watcher.py
def get_version():
    """Extract version from config_watcher.py."""
    version = {}
    with open('config_watcher.py', 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                exec(line, version)
                return version['__version__']
    return '1.0.0'  # Default version

# Core requirements
install_requires = [
    'PyYAML>=6.0,<7.0',
    'watchdog>=2.1.0,<4.0.0',
]

# Optional requirements for advanced features
extras_require = {
    'dev': [
        'pytest>=6.2.0,<8.0.0',
        'pytest-cov>=3.0.0,<5.0.0',
        'black>=22.0.0,<24.0.0',
        'flake8>=4.0.0,<6.0.0',
        'mypy>=0.950,<1.5.0',
    ],
    'json-schema': [
        'jsonschema>=4.17.0,<5.0.0',
    ],
    'performance': [
        'psutil>=5.8.0',  # For system monitoring
    ],
    'all': [
        'pytest>=6.2.0,<8.0.0',
        'pytest-cov>=3.0.0,<5.0.0',
        'jsonschema>=4.17.0,<5.0.0',
        'psutil>=5.8.0',
    ]
}

setup(
    name='configwatcher',
    version=get_version(),
    description='Configuration Hot-Reload System with multi-format support and validation',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='ConfigWatcher Team',
    author_email='configwatcher@example.com',
    url='https://github.com/example/configwatcher',

    # Package discovery
    packages=find_packages(exclude=['tests', 'tests.*', 'examples']),
    py_modules=['config_watcher'],

    # Requirements
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires='>=3.7',

    # Classification
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],

    # Keywords
    keywords=[
        'configuration', 'config', 'hot-reload', 'monitoring',
        'yaml', 'json', 'env', 'validation', 'thread-safe'
    ],

    # Entry points
    entry_points={
        'console_scripts': [
            'configwatcher-check=check_dependencies:main',
        ],
    },

    # Package data
    include_package_data=True,
    package_data={
        '': ['*.md', '*.txt', '*.yml', '*.yaml'],
    },

    # Project URLs
    project_urls={
        'Documentation': 'https://github.com/example/configwatcher/blob/main/README.md',
        'Source': 'https://github.com/example/configwatcher',
        'Tracker': 'https://github.com/example/configwatcher/issues',
    },

    # Metadata
    license='MIT',
    platforms=['any'],
    zip_safe=False,
)
