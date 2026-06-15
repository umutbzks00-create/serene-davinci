import webview
import os
import threading
import sys

# To ensure the window closes the entire python process on exit
def on_closed():
    os._exit(0)

if __name__ == '__main__':
    # Determine absolute path to admin.html
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin.html')
    
    # Create the window
    window = webview.create_window(
        title='Vanta Wear - Yönetim Paneli',
        url=html_path,
        width=1200,
        height=800,
        resizable=True,
        text_select=True,
        confirm_close=True
    )
    
    window.events.closed += on_closed
    
    # Start the desktop app
    webview.start(debug=False)
