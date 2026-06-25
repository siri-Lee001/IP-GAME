from setuptools import find_packages, setup


setup(
    name="ip-game",
    version="0.2.0",
    description="IP-GAME interactive film skill: SOP prompts, assets, prototype videos, verification, and offline HTML",
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    install_requires=[
        "pillow>=10.0.0",
        "imageio-ffmpeg>=0.5.1",
    ],
    entry_points={"console_scripts": ["ip-game=ip_game.cli:main"]},
    python_requires=">=3.10",
)

