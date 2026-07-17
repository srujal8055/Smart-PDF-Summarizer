import subprocess
import sys
import os

def main():
    # Make sure we run Streamlit pointing to app/main.py
    script_path = os.path.join("app", "main.py")
    if not os.path.exists(script_path):
        print(f"Error: Could not find application entrypoint at {script_path}")
        sys.exit(1)
        
    print(f"Launching Multi-Format PDF Summarization Studio...")
    # Executing: streamlit run app/main.py
    try:
        subprocess.run(["streamlit", "run", script_path], check=True)
    except KeyboardInterrupt:
        print("\nShutting down Summarization Studio. Goodbye!")
    except Exception as e:
        print(f"Failed to launch Streamlit application: {e}")
        print("Please ensure Streamlit is installed and run 'pip install -r requirements.txt'")
        sys.exit(1)

if __name__ == "__main__":
    main()
