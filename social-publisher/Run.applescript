-- Background entry point. It deliberately does not activate any application.
-- Edit these two paths if this directory is moved to another Mac.
property publisherDirectory : "/Users/tprice/Documents/boldstone/social-publisher"
property pythonExecutable : "/usr/bin/python3"

on run argv
    if (count of argv) is 0 then set argv to {"doctor"}
    set commandText to quoted form of pythonExecutable & " " & quoted form of (publisherDirectory & "/publisher.py")
    repeat with argumentText in argv
        set commandText to commandText & " " & quoted form of (argumentText as text)
    end repeat
    -- The Python worker bounds every Apple event, owns its lock and writes receipts.
    -- No dialogs, notifications, keyboard input, window creation or focus restoration.
    with timeout of 86400 seconds
        return do shell script commandText
    end timeout
end run

