from setuptools import find_packages, setup


setup(
    name="ip-game",
    version="0.1.0",
    description="Portable interactive film game generator: story.json -> local HTML game + optional image-to-video synthesis",
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

