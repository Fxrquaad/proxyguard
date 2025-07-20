import os
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name='proxyguard',
    version='1.0.0',
    description='A Redis-backed proxy manager for Python with Webshare.io API support and intelligent proxy selection strategies',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Fxrquaad/proxyguard',
    author='Fxrquaad',
    packages=['proxyguard'],
    install_requires=[
        'aiohttp>=3.8.0',
        'redis>=4.0.0',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)