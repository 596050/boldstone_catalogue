-- One bounded Chrome operation. The Python supervisor also enforces a wall-clock timeout.
-- Arguments are passed directly, never interpolated into a shell command.
on run argv
    if (count of argv) is not 2 then error "Expected an exact tab URL and JavaScript payload"
    set wantedURL to item 1 of argv
    set payload to item 2 of argv
    if wantedURL does not start with "https://business.facebook.com/latest/" then error "Unexpected destination"
    with timeout of 5 seconds
        tell application "Google Chrome"
            set matches to {}
            repeat with browserWindow in windows
                repeat with browserTab in tabs of browserWindow
                    if URL of browserTab is wantedURL then set end of matches to browserTab
                end repeat
            end repeat
            if (count of matches) is not 1 then error "Expected exactly one matching Meta tab"
            set selectedTab to item 1 of matches
            return execute selectedTab javascript payload
        end tell
    end timeout
end run
