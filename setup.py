from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import sys
import setuptools
import os
import platform
import subprocess

__version__ = "0.1.0"


class get_pybind_include(object):
    def __init__(self, user=False):
        self.user = user

    def __str__(self):
        import pybind11

        return pybind11.get_include(self.user)


def get_macos_sdk_path():
    try:
        # Try to get SDK path from xcrun
        sdk_path = (
            subprocess.check_output(["xcrun", "--show-sdk-path"]).decode().strip()
        )
        if os.path.exists(sdk_path):
            return sdk_path
    except:
        pass

    # Fallback to default SDK path
    default_sdk = "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
    if os.path.exists(default_sdk):
        return default_sdk

    return None


# Add compiler flags for better compatibility
extra_compile_args = ["-std=c++17", "-O3", "-Wall", "-Wextra"]
if sys.platform == "darwin":
    extra_compile_args += ["-stdlib=libc++", "-mmacosx-version-min=10.9"]
    sdk_path = get_macos_sdk_path()
    if sdk_path:
        extra_compile_args += [f"-isysroot{sdk_path}"]
        print(f"Using SDK path: {sdk_path}")

ext_modules = [
    Extension(
        "match_engine",
        ["src/lob/match_engine.cpp"],
        include_dirs=[
            get_pybind_include(),
            get_pybind_include(user=True),
        ],
        language="c++",
        extra_compile_args=extra_compile_args,
    ),
]

setup(
    name="market_maker",
    version=__version__,
    ext_modules=ext_modules,
    setup_requires=["pybind11>=2.10.0"],
    install_requires=["pybind11>=2.10.0"],
    zip_safe=False,
    python_requires=">=3.11",  # Support Python 3.11 and above
)
