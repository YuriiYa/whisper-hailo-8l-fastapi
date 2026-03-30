import os
import subprocess
import sys
import argparse
import re

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
VENV_DIR = os.path.join(ROOT_DIR, ".venv")
PYTHON_BIN = os.path.join(VENV_DIR, "bin", "python")
PIP_BIN = os.path.join(VENV_DIR, "bin", "pip")
APP_DIR = os.path.join(ROOT_DIR, "app")

def run_command(command, cwd=None):
    """Helper function to run shell commands."""
    subprocess.run(command, shell=True, cwd=cwd, check=True)

def create_venv():
    """Creates a virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print(f"Creating virtual environment in {VENV_DIR}...")
        run_command(f"{sys.executable} -m venv {VENV_DIR}")
    else:
        print("Virtual environment already exists.")

    # Upgrade pip to the latest version
    print("\nUpgrading pip inside the virtual environment...")
    run_command(f"{PIP_BIN} install --upgrade pip wheel setuptools")

def download_resources():
    try:
        run_command(f"./download_resources.sh", cwd=ROOT_DIR)
        print("Downloading inference files.")
    except subprocess.CalledProcessError:
        print("Inference files download failed.")
    return

def install_requirements(develop_install=False):
    """Installs required Python packages inside the virtual environment."""

    requirements_inference_file = os.path.join(ROOT_DIR, "requirements_inference.txt")
    if os.path.exists(requirements_inference_file):
        print("\nInstalling dependencies from requirements_inference.txt...")
        run_command(f"{PIP_BIN} install -r {requirements_inference_file}")
    else:
        pyproject_file = os.path.join(ROOT_DIR, "pyproject.toml")
        print(f"\nNo requirements_inference.txt found, installing from {pyproject_file}...")
        with open(pyproject_file) as f:
            content = f.read()
        # Extract the [tool.poetry.dependencies] section
        match = re.search(r'\[tool\.poetry\.dependencies\](.*?)(\[|\Z)', content, re.DOTALL)
        if not match:
            print("Could not find [tool.poetry.dependencies] in pyproject.toml, skipping.")
            return
        deps_block = match.group(1)
        packages = []
        for line in deps_block.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # key = "^version" or key = {version = "...", ...}
            kv = re.match(r'^(\S+)\s*=\s*"([^"]*)"', line)
            if kv:
                name, version = kv.group(1), kv.group(2)
                if name.lower() == 'python':
                    continue
                # Convert poetry version constraint to pip specifier
                pip_version = re.sub(r'^\^', '>=', version)
                pip_version = re.sub(r'^~', '~=', pip_version)
                packages.append(f'{name}{pip_version}')
        if packages:
            run_command(f"{PIP_BIN} install " + " ".join(f'"{p}"' for p in packages))

    download_resources()

    

def main():
    """Main function to set up the environment."""

    create_venv()
    install_requirements()

    print("\n✅ Setup complete! To activate the environment, run:")
    print(f"source {VENV_DIR}/bin/activate\n")

if __name__ == "__main__":
    main()
