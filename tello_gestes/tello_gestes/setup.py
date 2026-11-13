from glob import glob

from setuptools import setup

package_name = "tello_gestes"

setup(
    name=package_name,
    version="1.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    description="DJI Tello : suivi de visage et pilotage aux gestes",
    license="MIT",
    entry_points={
        "console_scripts": [
            "tello_driver = tello_gestes.tello_driver:main",
            "controleur = tello_gestes.controleur:main",
        ],
    },
)
