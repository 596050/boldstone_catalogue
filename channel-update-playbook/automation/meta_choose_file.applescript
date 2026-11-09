-- Called only after the observed Meta upload control has opened an OS file chooser.
on run argv
    if (count of argv) is not 1 then error "Expected one absolute media path"
    set mediaPath to item 1 of argv
    if mediaPath does not start with "/" then error "Expected absolute media path"
    with timeout of 5 seconds
        tell application "System Events"
            tell process "Google Chrome"
                if frontmost is false then error "Chrome does not have focus; stop instead of typing elsewhere"
                set foundChooser to false
                repeat 15 times
                    if exists sheet 1 of front window then
                        set foundChooser to true
                        exit repeat
                    end if
                    delay 0.1
                end repeat
                if foundChooser is false then error "No file chooser detected"
                if not (exists button "Open" of sheet 1 of front window) then error "The sheet is not the expected Open file chooser"
                keystroke "g" using {command down, shift down}
                delay 0.2
                keystroke mediaPath
                key code 36
                delay 0.2
                key code 36
            end tell
        end tell
    end timeout
    return "File chooser submitted; verify uploaded media in Meta before publishing"
end run
