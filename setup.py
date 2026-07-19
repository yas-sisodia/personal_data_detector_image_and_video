import shutil
import subprocess
import sys
import os
import platform
from huggingface_hub import login
from backend.core.model_manager import load_all_models
import time

token="hf_token"

def check_tesseract():
    """Check if Tesseract is installed."""
    print("Checking for Tesseract installation...")
    tesseract_path = shutil.which("tesseract")
    if tesseract_path:
        print(f"✅ Tesseract found at: {tesseract_path}")
        subprocess.run(["tesseract", "--version"])
    else:
        print("❌ Tesseract not found.")
        install_tesseract()


def install_tesseract():
    """Guide the user to install Tesseract OCR."""
    os_type = platform.system()

    if os_type == "Windows":
        print("\n## 🪟 Windows Users")
        print("1. Download Tesseract from:")
        print("   https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-v5.2.0.20220712.exe")
        print("\n2. Install it (recommended location):")
        print("   C:\\Program Files\\Tesseract-OCR")
        
        print("\n3. Add it to Environment Variables (PATH):")
        print("- Press Windows Key")
        print("- Search 'Environment Variables'")
        print("- Click 'Edit the system environment variables'")
        print("- Click 'Environment Variables'")
        print("- Under 'System Variables', find 'Path'")
        print("- Click 'Edit'")
        print("- Click 'New'")
        print("- Add: C:\\Program Files\\Tesseract-OCR")
        print("- Click OK and restart terminal / VS Code")

        print("\nAfter installation, restart your terminal and run:")
        print("   tesseract --version")
        print("If it prints version details → Installation successful.")
        
    elif os_type == "Darwin":  # macOS
        print("\n## 🍎 Mac Users")
        print("Run this in Terminal:")
        print("   brew install tesseract")
        print("\nAfter installation, restart your terminal and run:")
        print("   tesseract --version")
        print("If it prints version details → Installation successful.")
        
    elif os_type == "Linux":
        print("\n## Linux Users")
        print("You can install Tesseract using your package manager.")
        print("For Ubuntu/Debian:")
        print("   sudo apt install tesseract-ocr")
        print("\nAfter installation, restart your terminal and run:")
        print("   tesseract --version")
        print("If it prints version details → Installation successful.")
        
    else:
        print("Your OS is not recognized. Please manually install Tesseract from https://github.com/tesseract-ocr/tesseract.")
    
    exit(1)


def check_python_version():
    """Ensure Python 3.11 is being used."""
    print("Checking Python version...")
    python_version = sys.version_info
    if python_version.major == 3 and python_version.minor == 11:
        print(f"✅ Python version is {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python 3.11 is required. Your version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        print("Attempting to install Python 3.11...")
        install_python_3_11()


def install_python_3_11():
    """Install Python 3.11 based on the user's operating system."""
    os_type = platform.system()
    
    if os_type == "Windows":
        print("To install Python 3.11 on Windows:")
        print("1. Download Python 3.11 from https://www.python.org/downloads/")
        print("2. Make sure to check the box to add Python to PATH during installation.")
        print("After installing, re-run the script.")
    elif os_type == "Darwin":  # macOS
        print("To install Python 3.11 on macOS:")
        print("You can use Homebrew:")
        print("brew install python@3.11")
        print("After installing, re-run the script.")
    elif os_type == "Linux":
        print("To install Python 3.11 on Linux:")
        print("You can use pyenv or your package manager.")
        print("For Ubuntu, you can run:")
        print("sudo apt update && sudo apt install python3.11 python3.11-venv python3.11-dev")
        print("After installing, re-run the script.")
    else:
        print("Your OS is not recognized. Please manually install Python 3.11.")
    exit(1)


def activate_virtualenv():
    print("create virtual env by running command in terminal in root folder")
    print("python -m venv .venv")
    """Activate the virtual environment based on the OS."""
    print("Activating virtual environment...")
    if os.name == "nt":
        print('Please run this command to activate the virtual environment:')
        print('.venv\\Scripts\\Activate')
    else:
        print('Please run this command to activate the virtual environment:')
        print('source .venv/bin/activate')


def install_requirements():
    """Install required packages."""
    print("Installing dependencies from requirements.txt...")
    subprocess.run(["pip", "install", "-r", "requirements.txt"])


def check_huggingface_login():
    """Ensure Hugging Face token is set up and logged in."""
    print("Checking Hugging Face login...")
    try:
        
        login(token=token)
        print("✅ Logged in to Hugging Face Hub successfully!")
    except Exception as e:
        print("❌ Failed to log in to Hugging Face Hub.")
        print("Ensure that you have your Hugging Face token set up.")
        exit(1)


def load_models():
    """Load models from the backend."""
    print("Loading models from backend...")
    try:
        load_all_models()
        print("✅ All models loaded successfully!")
    except Exception as e:
        print("❌ Failed to load models.")
        exit(1)


def start_backend_and_frontend():
    """Start Backend (FastAPI) and Frontend (Streamlit) in separate terminals."""
    print("Starting backend (FastAPI) in a new terminal...")
    
    # Determine OS to run the correct command to open a new terminal
    os_type = platform.system()
    
    # Backend command (FastAPI)
    backend_command = "uvicorn backend.main:app --reload"
    
    # Frontend command (Streamlit)
    frontend_command = "streamlit run frontend/app.py"
    
    if os_type == "Windows":
        subprocess.Popen(f'start cmd /K "{backend_command}"', shell=True)  # Start backend in new terminal
        time.sleep(1)  # Give it a second before starting frontend in another terminal
        subprocess.Popen(f'start cmd /K "{frontend_command}"', shell=True)  # Start frontend in new terminal

    elif os_type == "Darwin" or os_type == "Linux":
        subprocess.Popen(f'gnome-terminal -- {backend_command}', shell=True)  # Start backend in new terminal
        time.sleep(1)  # Give it a second before starting frontend in another terminal
        subprocess.Popen(f'gnome-terminal -- {frontend_command}', shell=True)  # Start frontend in new terminal

    else:
        print("Your OS is not recognized. Please manually start the backend and frontend.")
        print(f"Backend command: {backend_command}")
        print(f"Frontend command: {frontend_command}")

    print("Wait until you see: 'INFO: Application startup complete.' for backend.")
    print("Frontend should be running at: http://localhost:8501")

    print("Do NOT close these terminals.")

def print_startup_commands():
    # Command to start the backend (FastAPI)
    backend_command = "uvicorn backend.main:app --reload"
    print(f"1. Open a new terminal and activate your virtual environment.")
    print(f"2. Run the following command to start the backend:\n{backend_command}")
    print("   Wait until you see: INFO: Application startup complete.")
    print("   Backend runs at: http://127.0.0.1:8000")
    print("   Do NOT close this terminal.\n")
    
    # Command to start the frontend (Streamlit)
    frontend_command = "streamlit run frontend/app.py"
    print(f"3. Open another new terminal and activate your virtual environment again.")
    print(f"4. Run the following command to start the frontend:\n{frontend_command}")
    print("   Frontend runs at: http://localhost:8501")




def main():
    """Run all checks and setup steps in order."""
    check_python_version()   # Ensure Python version is correct
    check_tesseract()        # Check if Tesseract is installed
    activate_virtualenv()    # Provide instructions for activating the virtualenv
    install_requirements()   # Install required packages
    check_huggingface_login()# Ensure user is logged in to Hugging Face
    load_models()            # Load models from the backend
    # start_backend_and_frontend()  # Start Backend (FastAPI) and Frontend (Streamlit)
    print_startup_commands()


if __name__ == "__main__":
    main()