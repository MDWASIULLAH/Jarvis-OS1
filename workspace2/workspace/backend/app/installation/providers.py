"""Read-only provider abstractions for packages and environment inventory."""
from __future__ import annotations
import os, platform
from abc import ABC, abstractmethod
from .models import EnvironmentSnapshot, PackageSpec

class PackageProvider(ABC):
    @abstractmethod
    def packages_for_goal(self, goal: str) -> tuple[PackageSpec,...]: ...
    @abstractmethod
    def package(self, package_id: str) -> PackageSpec: ...

class RulePackageProvider(PackageProvider):
    def __init__(self) -> None:
        self._packages={
            "vscode":PackageSpec("vscode","VS Code",download_mb=100,installation_mb=500,publisher="Microsoft",source_url="https://code.visualstudio.com"),
            "git":PackageSpec("git","Git",download_mb=50,installation_mb=200,publisher="Git SCM",source_url="https://git-scm.com"),
            "python":PackageSpec("python","Python",dependencies=("pip",),download_mb=35,installation_mb=150,publisher="Python Software Foundation",source_url="https://python.org"),
            "pip":PackageSpec("pip","pip",download_mb=5,installation_mb=20,publisher="Python Software Foundation"),
            "docker":PackageSpec("docker","Docker",dependencies=("wsl2",),download_mb=600,installation_mb=1200,publisher="Docker",source_url="https://docker.com"),
            "wsl2":PackageSpec("wsl2","WSL2",download_mb=150,installation_mb=600,publisher="Microsoft"),
            "android-studio":PackageSpec("android-studio","Android Studio",dependencies=("jdk","android-sdk"),download_mb=1100,installation_mb=4000,publisher="Google",source_url="https://developer.android.com"),
            "jdk":PackageSpec("jdk","JDK",download_mb=200,installation_mb=500,publisher="OpenJDK"),"android-sdk":PackageSpec("android-sdk","Android SDK",download_mb=1000,installation_mb=3000,publisher="Google"),
            "pytorch":PackageSpec("pytorch","PyTorch",dependencies=("python",),download_mb=800,installation_mb=2500,cache_mb=2000,publisher="PyTorch"),"jupyter":PackageSpec("jupyter","Jupyter",dependencies=("python",),download_mb=100,installation_mb=300,publisher="Project Jupyter"),
        }
    def packages_for_goal(self, goal:str)->tuple[PackageSpec,...]:
        text=goal.lower(); ids=("android-studio","vscode","git") if "android" in text else ("docker",) if "docker" in text else ("pytorch","jupyter","vscode") if any(x in text for x in ("ai","machine learning","data science")) else ("python","vscode") if "python" in text else ("vscode",) if "vs code" in text else ()
        return tuple(self._packages[item] for item in ids)
    def package(self, package_id:str)->PackageSpec:return self._packages[package_id]

class EnvironmentProvider(ABC):
    @abstractmethod
    def inspect(self)->EnvironmentSnapshot: ...
class LocalReadOnlyEnvironmentProvider(EnvironmentProvider):
    def inspect(self)->EnvironmentSnapshot:
        stat=os.statvfs(os.getcwd()) if hasattr(os,"statvfs") else None
        free=(stat.f_bavail*stat.f_frsize/1024/1024) if stat else 100_000.0
        return EnvironmentSnapshot(platform.system(),os.cpu_count() or 1,0.0,free,path_entries=tuple(os.environ.get("PATH","").split(os.pathsep)))
