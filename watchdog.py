import subprocess
import sys
import os
import time
import signal
import psutil
import threading

class BotWatchdog:
    def __init__(self):
        self.bot_process = None
        self.should_restart = False
        self.running = True

    def start_bot(self):
        """Start the DEV bot process."""
        print("\n🟢 Starting Kingshot Dev Bot...")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        env = os.environ.copy()
        env["KINGSHOT_DEV_MODE"] = "1"

        # Optional: if you don’t use .env, include token manually
        # env["KINGSHOT_DEV_TOKEN"] = "your_token_here"

        self.bot_process = subprocess.Popen(
            [sys.executable, "bot.py"],  # if bot.py is now standalone
            cwd=script_dir,
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        print(f"✅ Dev Bot started with PID: {self.bot_process.pid}")

    def stop_bot(self):
        """Stop the bot process gracefully."""
        if self.bot_process:
            print("\n🛑 Stopping bot...")
            try:
                # Try to terminate gracefully first
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate
                print("⚠️ Bot didn't terminate gracefully, forcing stop...")
                self.bot_process.kill()
            self.bot_process = None
            print("✅ Bot stopped")

    def restart_bot(self):
        """Restart the bot process."""
        print("\n🔁 Restarting bot...")
        self.should_restart = True
        self.stop_bot()
        time.sleep(2)  # Give it a moment to fully stop
        self.start_bot()
        self.should_restart = False

    def run(self):
        """Main watchdog loop."""
        print("\n👀 Bot Watchdog Started (non-interactive mode)")
        print("The watchdog will automatically restart the bot if it crashes.")
        print("Stop the watchdog by killing this process (Ctrl+C or your deployment tool).\n")
        
        self.start_bot()
        
        while self.running:
            try:
                # Check if bot process is still alive
                if self.bot_process and self.bot_process.poll() is not None:
                    print("\n⚠️ Bot process terminated unexpectedly")
                    if not self.should_restart:  # Don't restart if we're already restarting
                        print("🔄 Attempting to restart...")
                        self.restart_bot()
                time.sleep(1)  # Prevent high CPU usage
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"❌ Watchdog error: {e}")
                time.sleep(5)  # Wait before retrying
        # Cleanup
        self.stop_bot()
        print("\n👋 Watchdog stopped")

if __name__ == "__main__":
    watchdog = BotWatchdog()
    watchdog.run() 