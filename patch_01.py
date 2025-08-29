import os

MAIN_FILE_PATH = "main.py"
BACKUP_FILE_PATH = "main.py.bak"

# The exact block of code to find in the mdg_time_request_keyboard function
# This represents the "if len(vendors) > 1:" block from the original V14 code.
OLD_BLOCK = """        if len(vendors) > 1:
            # Multi-vendor order: show restaurant selection buttons
            rows = []
            for vendor in vendors:
                rows.append([InlineKeyboardButton(f"Request {vendor}", callback_data=f"req_vendor|{order_id}|{vendor}|{timestamp}")])
            # THIS IS THE LINE WE NEED TO REMOVE FROM THE ORIGINAL V14
            rows.append([InlineKeyboardButton("Request SAME TIME AS", callback_data=f"req_same|{order_id}|{timestamp}")])
            return InlineKeyboardMarkup(rows)"""

# The new block of code that removes the "Request SAME TIME AS" button
NEW_BLOCK = """        if len(vendors) > 1:
            # Multi-vendor order: show restaurant selection buttons ONLY
            rows = []
            for vendor in vendors:
                rows.append([InlineKeyboardButton(f"Request {vendor}", callback_data=f"req_vendor|{order_id}|{vendor}|{timestamp}")])
            return InlineKeyboardMarkup(rows)"""

def apply_patch():
    """
    Reads main.py, applies the patch, and saves the updated file.
    Creates a backup of the original file.
    """
    print(f"--- Applying Patch 01 to {MAIN_FILE_PATH} ---")

    # Ensure the main file exists
    if not os.path.exists(MAIN_FILE_PATH):
        print(f"ERROR: {MAIN_FILE_PATH} not found. Make sure this script is in the same directory.")
        return

    # Read the original content
    try:
        with open(MAIN_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read {MAIN_FILE_PATH}: {e}")
        return

    # Check if the patch is needed
    if OLD_BLOCK not in content:
        if NEW_BLOCK in content:
            print("INFO: Patch seems to be already applied. No changes made.")
        else:
            print("ERROR: Could not find the target code block to replace. Aborting patch.")
        return

    # Create a backup
    try:
        with open(BACKUP_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Backup of original file created at {BACKUP_FILE_PATH}")
    except Exception as e:
        print(f"WARNING: Could not create backup file: {e}")

    # Apply the patch
    new_content = content.replace(OLD_BLOCK, NEW_BLOCK)

    # Write the updated content back to the main file
    try:
        with open(MAIN_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ Patch applied successfully.")
    except Exception as e:
        print(f"ERROR: Could not write updated content to {MAIN_FILE_PATH}: {e}")

if __name__ == "__main__":
    apply_patch()
