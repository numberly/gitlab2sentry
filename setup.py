from setuptools import setup

setup(
    name="gitlab2sentry",
    version="1.7.1",
    author="Numberly",
    description="Gitlab to Sentry automatic project creation task",
    long_description="This library ensures the creation of a sentry project for all gitlab repos.",  # noqa
    url="github?",
    keywords="gitlab2sentry, g2s, automation, sentry, gitlab",
    python_requires=">=3.7, <4",
    install_requires=[
        "aiohttp",
        "awesome-slugify",
        "certifi",
        "gql",
        "idna",
        "python-gitlab",
        "pyyaml",
        "regex",
        "requests",
        "sentry-sdk",
        "Unidecode",
        "urllib3",
    ],
    extras_require={
        "test": [
            "black",
            "flake8",
            "isort",
            "mypy",
            "types-python-slugify",
            "types-PyYAML",
            "types-requests",
        ],
    },
)
