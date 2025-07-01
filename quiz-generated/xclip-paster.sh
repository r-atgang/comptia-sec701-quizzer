#!/bin/bash

# Trap Ctrl+C (SIGINT) to exit cleanly
trap "echo -e '\nScript interrupted by user.'; exit 1" SIGINT

# Loop through all .txt files in the current directory
for file in *.txt; do
    # Check if the file exists
    if [[ -f "$file" ]]; then
        echo "Preparing to write to: $file"

        while true; do
            echo -n "Press Enter to paste clipboard contents into $file, or press Backspace to skip this file: "
            IFS= read -rsn1 user_input

            # Read input byte value
            byte_val=$(printf "%d" "'$user_input")

            if [[ -z "$user_input" ]]; then
                # ENTER pressed
                break
            elif [[ $byte_val -eq 127 ]]; then
                echo -e "\nSkipping $file"
                continue 2  # Skip to next file in outer loop
            else
                echo -e "\nInvalid key. Press Enter to paste or Backspace to skip."
            fi
        done

        # Check if the clipboard has content
        if ! xclip -o -selection clipboard &>/dev/null; then
            echo "Clipboard is empty. Skipping $file."
            continue
        fi

        # Write clipboard content to the file
        xclip -o -selection clipboard > "$file"
        echo "Contents pasted into $file"

    else
        echo "No .txt files found in the current directory."
    fi
done

echo "All files processed."
