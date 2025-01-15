from setuptools import setup, find_packages

setup(
    name="rss_polling",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "aiohttp",
        "feedparser",
        "redis",
        "loguru",
    ],
) 