import subprocess
import sys
from loguru import logger
import os

def setup_modal():
    """Set up Modal with proper error handling"""
    try:
        # Check if Modal is already installed
        try:
            import modal
            logger.info("Modal is already installed")
        except ImportError:
            logger.info("Installing Modal...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "modal"])
        
        # Check if token exists
        token_path = os.path.expanduser("~/.modal/token.json")
        if not os.path.exists(token_path):
            logger.info("Modal token not found. Starting authentication...")
            
            # Print instructions instead of opening browser
            logger.info("""
Please follow these steps to authenticate Modal:

1. Open https://modal.com/signup in your browser
2. Create an account or sign in
3. Once logged in, run this command in another terminal:
   python3 -m modal token new

Press Enter after completing these steps...
""")
            input("Press Enter to continue...")
            
            # Verify token was created
            if os.path.exists(token_path):
                logger.success("✅ Token found!")
            else:
                logger.error("❌ Token not found. Please run 'python3 -m modal token new'")
                return False
        else:
            logger.info("Modal token found")
            
        logger.success("✅ Modal setup completed!")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error during Modal setup: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    setup_modal() 