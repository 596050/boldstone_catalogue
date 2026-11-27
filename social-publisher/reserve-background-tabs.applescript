-- Create blank tabs in an existing background window. Never create a window,
-- set a tab URL through Chrome's native URL setter, or activate an application.
-- Chrome's native tab insertion selects the new tab inside its own window; undo
-- only that selection while the same window is still background and the newly
-- inserted tab is still selected. Never restore a changed foreground selection.
use framework "Foundation"
use framework "AppKit"
use scripting additions

on frontBundle()
    return (current application's NSWorkspace's sharedWorkspace()'s frontmostApplication()'s bundleIdentifier()) as text
end frontBundle

on stamp()
    set activeRows to current application's NSMutableDictionary's dictionary()
    tell application "Google Chrome"
        set fw to (id of front window) as integer
        set ft to (id of active tab of front window) as integer
        repeat with w in every window
            activeRows's setObject:((id of active tab of w) as integer) forKey:((id of w) as text)
        end repeat
    end tell
    set d to current application's NSMutableDictionary's dictionary()
    d's setObject:(my frontBundle()) forKey:"frontmost"
    d's setObject:fw forKey:"front_window_id"
    d's setObject:ft forKey:"front_tab_id"
    d's setObject:activeRows forKey:"active_tabs"
    return d
end stamp

on sameForeground(focusBefore, targetWindow)
    set now to my stamp()
    set oldApp to (focusBefore's objectForKey:"frontmost") as text
    set oldWindow to (focusBefore's objectForKey:"front_window_id") as integer
    set newWindow to (now's objectForKey:"front_window_id") as integer
    set oldActive to (focusBefore's objectForKey:"front_tab_id") as integer
    set newActive to (now's objectForKey:"front_tab_id") as integer
    if ((now's objectForKey:"frontmost") as text) is not oldApp or newWindow is not oldWindow or newActive is not oldActive then error "USER_FOREGROUND_CHANGED_PAUSED"
    if newWindow is targetWindow then error "BACKGROUND_WINDOW_REQUIRED"
    return now
end sameForeground

on saveReceipt(receipt, receiptPath)
    set encodedData to current application's NSJSONSerialization's dataWithJSONObject:receipt options:2 |error|:(missing value)
    if encodedData is missing value then error "JSON_ENCODING_FAILED"
    if not (encodedData's writeToFile:receiptPath atomically:true) then error "RECEIPT_WRITE_FAILED"
end saveReceipt

on run argv
    if (count of argv) is not 3 then error "Expected existing background window ID, count and receipt path"
    set wantedWindow to (item 1 of argv) as integer
    set wantedCount to (item 2 of argv) as integer
    set receiptPath to item 3 of argv
    if (current application's NSFileManager's defaultManager()'s fileExistsAtPath:receiptPath) then error "RESERVATION_RECEIPT_EXISTS_INSPECT_BEFORE_RETRY"
    if wantedCount < 1 or wantedCount > 14 then error "TAB_COUNT_OUT_OF_RANGE"
    if application id "com.google.Chrome" is not running then error "CHROME_NOT_RUNNING"
    set initial to my stamp()
    my sameForeground(initial, wantedWindow)
    set createdRows to current application's NSMutableArray's array()
    set receipt to current application's NSMutableDictionary's dictionary()
    receipt's setObject:initial forKey:"before"
    receipt's setObject:createdRows forKey:"created_tabs"
    receipt's setObject:"CREATING" forKey:"state"
    my saveReceipt(receipt, receiptPath)
    repeat wantedCount times
        my sameForeground(initial, wantedWindow)
        tell application "Google Chrome"
            set target to window id wantedWindow
            if mode of target is not "normal" then error "NORMAL_PROFILE_REQUIRED"
            set oldTab to (id of active tab of target) as integer
            set oldIndex to active tab index of target
            -- No URL property: Chrome's separate native URL setter can show its
            -- window. Navigate our own new document using JavaScript instead.
            set fresh to make new tab at end of tabs of target
            set freshID to (id of fresh) as integer
            set freshURL to URL of fresh
        end tell
        set row to current application's NSMutableDictionary's dictionary()
        row's setObject:wantedWindow forKey:"window_id"
        row's setObject:freshID forKey:"tab_id"
        row's setObject:freshURL forKey:"url"
        createdRows's addObject:row
        my saveReceipt(receipt, receiptPath)
        my sameForeground(initial, wantedWindow)
        tell application "Google Chrome"
            if ((id of active tab of target) as integer) is not freshID then error "BACKGROUND_SELECTION_CHANGED_PAUSED"
            if ((id of tab oldIndex of target) as integer) is not oldTab then error "ORIGINAL_BACKGROUND_TAB_CHANGED"
            set active tab index of target to oldIndex
        end tell
        my sameForeground(initial, wantedWindow)
        tell application "Google Chrome"
            set navResult to execute fresh javascript "(() => { if (document.hasFocus()) throw new Error('FOREGROUND_TAB_PAUSED'); location.replace('about:blank'); return 'BLANK_NAVIGATION_REQUESTED'; })()"
        end tell
        set settled to false
        repeat 40 times
            my sameForeground(initial, wantedWindow)
            tell application "Google Chrome"
                if URL of fresh is "about:blank" and loading of fresh is false then set settled to true
            end tell
            if settled then exit repeat
            delay 0.1
        end repeat
        if not settled then error "BLANK_TAB_NOT_READY"
        row's setObject:"about:blank" forKey:"url"
        row's setObject:true forKey:"target_remained_background"
        receipt's setObject:(my stamp()) forKey:"after"
        my saveReceipt(receipt, receiptPath)
    end repeat
    set finalStamp to my sameForeground(initial, wantedWindow)
    receipt's setObject:finalStamp forKey:"after"
    receipt's setObject:(initial's isEqualToDictionary:finalStamp) forKey:"all_window_selections_unchanged"
    receipt's setObject:"RESERVED" forKey:"state"
    my saveReceipt(receipt, receiptPath)
    set encoded to current application's NSJSONSerialization's dataWithJSONObject:receipt options:0 |error|:(missing value)
    return (current application's NSString's alloc()'s initWithData:encoded encoding:(current application's NSUTF8StringEncoding)) as text
end run
