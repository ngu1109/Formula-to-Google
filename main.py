import time
import re
import threading
import unicodedata
import pyperclip
import pyautogui
from pynput import keyboard

# Define the trigger key (Right Arrow Key)
TRIGGER_KEY = keyboard.Key.right

# Define the break key (Left Arrow Key)
BREAK_KEY = keyboard.Key.left

# Toggle to include non-equation text
INCLUDE_TEXT = True  # Set to False if you only want to paste equations

# Global flag to stop the script
stop_script = threading.Event()

def normalize_text(text):
    """
    Normalizes text by replacing special Unicode characters with their ASCII equivalents.
    """
    # Replace curly quotes with straight quotes
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    # Replace long dashes with regular dashes
    text = text.replace('–', '-').replace('—', '-')
    # Replace special spaces with regular spaces
    text = text.replace('\u00A0', ' ')
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    return text

def preprocess_equation_text(equation_text):
    """
    Preprocesses the equation text by:
    - Removing \text{...} and replacing with the content inside.
    - Removing \left and \right commands.
    - Replacing \mathcal{E} with \varepsilon.
    """
    # Replace \mathcal{E} with \varepsilon
    equation_text = equation_text.replace('\\mathcal{E}', '\\varepsilon')

    # Remove \left and \right commands
    equation_text = equation_text.replace('\\left', '').replace('\\right', '')

    # Remove \text{...} and replace with the content inside
    equation_text = re.sub(r'\\text\{([^}]*)\}', r'\1', equation_text)

    return equation_text

def extract_equations_and_text(text):
    """
    Extracts all equations and text from the clipboard content.
    Returns a list of tuples (content, is_equation), where is_equation is True if content is an equation.
    """
    # Normalize text to handle special characters
    text = normalize_text(text)

    # Pattern to match equations enclosed in \[ \], \( \), $$ $$, or $ $
    pattern = r'(\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|\$.*?\$)'
    parts = re.split(pattern, text, flags=re.DOTALL)
    content_list = []
    for part in parts:
        if re.match(pattern, part, flags=re.DOTALL):
            # It's an equation
            # Remove LaTeX delimiters
            equation = re.sub(r'^\\[\[\(]{1,2}|\\[\]\)]{1,2}$|\${1,2}', '', part.strip())
            equation = preprocess_equation_text(equation.strip())
            content_list.append((equation.strip(), True))
        else:
            # It's regular text
            content_list.append((part, False))
    return content_list

def process_equation(equation_text):
    """
    Parses the equation text and simulates the necessary keystrokes
    to correctly input the equation into Google Docs.
    """
    i = 0
    length = len(equation_text)
    while i < length:
        if stop_script.is_set():
            break
        char = equation_text[i]

        # Handle \frac
        if equation_text.startswith('\\frac', i):
            # Type \frac and press space to activate fraction format
            pyautogui.write('\\frac')
            pyautogui.press('space')
            i += 5  # Skip past '\frac'

            # Process numerator
            numerator, i = extract_braces_content(equation_text, i)
            if numerator is not None:
                process_equation(numerator)
            else:
                continue

            # Press right arrow to move to denominator
            pyautogui.press('right')

            # Process denominator
            denominator, i = extract_braces_content(equation_text, i)
            if denominator is not None:
                process_equation(denominator)
            else:
                continue

            # Press right arrow to exit fraction
            pyautogui.press('right')
        # Handle subscripts '_'
        elif char == '_':
            pyautogui.write('_')
            i += 1
            subscript, i = extract_braces_or_char(equation_text, i)
            if subscript is not None:
                process_equation(subscript)
            # Press right arrow to exit subscript
            pyautogui.press('right')
        # Handle superscripts '^'
        elif char == '^':
            pyautogui.write('^')
            i += 1
            superscript, i = extract_braces_or_char(equation_text, i)
            if superscript is not None:
                process_equation(superscript)
            # Press right arrow to exit superscript
            pyautogui.press('right')
        # Handle Greek letters and other LaTeX commands starting with '\'
        elif char == '\\':
            cmd_match = re.match(r'\\[a-zA-Z]+', equation_text[i:])
            if cmd_match:
                cmd = cmd_match.group(0)
                pyautogui.write(cmd)
                pyautogui.press('space')  # Add space after LaTeX command
                i += len(cmd)
            else:
                # Just a backslash, type it
                pyautogui.write(char)
                i += 1
        else:
            # Regular character
            pyautogui.write(char)
            i += 1

def extract_braces_content(text, index):
    """
    Extracts content within braces starting from the given index.
    Returns the content and the new index position after the closing brace.
    """
    if index < len(text) and text[index] == '{':
        index += 1  # Skip '{'
        content = ''
        brace_count = 1
        while index < len(text) and brace_count > 0:
            if text[index] == '{':
                brace_count += 1
            elif text[index] == '}':
                brace_count -= 1
            if brace_count > 0:
                content += text[index]
            index += 1
        return content, index
    else:
        # No braces found, return None
        return None, index

def extract_braces_or_char(text, index):
    """
    Extracts content within braces or a single character starting from the given index.
    Returns the content and the new index position.
    """
    if index < len(text):
        if text[index] == '{':
            return extract_braces_content(text, index)
        else:
            return text[index], index + 1
    else:
        return None, index

def type_equation(equation_text):
    """
    Inserts an equation into Google Docs and types the given equation text.
    """
    if stop_script.is_set():
        return

    # Open the equation editor using the menu: Alt + I, then E
    pyautogui.hotkey('alt', 'i')
    pyautogui.press('e')

    # Remove newlines and extra spaces from the equation text
    equation_text = equation_text.replace('\n', ' ').strip()

    # Process and type the equation
    process_equation(equation_text)

    # Press right arrow key to exit equation box
    pyautogui.press('right')

def type_text(text):
    """
    Types regular text into Google Docs.
    """
    if stop_script.is_set():
        return
    pyautogui.write(text)

def on_press(key):
    global typing_thread
    try:
        if key == TRIGGER_KEY and not typing_thread.is_alive():
            # Start the typing thread
            typing_thread = threading.Thread(target=process_clipboard_content)
            typing_thread.start()
        elif key == BREAK_KEY:
            # Set the flag to stop the script
            stop_script.set()
            print("Script execution stopped by user.")
    except Exception as e:
        print(f"Error: {e}")

def process_clipboard_content():
    try:
        stop_script.clear()
        text = pyperclip.paste()
        content_list = extract_equations_and_text(text)
        for content, is_equation in content_list:
            if stop_script.is_set():
                break
            if is_equation:
                type_equation(content)
            else:
                if INCLUDE_TEXT:
                    # Type the regular text
                    type_text(content)
    except Exception as e:
        print(f"Error in typing thread: {e}")

if __name__ == "__main__":
    print("Script is running...")
    print("Press the Right Arrow key to paste content into Google Docs.")
    print("Press the Left Arrow key to stop the script if needed.")

    # Initialize typing thread
    typing_thread = threading.Thread(target=process_clipboard_content)
    typing_thread.daemon = True  # Daemon thread will close when main thread exits

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
